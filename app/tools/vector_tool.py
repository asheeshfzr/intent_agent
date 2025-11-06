from typing import Any, Dict, List, Optional
import httpx
import json
from ..config import settings as cfg 


async def call_vector(
    collection_name: str,
    query_vector: List[float],
    limit: int = 5,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Communicates with the Qdrant vector database (or local mock) to perform similarity search.
    This is used by the Orchestrator to retrieve semantically similar items.

    Args:
        collection_name: Name of the Qdrant collection.
        query_vector: The vector embedding to query against.
        limit: Max number of results.
        timeout: Optional timeout for the request.

    Returns:
        JSON-like dictionary with search results or error.
    """

    # Default timeout
    timeout = timeout or settings.HTTP_TIMEOUT_SECONDS

    qdrant_url = f"http://localhost:{settings.qdrant_port}/collections/{collection_name}/points/search"

    payload = {
        "vector": query_vector,
        "limit": limit,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(qdrant_url, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        # Fallback mock (so you can run without Qdrant Docker)
        return {
            "collection_name": collection_name,
            "query_vector": query_vector[:5],
            "limit": limit,
            "status": "mock",
            "message": f"Qdrant not reachable or error: {e}",
            "results": [
                {"id": 1, "score": 0.92, "payload": {"mock": True}},
                {"id": 2, "score": 0.88, "payload": {"mock": True}},
            ],
        }
