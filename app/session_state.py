from typing import Dict, Optional

# naive in-memory session storage for clarifying questions
_pending: Dict[str, str] = {}

def get_pending_clarify(user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    return _pending.get(user_id)

def set_pending_clarify(user_id: Optional[str], question: str) -> None:
    if not user_id:
        return
    _pending[user_id] = question

def clear_pending_clarify(user_id: Optional[str]) -> None:
    if not user_id:
        return
    _pending.pop(user_id, None)
