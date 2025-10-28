from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from .config import cfg
from .router import classify_and_extract
from .trace import record_prov, clear_trace
from .session_state import get_pending_clarify, set_pending_clarify, clear_pending_clarify
from .tools.metrics_client import call_metrics
from .tools.vector_tool import call_vector
from .tools.util_tool import run_sql
import asyncio, httpx

@dataclass
class OrchestratorState:
    user_id: Optional[str]
    query: str
    intent: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    clarify_question: Optional[str] = None
    status: str = "pending"  # pending|clarify|done|error
    answer: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

# Nodes

def node_route(st: OrchestratorState) -> OrchestratorState:
    parsed = classify_and_extract(st.query)
    st.intent = parsed.get('intent')
    st.entities = parsed.get('entities', {})
    st.confidence = parsed.get('confidence', 0.0)
    record_prov('intent','router','llm', {'query': st.query}, parsed, st.confidence, 'router_prompt', session_id=st.user_id)
    return st

def node_plan(st: OrchestratorState) -> OrchestratorState:
    # Determine missing info and set clarify if needed
    if st.confidence < 0.6 or not st.intent:
        st.clarify_question = "Could you clarify what you want to do? For example: metrics for which service and time window, or a topic to search?"
        return st
    if st.intent == 'metrics_lookup':
        svc = st.entities.get('service')
        if not svc:
            st.clarify_question = "Which service should I get metrics for? (e.g., payments or orders)"
        elif svc not in set(cfg.SERVICE_CATALOG):
            st.clarify_question = f"I don't recognize service '{svc}'. Should I use one of: {', '.join(cfg.SERVICE_CATALOG)}?"
        elif not st.entities.get('window'):
            st.clarify_question = "What time window should I use (e.g., 5m, 1h)?"
    elif st.intent == 'calc_compare':
        targets = st.entities.get('targets') or []
        if len(targets) < 2:
            st.clarify_question = "Which two services should I compare (e.g., payments vs orders)?"
    elif st.intent == 'knowledge_lookup':
        # allow running with the full query
        pass
    return st

def node_act(st: OrchestratorState) -> OrchestratorState:
    if st.clarify_question:
        return st
    if st.intent == 'metrics_lookup':
        svc = st.entities.get('service') or 'payments'
        window = st.entities.get('window') or '5m'
        res = asyncio.run(call_metrics(svc, window))
        record_prov('fetch_metrics','tool','metrics', {'service':svc,'window':window}, res.dict(), res.score, 'direct_api', session_id=st.user_id)
        st.tool_results.append(res.dict())
        if res.success:
            p95 = res.data.get('p95')
            if p95 and p95 > cfg.DEFAULT_P95_THRESHOLD_MS:
                st.answer = f"{svc} p95={p95}ms > {cfg.DEFAULT_P95_THRESHOLD_MS}ms"
                st.data = {'service': svc, 'window': window, 'p95': p95, 'threshold_ms': cfg.DEFAULT_P95_THRESHOLD_MS, 'verdict': 'above'}
            else:
                st.answer = f"{svc} p95={p95}ms OK"
                st.data = {'service': svc, 'window': window, 'p95': p95, 'threshold_ms': cfg.DEFAULT_P95_THRESHOLD_MS, 'verdict': 'ok'}
            st.status = 'done'
        else:
            # Try docs fallback
            try:
                r = httpx.get(f'{cfg.DOCS_BASE_URL}/search', params={'q': svc}, timeout=cfg.HTTP_TIMEOUT_SECONDS)
                docs = r.json()
                record_prov('http_docs','tool','http_docs', {'q':svc}, docs, 0.5, 'http_fallback', session_id=st.user_id)
                if docs.get('items'):
                    t = docs['items'][0]
                    st.answer = 'Found docs: ' + t['title']
                    st.data = {'query': svc, 'top': {'title': t['title'], 'snippet': t.get('snippet','')}}
                    st.status = 'done'
                    return st
            except Exception:
                pass
            st.clarify_question = 'No metrics found'
    elif st.intent == 'knowledge_lookup':
        vec = call_vector(st.query)
        record_prov('vector','tool','vector', {'query':st.query}, vec.dict(), vec.score, 'vector_search', session_id=st.user_id)
        st.tool_results.append(vec.dict())
        if vec.success and vec.score >= cfg.KNOWLEDGE_SCORE_MIN:
            top = vec.data.get('top', {})
            title = (top.get('payload',{}) or {}).get('title','unknown')
            snippet = (top.get('payload',{}) or {}).get('text','')[:300]
            st.answer = f"Found doc: {title} - snippet: {snippet}"
            st.data = {'query': st.query, 'top': {'title': title, 'snippet': snippet}}
            st.status = 'done'
        else:
            # Fallback docs search
            try:
                r = httpx.get(f'{cfg.DOCS_BASE_URL}/search', params={'q': st.query}, timeout=cfg.HTTP_TIMEOUT_SECONDS)
                docs = r.json()
                record_prov('http_docs','tool','http_docs', {'q':st.query}, docs, 0.5, 'http_fallback', session_id=st.user_id)
                if docs.get('items'):
                    t = docs['items'][0]
                    st.answer = 'Found doc: ' + t['title']
                    st.data = {'query': st.query, 'top': {'title': t['title'], 'snippet': t.get('snippet','')}}
                    st.status = 'done'
                    return st
            except Exception:
                pass
            st.clarify_question = 'No reliable docs found. Clarify?'
    elif st.intent == 'calc_compare':
        sql_res = run_sql('SELECT * FROM services')
        rows = sql_res.data.get('rows', [])
        d = {r[0]: r[1] for r in rows}
        targets = st.entities.get('targets') or []
        if len(targets) < 2:
            st.clarify_question = "Which two services should I compare (e.g., payments vs orders)?"
            return st
        a, b = targets[:2]
        if a in d and b in d:
            diff = d[a] - d[b]
            st.answer = f"{a.capitalize()} p95={d[a]}ms, {b.capitalize()} p95={d[b]}ms, diff={diff}ms"
            st.data = {'targets': [a,b], 'p95s': {a: d[a], b: d[b]}, 'diff_ms': diff}
            st.status = 'done'
        else:
            st.clarify_question = 'Targets not found in table'
    return st

def node_reflect(st: OrchestratorState) -> OrchestratorState:
    # If we asked a clarification, persist and mark clarify
    if st.clarify_question:
        set_pending_clarify(st.user_id, st.clarify_question)
        st.status = 'clarify'
    else:
        clear_pending_clarify(st.user_id)
    return st

def node_finalize(st: OrchestratorState) -> Dict[str, Any]:
    if st.status == 'done':
        return {'answer': st.answer, 'status': 'done', 'trace': [], 'data': st.data}
    if st.status == 'clarify':
        return {'answer': st.clarify_question or 'Please clarify', 'status': 'clarify', 'trace': []}
    return {'answer': 'Unknown state', 'status': 'error', 'trace': []}

# Graph runner

def run_graph(query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    clear_trace()
    st = OrchestratorState(user_id=user_id, query=query)
    st = node_route(st)
    st = node_plan(st)
    st = node_act(st)
    st = node_reflect(st)
    return node_finalize(st)
