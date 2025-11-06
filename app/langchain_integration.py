"""
LangChain Integration Layer
---------------------------
Provides compatibility utilities to construct LangChain-style tools
and run simple reasoning chains using the local LLM or external APIs.
"""

from typing import Any, Callable, Dict, List
from .llm_local import LocalLLM


class LocalLangChain:
    """
    Lightweight LangChain-style wrapper around the local LLM engine.
    Useful for tool orchestration and reasoning tasks inside workflows.
    """

    def __init__(self, model_path: str | None = None):
        self.llm = LocalLLM(model_path=model_path)
        print("[LocalLangChain] Initialized LangChain-like wrapper")

    def run(self, prompt: str, context: Dict[str, Any] | None = None) -> str:
        """
        Execute a reasoning-style chain by sending a formatted prompt to the LLM.
        """
        context_str = (
            "\nContext:\n" + "\n".join(f"{k}: {v}" for k, v in context.items())
            if context else ""
        )
        query = f"{prompt}{context_str}\nAnswer:"
        response = self.llm.generate(query)
        return response


def make_langchain_tools(tools: Dict[str, Callable[..., Any]]) -> List[Dict[str, Any]]:
    """
    Builds a mock LangChain-style list of tools for use in workflow orchestration.

    Args:
        tools: Dictionary of tool_name → function.

    Returns:
        A LangChain-like tool list where each tool is represented as a callable object.
    """
    wrapped_tools = []

    for name, func in tools.items():
        wrapped_tools.append({
            "name": name,
            "description": func.__doc__ or f"Tool: {name}",
            "run": func
        })

    print(f"[LocalLangChain] Registered {len(wrapped_tools)} tools.")
    return wrapped_tools
