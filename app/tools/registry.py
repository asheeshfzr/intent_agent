from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class ToolSchema(BaseModel):
    name: str
    capabilities: List[str] = Field(default_factory=list)
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 5.0

# Lightweight registry with metadata; in prod, fetch from config or service discovery
REGISTRY: Dict[str, ToolSchema] = {
    "metrics_tool": ToolSchema(
        name="metrics_tool",
        capabilities=["metrics"],
        input_schema={"type": "string", "format": "service=<name>;window=<duration>"},
        output_schema={"type": "object", "properties": {"p95": {"type": "number"}}},
        timeout_seconds=5.0,
    ),
    "vector_tool": ToolSchema(
        name="vector_tool",
        capabilities=["knowledge"],
        input_schema={"type": "string", "format": "raw question"},
        output_schema={"type": "object", "properties": {"top": {"type": "object"}}},
        timeout_seconds=5.0,
    ),
    "util_sql": ToolSchema(
        name="util_sql",
        capabilities=["calc", "sql"],
        input_schema={"type": "string", "format": "SQL SELECT or arithmetic expression"},
        output_schema={"type": "object", "properties": {"rows": {"type": "array"}}},
        timeout_seconds=5.0,
    ),
}

def tools_by_capability(capability: str) -> List[str]:
    out: List[str] = []
    for name, meta in REGISTRY.items():
        if capability in meta.capabilities:
            out.append(name)
    return out
