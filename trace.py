"""
Lightweight in-memory tracing / provenance store for local development.

Provides:
- new_trace_id(session_id=None) -> str
- record_prov(..., session_id=None, trace_id=None) -> str (returns trace_id)
- get_trace(trace_id) -> list
- clear_trace(trace_id) -> None
- get_trace_summary(trace_id) -> dict
"""
from typing import Any, Dict, List, Optional
from uuid import uuid4
import time
import threading

_lock = threading.Lock()
_traces: Dict[str, List[Dict[str, Any]]] = {}

def new_trace_id(session_id: Optional[str] = None) -> str:
    """Create a new trace id and initialize storage for it."""
    trace_id = str(uuid4())
    with _lock:
        _traces[trace_id] = []
    return trace_id

def record_prov(event_type: str,
                component: str,
                actor: str,
                inputs: Any,
                outputs: Any,
                confidence: float = 0.0,
                prompt_name: Optional[str] = None,
                session_id: Optional[str] = None,
                trace_id: Optional[str] = None) -> str:
    """Record a provenance trace entry. Returns the trace_id used."""
    if trace_id is None:
        trace_id = new_trace_id(session_id=session_id)
    entry = {
        "timestamp": time.time(),
        "event_type": event_type,
        "component": component,
        "actor": actor,
        "inputs": inputs,
        "outputs": outputs,
        "confidence": float(confidence),
        "prompt_name": prompt_name,
        "session_id": session_id,
        "trace_id": trace_id
    }
    with _lock:
        if trace_id not in _traces:
            _traces[trace_id] = []
        _traces[trace_id].append(entry)
    return trace_id

def get_trace(trace_id: str) -> List[Dict[str, Any]]:
    """Return full trace entries for a trace_id."""
    with _lock:
        return list(_traces.get(trace_id, []))

def clear_trace(trace_id: str) -> None:
    """Remove trace entries for a trace_id."""
    with _lock:
        if trace_id in _traces:
            del _traces[trace_id]

def get_trace_summary(trace_id: str) -> Dict[str, Any]:
    """Return a compact summary (count, first_ts, last_ts)."""
    with _lock:
        entries = _traces.get(trace_id, [])
        if not entries:
            return {"trace_id": trace_id, "count": 0}
        return {
            "trace_id": trace_id,
            "count": len(entries),
            "first_ts": entries[0]["timestamp"],
            "last_ts": entries[-1]["timestamp"],
        }
