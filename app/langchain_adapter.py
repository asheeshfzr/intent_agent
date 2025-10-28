# app/langchain_adapter.py
from typing import Callable, List
from dataclasses import dataclass

@dataclass
class Tool:
    name: str
    func: Callable[[str], str]
    description: str = ""

def run_agent_with_tools(query: str, tools: List[Tool], router_func):
    """
    Small local adapter: call router_func(query) -> parsed,
    then call the appropriate tool based on intent.
    """
    parsed = router_func(query)
    intent = parsed.get("intent", "unknown")
    entities = parsed.get("entities", {})
    result = {"intent": intent, "entities": entities, "tool_results": []}

    if intent == "metrics_lookup":
        t = next((t for t in tools if t.name == "metrics_tool"), None)
        if not t:
            return {"error": "no metrics tool registered"}
        svc = entities.get("service", "payments")
        arg = f"service={svc};window={entities.get('window','5m')}"
        out = t.func(arg)
        result["tool_results"].append({"tool": t.name, "output": out})
        return result

    if intent == "knowledge_lookup":
        t = next((t for t in tools if t.name == "vector_tool"), None)
        if not t:
            return {"error": "no vector tool registered"}
        out = t.func(query)
        result["tool_results"].append({"tool": t.name, "output": out})
        return result

    if intent == "calc_compare":
        t = next((t for t in tools if t.name == "util_sql"), None)
        if not t:
            return {"error": "no util tool registered"}
        out = t.func(query)
        result["tool_results"].append({"tool": t.name, "output": out})
        return result

    # fallback
    return {"intent": intent, "entities": entities}
