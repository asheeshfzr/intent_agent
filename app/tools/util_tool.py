import sqlite3
import math
from typing import Any, Dict, List, Optional, Union
from ..config import settings as cfg


def run_sql(query: str, params: Optional[Union[List[Any], Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Executes a SQL query on a local SQLite database.
    Used for local mocking of database calls inside the orchestration flow.
    """

    db_path = getattr(cfg, "local_db_path", "local_agent.db")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params or [])
        rows = cursor.fetchall()
        conn.commit()
        conn.close()

        # Convert to list of dicts
        return [dict(row) for row in rows]
    except Exception as e:
        # In local/mock mode, we just return a safe placeholder
        return [{"query": query, "error": str(e)}]


def calc(a: float, b: float, op: str = "+") -> float:
    """
    Performs a basic arithmetic or mathematical operation.
    Acts as a utility calculator for orchestrator logic (e.g., scoring, metrics normalization).
    """
    try:
        if op == "+":
            return a + b
        elif op == "-":
            return a - b
        elif op == "*":
            return a * b
        elif op == "/":
            return a / b if b != 0 else float("inf")
        elif op == "^":
            return math.pow(a, b)
        elif op == "sqrt":
            return math.sqrt(a)
        elif op == "log":
            return math.log(a, b if b > 0 else math.e)
        else:
            raise ValueError(f"Unsupported operation: {op}")
    except Exception as e:
        print(f"[util_tool.calc] Error: {e}")
        return float("nan")
