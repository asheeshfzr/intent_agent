import time
TRACE_LOG = []
def record_prov(node_id, node_type, tool, input_summary, output_summary, confidence, decision_rule, parent=None, session_id=None):
    TRACE_LOG.append({
        'ts': time.time(),
        'node_id': node_id,
        'node_type': node_type,
        'tool': tool,
        'input': input_summary,
        'output': output_summary,
        'confidence': confidence,
        'decision_rule': decision_rule,
        'parent': parent,
        'session_id': session_id
    })
def get_trace():
    return TRACE_LOG
def clear_trace():
    TRACE_LOG.clear()
