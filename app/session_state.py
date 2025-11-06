"""
Session State Management
------------------------
Tracks per-session memory, especially pending clarifications and
intermediate agent states.
"""

# app/session_state.py
import json
from pathlib import Path
from typing import Dict, Any
from threading import Lock

# Global in-memory session state
_session_memory: Dict[str, Dict[str, Any]] = {}
_lock = Lock()


def get_pending_clarify(session_id: str) -> Any:
    """
    Retrieve pending clarification data for a given session.
    Returns None if nothing is pending.
    """
    with _lock:
        session = _session_memory.get(session_id, {})
        return session.get("pending_clarify")


def set_pending_clarify(session_id: str, clarify_data: Any) -> None:
    """
    Store pending clarification data for a given session.
    """
    with _lock:
        if session_id not in _session_memory:
            _session_memory[session_id] = {}
        _session_memory[session_id]["pending_clarify"] = clarify_data


def clear_pending_clarify(session_id: str) -> None:
    """
    Clear any pending clarification data for a given session.
    """
    with _lock:
        if session_id in _session_memory:
            _session_memory[session_id].pop("pending_clarify", None)
            if not _session_memory[session_id]:
                _session_memory.pop(session_id, None)


def get_session_data(session_id: str) -> Dict[str, Any]:
    """
    Get full session data (useful for debugging).
    """
    with _lock:
        return _session_memory.get(session_id, {}).copy()


def reset_all_sessions() -> None:
    """
    Reset all session states (useful in dev mode).
    """
    with _lock:
        _session_memory.clear()


STATE_FILE = Path("data/session_state.json")
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
if not STATE_FILE.exists():
    STATE_FILE.write_text("{}")

def load_session(session_id: str) -> Dict[str,Any]:
    data = json.loads(STATE_FILE.read_text())
    return data.get(session_id, {})

def save_session(session_id: str, payload: Dict[str,Any]):
    data = json.loads(STATE_FILE.read_text())
    data[session_id] = payload
    STATE_FILE.write_text(json.dumps(data, indent=2))
