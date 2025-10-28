from .orchestrator_adapter import execute_workflow
from .trace import get_trace
from .config import cfg
from .schemas import QueryResponse, TraceItem

def _compact_trace(nodes, last_n: int):
    sl = nodes[-last_n:]
    compact = []
    for n in sl:
        compact.append(TraceItem(
            ts=n.get('ts'),
            node_id=n.get('node_id'),
            node_type=n.get('node_type'),
            tool=n.get('tool'),
            decision_rule=n.get('decision_rule'),
            confidence=n.get('confidence'),
        ).dict())
    return compact

def handle_query(query: str, user_id: str = None):
    res = execute_workflow(query, user_id)
    # Build standardized response
    status = res.get('status', 'done')
    summary = res.get('answer', '')
    data = res.get('data', {})
    # Attach a short inline trace to the response (configurable)
    try:
        trace = _compact_trace(get_trace(), last_n=cfg.TRACE_COMPACT_LAST_N)
    except Exception:
        trace = res.get('trace', []) or []
    return QueryResponse(status=status, summary=summary, data=data, trace=trace).dict()
