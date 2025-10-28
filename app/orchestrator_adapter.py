# This orchestrator will use LangChain agent if USE_LANGCHAIN true, otherwise fallback to simple flow.
from .config import cfg
from .router import classify_and_extract
from .trace import record_prov, clear_trace
from .tools.metrics_client import call_metrics
from .tools.vector_tool import call_vector
from .tools.util_tool import run_sql, calc
from .langchain_integration import LocalLangChain, make_langchain_tools
from .langchain_adapter import run_agent_with_tools, Tool as LocalTool
import asyncio, time, httpx, json, os
from typing import List
from .session_state import get_pending_clarify, set_pending_clarify, clear_pending_clarify
try:
    from .orchestrator_langgraph import run_langgraph as run_graph_engine  # full LangGraph
    _HAS_FULL_LG = True
except Exception:
    from .orchestrator_graph import run_graph as run_graph_engine          # minimal fallback
    _HAS_FULL_LG = False

def execute_workflow(query: str, user_id: str = None):
    clear_trace()
    # If LangGraph is enabled, run the stateful graph orchestrator (full if available, else minimal) and return
    if getattr(cfg, 'USE_LANGGRAPH', False):
        try:
            return run_graph_engine(query, user_id)
        except ImportError:
            # Fallback to minimal in-process graph
            from .orchestrator_graph import run_graph as _fallback_graph
            return _fallback_graph(query, user_id)
    parsed = classify_and_extract(query)
    record_prov('intent','router','llm', {'query': query}, parsed, parsed.get('confidence',0.0), 'router_prompt', session_id=user_id)
    intent = parsed.get('intent')
    entities = parsed.get('entities', {})
    conf = parsed.get('confidence', 0.0)
    # Feedback loop: low confidence or missing entities -> ask clarifying question
    clarify_q = None
    if conf < 0.6 or not intent:
        clarify_q = "Could you clarify what you want to do? For example: metrics for which service and time window, or a topic to search?"
    else:
        if intent == 'metrics_lookup':
            known_services = set(cfg.SERVICE_CATALOG)
            svc = entities.get('service')
            if not svc:
                clarify_q = "Which service should I get metrics for? (e.g., payments or orders)"
            elif svc not in known_services:
                clarify_q = f"I don't recognize service '{svc}'. Should I use 'payments' or 'orders'?"
            elif not entities.get('window'):
                clarify_q = "What time window should I use (e.g., 5m, 1h)?"
        elif intent == 'calc_compare':
            targets = entities.get('targets') or []
            if len(targets) < 2:
                clarify_q = "Which two services should I compare (e.g., payments vs orders)?"
        elif intent == 'knowledge_lookup':
            # Do not require explicit topic; we'll run vector search with the whole query
            pass
    # If there is an outstanding clarify for this user and still missing info, keep asking
    pend = get_pending_clarify(user_id)
    if pend and clarify_q is None and intent in ('metrics_lookup','calc_compare','knowledge_lookup'):
        # If still missing typical required entity, repeat previous clarify
        clarify_q = pend
    if clarify_q is not None:
        record_prov('clarify','control','orchestrator', {'query': query}, {'question': clarify_q}, 0.5, 'clarify_question', session_id=user_id)
        set_pending_clarify(user_id, clarify_q)
        return {'answer': clarify_q, 'status': 'clarify', 'trace': []}
    # If LangChain enabled, use agent for all intents (including metrics)
    if cfg.USE_LANGCHAIN:
        try:
            lc = LocalLangChain()
            tools = make_langchain_tools()
            # Constrain tools by capability to avoid indecision/loops
            cap = None
            if intent == 'metrics_lookup':
                cap = 'metrics'
            elif intent == 'knowledge_lookup':
                cap = 'knowledge'
            elif intent == 'calc_compare':
                cap = 'calc'
            if cap:
                tools = [t for t in tools if cap in (getattr(t, 'capabilities', []) or [])]
            # New-style agent construction (ReAct)
            from langchain.agents import create_react_agent, AgentExecutor
            from langchain.prompts import PromptTemplate
            # Load ReAct prompt from file
            try:
                with open(os.path.join(cfg.PROMPTS_DIR, cfg.REACT_PROMPT_VERSION), 'r') as f:
                    react_text = f.read()
            except Exception:
                react_text = "You are an operations assistant. Use tools.\n\nAvailable tools:\n{tools}\n\nYou can use one of these tool names: {tool_names}\n\nUser question: {input}\n\n{agent_scratchpad}\n"
            react_prompt = PromptTemplate.from_template(react_text)
            agent = create_react_agent(lc, tools, react_prompt)
            executor = AgentExecutor(
                agent=agent,
                tools=tools,
                handle_parsing_errors=True,
                max_iterations=cfg.AGENT_MAX_ITERATIONS,
                verbose=False,
            )
            result = executor.invoke({"input": query})
            out = result.get('output') if isinstance(result, dict) else result
            # If the agent bailed out due to parse/iteration limits, try guided single-steps per intent
            if isinstance(out, str) and 'Agent stopped' in out:
                if intent == 'metrics_lookup':
                    # Force-run the metrics tool with the extracted entities
                    svc = entities.get('service', 'payments')
                    window = entities.get('window', '5m')
                    arg = f"service={svc};window={window}"
                    mt = next((t for t in tools if 'metrics' in (getattr(t, 'capabilities', []) or [])), None)
                    if mt is not None:
                        tool_raw = mt.func(arg)
                        # tool_raw may be a JSON string or already a dict
                        if isinstance(tool_raw, str):
                            try:
                                tool_json = json.loads(tool_raw)
                            except Exception:
                                tool_json = {'tool':'metrics', 'success': False, 'data': {'error': 'parse'}, 'score': 0.0}
                        elif isinstance(tool_raw, dict):
                            tool_json = tool_raw
                        else:
                            tool_json = {'tool':'metrics', 'success': False, 'data': {'error': 'unknown tool output type'}, 'score': 0.0}
                        # Record a successful agent step with the tool observation
                        record_prov('langchain_agent','agent','langchain', {'query':query}, {'output': tool_json}, 0.9, 'langchain_agent', session_id=user_id)
                        # Compose final answer similar to deterministic path
                        data = tool_json.get('data', {})
                        p95 = data.get('p95')
                        thr = cfg.DEFAULT_P95_THRESHOLD_MS
                        if isinstance(p95, (int, float)):
                            sign = '>' if p95 > thr else '<='
                            answer = f"{svc} p95={p95}ms {sign} {thr}ms"
                            data_payload = {
                                'service': svc,
                                'window': window,
                                'p95': p95,
                                'threshold_ms': thr,
                                'verdict': 'above' if p95 > thr else 'ok'
                            }
                        else:
                            answer = json.dumps(tool_json)
                            data_payload = {'raw': tool_json}
                        return {'answer': answer, 'status': 'done', 'trace': [], 'data': data_payload}
                elif intent == 'knowledge_lookup':
                    vt = next((t for t in tools if 'knowledge' in (getattr(t, 'capabilities', []) or [])), None)
                    if vt is not None:
                        tool_raw = vt.func(query)
                        tool_json = json.loads(tool_raw) if isinstance(tool_raw, str) else tool_raw
                        record_prov('langchain_agent','agent','langchain', {'query':query}, {'output': tool_json}, 0.9, 'langchain_agent', session_id=user_id)
                        data = tool_json.get('data', {})
                        top = data.get('top') or {}
                        title = (top.get('payload', {}) or {}).get('title') or top.get('title') or 'unknown'
                        snippet = (top.get('payload', {}) or {}).get('text') or top.get('text') or ''
                        if not top or (isinstance(top.get('score'), (int,float)) and top.get('score') < cfg.KNOWLEDGE_SCORE_MIN_AGENT):
                            cq = "I couldn't find a strong match. Can you specify the topic or doc name?"
                            record_prov('clarify','control','orchestrator', {'query': query}, {'question': cq}, 0.5, 'clarify_question', session_id=user_id)
                            return {'answer': cq, 'status': 'clarify', 'trace': []}
                        answer = f"Found doc: {title} - snippet: {snippet[:300]}"
                        data_payload = {'query': query, 'top': {'title': title, 'snippet': snippet[:300], 'score': top.get('score')}}
                        return {'answer': answer, 'status': 'done', 'trace': [], 'data': data_payload}
                elif intent == 'calc_compare':
                    # Deterministic compute: run SQL to get p95 per service and compute diff
                    sql_res = run_sql('SELECT * FROM services')
                    record_prov('langchain_agent','agent','langchain', {'query':query}, {'output': sql_res.dict()}, 0.9, 'langchain_agent', session_id=user_id)
                    rows = sql_res.data.get('rows', []) if hasattr(sql_res, 'data') else []
                    d = {r[0]: r[1] for r in rows}
                    # Also aggregate live metrics for the same services to demonstrate multi-tool aggregation
                    # choose up to two services from SQL result for live metrics aggregation
                    services = list(d.keys())[:2]
                    metrics_live = {}
                    for s in services:
                        try:
                            m = asyncio.run(call_metrics(s, entities.get('window','15m')))
                            record_prov('fetch_metrics','tool','metrics', {'service':s,'window':entities.get('window','15m')}, m.dict(), m.score, 'direct_api', session_id=user_id)
                            if m.success:
                                metrics_live[s] = m.data.get('p95')
                        except Exception:
                            pass
                    if len(services) >= 2 and all(s in d for s in services):
                        diff = d[services[0]] - d[services[1]]
                        parts = [f"{services[0].capitalize()} p95={d[services[0]]}ms", f"{services[1].capitalize()} p95={d[services[1]]}ms", f"diff={diff}ms"]
                        if metrics_live:
                            live_str = ", ".join([f"{k} {v}ms" for k,v in metrics_live.items() if v is not None])
                            parts.append(f"(live: {live_str})")
                        answer = ", ".join(parts)
                        data_payload = {'targets': services, 'p95s': {services[0]: d[services[0]], services[1]: d[services[1]]}, 'diff_ms': diff, 'live_p95s': metrics_live}
                    else:
                        answer = json.dumps(sql_res.dict())
                        data_payload = {'raw': sql_res.dict()}
                    return {'answer': answer, 'status': 'done', 'trace': [], 'data': data_payload}
                # Otherwise record bailout and fall through to deterministic handlers below
                record_prov('langchain_agent','agent','langchain', {'query':query}, {'output': out}, 0.5, 'langchain_agent_bailout', session_id=user_id)
            else:
                # Post-agent guardrails: if the agent returned an error-like payload for metrics/calc, ask a clarifying question
                # Also trigger if the tool is metrics with success=false regardless of routed intent
                if True:
                    maybe = None
                    raw = out
                    if isinstance(out, str):
                        try:
                            maybe = json.loads(out)
                        except Exception:
                            maybe = None
                    elif isinstance(out, dict):
                        maybe = out
                    if isinstance(maybe, dict):
                        succ = maybe.get('success')
                        data = maybe.get('data') or {}
                        # error may be nested as a JSON string
                        err = None
                        if isinstance(data, dict):
                            err = data.get('error')
                            # try to parse nested error JSON
                            if isinstance(err, str):
                                try:
                                    inner = json.loads(err)
                                    if isinstance(inner, dict) and inner.get('error'):
                                        err = inner.get('error')
                                except Exception:
                                    pass
                        err = err or maybe.get('error')
                        tool_name = maybe.get('tool')
                        if succ is False or err or tool_name == 'metrics' and succ is False:
                            cq = "I couldn't find that. Which service(s) should I use? For example: payments and orders, and a time window."
                            record_prov('clarify','control','orchestrator', {'query': query}, {'question': cq, 'raw': raw}, 0.5, 'clarify_question', session_id=user_id)
                            return {'answer': cq, 'status': 'clarify', 'trace': []}
                record_prov('langchain_agent','agent','langchain', {'query':query}, {'output': out}, 0.9, 'langchain_agent', session_id=user_id)
                return {'answer': out, 'status':'done', 'trace': []}
        except Exception as e:
            # Log and fall back
            record_prov('langchain_agent_error','agent','langchain', {'query':query}, {'error': str(e)}, 0.0, 'langchain_agent_error', session_id=user_id)
    # Else simple deterministic flow (fallback)
    if intent == 'metrics_lookup':
        svc = entities.get('service') or 'payments'; window = entities.get('window') or '5m'
        # We are inside FastAPI's threadpool worker (no active event loop), so use asyncio.run
        metrics_res = asyncio.run(call_metrics(svc, window))
        record_prov('fetch_metrics','tool','metrics', {'service':svc,'window':window}, metrics_res.dict(), metrics_res.score, 'direct_api', session_id=user_id)
        if not metrics_res.success:
            # try docs fallback
            try:
                r = httpx.get(f'{cfg.DOCS_BASE_URL}/search', params={'q': svc}, timeout=cfg.HTTP_TIMEOUT_SECONDS)
                docs = r.json()
                record_prov('http_docs','tool','http_docs', {'q':svc}, docs, 0.5, 'http_fallback', session_id=user_id)
                if docs.get('items'):
                    t = docs['items'][0]
                    return {'answer':'Found docs: ' + t['title'], 'status':'done', 'trace': [], 'data': {'query': svc, 'top': {'title': t['title'], 'snippet': t.get('snippet','')}}}
            except Exception:
                pass
            return {'answer':'No metrics found', 'status':'clarify', 'trace': []}
        p95 = metrics_res.data.get('p95')
        if p95 and p95 > cfg.DEFAULT_P95_THRESHOLD_MS:
            ans = f"{svc} p95={p95}ms > {cfg.DEFAULT_P95_THRESHOLD_MS}ms"
        else:
            ans = f"{svc} p95={p95}ms OK"
        clear_pending_clarify(user_id)
        data_payload = {'service': svc, 'window': window, 'p95': p95, 'threshold_ms': cfg.DEFAULT_P95_THRESHOLD_MS, 'verdict': 'above' if p95 and p95 > cfg.DEFAULT_P95_THRESHOLD_MS else 'ok'}
        return {'answer': ans, 'status':'done', 'trace': [], 'data': data_payload}
    if intent == 'knowledge_lookup':
        vec_res = call_vector(query)
        record_prov('vector','tool','vector', {'query':query}, vec_res.dict(), vec_res.score, 'vector_search', session_id=user_id)
        if not vec_res.success or vec_res.score < cfg.KNOWLEDGE_SCORE_MIN:
            # fallback http docs
            try:
                r = httpx.get(f'{cfg.DOCS_BASE_URL}/search', params={'q': query}, timeout=cfg.HTTP_TIMEOUT_SECONDS)
                docs = r.json()
                record_prov('http_docs','tool','http_docs', {'q':query}, docs, 0.5, 'http_fallback', session_id=user_id)
                if docs.get('items'):
                    t = docs['items'][0]
                    return {'answer': 'Found doc: ' + t['title'], 'status':'done', 'trace': [], 'data': {'query': query, 'top': {'title': t['title'], 'snippet': t.get('snippet','')}}}
            except Exception:
                pass
            return {'answer': 'No reliable docs found. Clarify?', 'status':'clarify', 'trace': []}
        top = vec_res.data.get('top', {})
        ans = f"Found doc: {top.get('payload',{}).get('title','unknown')} - snippet: {top.get('payload',{}).get('text','')[:300]}"
        data_payload = {'query': query, 'top': {'title': top.get('payload',{}).get('title','unknown'), 'snippet': top.get('payload',{}).get('text','')[:300]}}
        clear_pending_clarify(user_id)
        return {'answer': ans, 'status':'done', 'trace': [], 'data': data_payload}
    if intent == 'calc_compare':
        targets = entities.get('targets')
        if not targets and 'and' in query:
            parts = [p.strip() for p in query.split('and')]
            targets = [p for p in parts if p in cfg.SERVICE_CATALOG]
        if targets and len(targets) >= 2:
            sql = 'SELECT * FROM services'
            sql_res = run_sql(sql)
            rows = sql_res.data.get('rows', [])
            d = {r[0]: r[1] for r in rows}
            if all(t in d for t in targets[:2]):
                a, b = targets[:2]
                diff = d[a] - d[b]
                ans = f"{a.capitalize()} p95={d[a]}ms, {b.capitalize()} p95={d[b]}ms, diff={diff}ms"
                data_payload = {'targets': [a,b], 'p95s': {a: d[a], b: d[b]}, 'diff_ms': diff}
                clear_pending_clarify(user_id)
                return {'answer': ans, 'status':'done', 'trace': [], 'data': data_payload}
        return {'answer':'Which two services?', 'status':'clarify', 'trace': []}
    return {'answer':'Unknown intent','status':'clarify','trace': []}
