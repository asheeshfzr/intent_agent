from pydantic import BaseModel
from typing import Any, Dict
import time
class MCPInput(BaseModel):
    tool: str
    params: Dict[str, Any] = {}
    meta: Dict[str, Any] = {}
class MCPOutput(BaseModel):
    tool: str
    success: bool
    data: Dict[str, Any] = {}
    score: float = 0.0
    reason: str = ''
    ts: float = time.time()
