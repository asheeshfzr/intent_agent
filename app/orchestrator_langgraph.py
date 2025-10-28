from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from .config import cfg
from .router import classify_and_extract
from .trace import record_prov, clear_trace
from .session_state import get_pending_clarify, set_pending_clarify, clear_pending_clarify
from .tools.metrics_client import call_metrics
from .tools.vector_tool import call_vector
from .tools.util_tool import run_sql
import asyncio, httpx

# Full LangGraph integration
try:
    from langgraph.graph import StateGraph, END
    _LG_AVAILABLE = True
except Exception as e:
    _LG_AVAILABLE = False
    _IMPORT_ERROR = e

class LGState(BaseModel):
    user_id: Optional[str] = None
    query: str
    intent: Optional[str] = None
    entities: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    answer: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    clarify_question: Optional[str] = None
    error: Optional[str] = None

# Node functions

def lg_route(state: LGState) -> LGState:
    parsed = classify_and_extract(state.query)
    state.intent = parsed.get('intent')
    state.entities = parsed.get('entities', {})
    state.confidence = parsed.get('confidence', 0.0)
    record_prov('intent','router','llm', {'query': state.query}, parsed, state.confidence, 'router_prompt', session_id=state.user_id)
    return state

def lg_plan(state: LGState) -> LGState:
    if state.confidence < 0.6 or not state.intent:
        state.clarify_question = (
            "Could you clarify what you want to do? For example: metrics for which service and time window, or a topic to search?"
        )
        return state
    if state.intent == 'metrics_lookup':
        svc = state.entities.get('service')
        if not svc:
            state.clarify_question = "Which service should I get metrics for? (e.g., payments or orders)"
        elif svc not in set(cfg.SERVICE_CATALOG):
            state.clarify_question = f"I don't recognize service '{svc}'. Should I use one of: {', '.join(cfg.SERVICE_CATALOG)}?"
        elif not state.entities.get('window'):
            state.clarify_question = "What time window should I use (e.g., 5m, 1h)?"
    elif state.intent == 'calc_compare':
        targets = state.entities.get('targets') or []
        if len(targets) < 2:
            state.clarify_question = "Which two services should I compare (e.g., payments vs orders)?"
    elif state.intent == 'knowledge_lookup':
        # allow running with the full query
        pass
    return state

def lg_act(state: LGState) -> LGState:
    if state.clarify_question:
        return state
    try:
        if state.intent == 'metrics_lookup':
            svc = state.entities.get('service') or 'payments'
            window = state.entities.get('window') or '5m'
            res = asyncio.run(call_metrics(svc, window))
            record_prov('fetch_metrics','tool','metrics', {'service':svc,'window':window}, res.dict(), res.score, 'direct_api', session_id=state.user_id)
            if res.success:
                p95 = res.data.get('p95')
                if p95 and p95 > cfg.DEFAULT_P95_THRESHOLD_MS:
                    state.answer = f"{svc} p95={p95}ms > {cfg.DEFAULT_P95_THRESHOLD_MS}ms"
                    state.data = {'service': svc, 'window': window, 'p95': p95, 'threshold_ms': cfg.DEFAULT_P95_THRESHOLD_MS, 'verdict': 'above'}
                else:
                    state.answer = f"{svc} p95={p95}ms OK"
                    state.data = {'service': svc, 'window': window, 'p95': p95, 'threshold_ms': cfg.DEFAULT_P95_THRESHOLD_MS, 'verdict': 'ok'}
            else:
                # docs fallback
                try:
                    r = httpx.get(f'{cfg.DOCS_BASE_URL}/search', params={'q': svc}, timeout=cfg.HTTP_TIMEOUT_SECONDS)
                    docs = r.json()
                    record_prov('http_docs','tool','http_docs', {'q':svc}, docs, 0.5, 'http_fallback', session_id=state.user_id)
                    if docs.get('items'):
                        t = docs['items'][0]
                        state.answer = 'Found docs: ' + t['title']
                        state.data = {'query': svc, 'top': {'title': t['title'], 'snippet': t.get('snippet','')}}
                        return state
                except Exception:
                    pass
                state.clarify_question = 'No metrics found'
        elif state.intent == 'knowledge_lookup':
            vec = call_vector(state.query)
            record_prov('vector','tool','vector', {'query':state.query}, vec.dict(), vec.score, 'vector_search', session_id=state.user_id)
            if vec.success and vec.score >= cfg.KNOWLEDGE_SCORE_MIN:
                top = vec.data.get('top', {})
                title = (top.get('payload',{}) or {}).get('title','unknown')
                snippet = (top.get('payload',{}) or {}).get('text','')[:300]
                state.answer = f"Found doc: {title} - snippet: {snippet}"
                state.data = {'query': state.query, 'top': {'title': title, 'snippet': snippet}}
            else:
                # fallback docs
                try:
                    r = httpx.get(f'{cfg.DOCS_BASE_URL}/search', params={'q': state.query}, timeout=cfg.HTTP_TIMEOUT_SECONDS)
                    docs = r.json()
                    record_prov('http_docs','tool','http_docs', {'q':state.query}, docs, 0.5, 'http_fallback', session_id=state.user_id)
                    if docs.get('items'):
                        t = docs['items'][0]
                        state.answer = 'Found doc: ' + t['title']
                        state.data = {'query': state.query, 'top': {'title': t['title'], 'snippet': t.get('snippet','')}}
                        return state
                except Exception:
                    pass
                state.clarify_question = 'No reliable docs found. Clarify?'
        elif state.intent == 'calc_compare':
            sql_res = run_sql('SELECT * FROM services')
            rows = sql_res.data.get('rows', [])
            d = {r[0]: r[1] for r in rows}
            targets = state.entities.get('targets') or []
            if len(targets) < 2:
                state.clarify_question = "Which two services should I compare (e.g., payments vs orders)?"
                return state
            a, b = targets[:2]
            if a in d and b in d:
                diff = d[a] - d[b]
                state.answer = f"{a.capitalize()} p95={d[a]}ms, {b.capitalize()} p95={d[b]}ms, diff={diff}ms"
                state.data = {'targets': [a,b], 'p95s': {a: d[a], b: d[b]}, 'diff_ms': diff}
            else:
                state.clarify_question = 'Targets not found in table'
    except Exception as e:
        state.error = str(e)
    return state

def lg_reflect(state: LGState) -> LGState:
    if state.clarify_question:
        set_pending_clarify(state.user_id, state.clarify_question)
    else:
        clear_pending_clarify(state.user_id)
    return state

# Conditional edges

def _needs_clarify(state: LGState) -> bool:
    return bool(state.clarify_question)

def _has_answer(state: LGState) -> bool:
    return bool(state.answer) and not state.clarify_question

# Build and cache the LangGraph graph
_graph = None

def _build_graph():
    global _graph
    if not _LG_AVAILABLE:
        raise ImportError(f"langgraph is not available: {_IMPORT_ERROR}")
    if _graph is not None:
        return _graph
    g = StateGraph(LGState)
    g.add_node('route', lg_route)
    g.add_node('plan', lg_plan)
    g.add_node('act', lg_act)
    g.add_node('reflect', lg_reflect)
    g.set_entry_point('route')
    g.add_edge('route', 'plan')
    g.add_edge('plan', 'act')
    g.add_edge('act', 'reflect')
    # Decide next step based on state
    g.add_conditional_edges(
        'reflect',
        lambda s: 'clarify' if _needs_clarify(s) else ('finalize' if _has_answer(s) else 'clarify'),
        {'clarify': END, 'finalize': END}
    )
    _graph = g.compile()
    return _graph

# Entry point for adapter

def run_langgraph(query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    if not _LG_AVAILABLE:
        # Surface a clear error so adapter can fallback if desired
        raise ImportError(f"langgraph is not installed: {_IMPORT_ERROR}")
    clear_trace()
    app = _build_graph()
    state = LGState(query=query, user_id=user_id)
    # Run end to end
    out = app.invoke(state)
    if out.clarify_question:
        return {'answer': out.clarify_question, 'status': 'clarify', 'trace': []}
    if out.answer:
        return {'answer': out.answer, 'status': 'done', 'trace': [], 'data': out.data}
    return {'answer': 'Unknown state', 'status': 'error', 'trace': []}
