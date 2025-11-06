# app/tools/registry.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum

class ToolCapability(str, Enum):
    METRICS = "metrics"
    VECTOR = "vector"
    SQL = "sql"
    HTTP = "http"
    UTIL = "util"

class ToolMeta(BaseModel):
    key: str
    name: str
    capabilities: List[ToolCapability]
    timeout_seconds: int = 5
    retries: int = 1
    description: Optional[str] = None
    request_schema: Optional[dict] = None
    response_schema: Optional[dict] = None

DEFAULT_TOOL_REGISTRY: Dict[str, ToolMeta] = {
    "metrics_tool": ToolMeta(
        key="metrics_tool",
        name="metrics_tool",
        capabilities=[ToolCapability.METRICS, ToolCapability.HTTP],
        timeout_seconds=6,
        retries=2,
        description="Fetch metrics from metrics mock API"
    ),
    "vector_tool": ToolMeta(
        key="vector_tool",
        name="vector_tool",
        capabilities=[ToolCapability.VECTOR],
        timeout_seconds=8,
        retries=1,
        description="Search documents / vector DB"
    ),
    "util_sql": ToolMeta(
        key="util_sql",
        name="util_sql",
        capabilities=[ToolCapability.SQL, ToolCapability.UTIL],
        timeout_seconds=3,
        retries=0,
        description="Local sqlite utility tool"
    )
}

def get_tools_by_capability(capability: ToolCapability):
    return [m for m in DEFAULT_TOOL_REGISTRY.values() if capability in m.capabilities]
