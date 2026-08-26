import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


logger = logging.getLogger("finance_agent.tools")
RETRIEVAL_ENDPOINT = os.getenv("RETRIEVAL_ENDPOINT", "http://127.0.0.1:8000/search")

FINANCE_SEARCH_DECLARATION = {
    "name": "finance_search",
    "description": (
        "Search the local Persian finance and cryptocurrency knowledge base for technical "
        "analysis, fundamental analysis, risk management, market concepts, and crypto topics."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "A focused Persian search query describing the financial topic.",
            },
            "k": {
                "type": "integer",
                "description": "Number of matching knowledge-base chunks to retrieve, from 1 to 10.",
            },
        },
        "required": ["query"],
    },
}

def finance_search(query: str, k: int = 5) -> dict:
    k = max(1, min(k, 10))
    payload = json.dumps({"query": query, "k": k}).encode("utf-8")
    request = Request(
        RETRIEVAL_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    logger.info("finance_search_started query_length=%d k=%d", len(query), k)
    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Retrieval endpoint returned HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(
            f"Could not reach retrieval endpoint at {RETRIEVAL_ENDPOINT}: {error.reason}"
        ) from error
    logger.info("finance_search_finished result_count=%d", len(result.get("results", [])))
    return result
