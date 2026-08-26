import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path

from google import genai
from google.genai import types

from .tools import FINANCE_SEARCH_DECLARATION, finance_search


logger = logging.getLogger("finance_agent")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEM_PROMPT = (PROJECT_ROOT / "src" / "agent" / "system_prompt.md").read_text(encoding="utf-8")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")


def _contents(history: list[dict[str, str]], query: str) -> list[types.Content]:
    contents = []
    for item in history[-20:]:
        role = "model" if item.get("role") in {"assistant", "model"} else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=item.get("content", ""))]))
    contents.append(types.Content(role="user", parts=[types.Part(text=query)]))
    return contents


def _decision_config() -> types.GenerateContentConfig:
    """Give the first pass access to the local knowledge-base tool."""
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=[FINANCE_SEARCH_DECLARATION])],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _answer_config() -> types.GenerateContentConfig:
    """Generate the final answer from the tool results already gathered by the app."""
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _function_calls(response) -> list:
    return list(getattr(response, "function_calls", None) or [])


def stream_answer(api_key: str, query: str, history: list[dict[str, str]]) -> Iterator[dict]:
    logger.info("stage=gemini_client_initializing model=%s", MODEL)
    client = genai.Client(api_key=api_key)
    contents = _contents(history, query)
    decision_config = _decision_config()

    # First ask Gemini whether the answer needs evidence from the local knowledge base.
    logger.info("stage=gemini_tool_decision_started history_messages=%d", len(history))
    decision = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=decision_config,
    )
    calls = _function_calls(decision)
    logger.info("stage=gemini_tool_decision_finished function_call_count=%d", len(calls))
    if calls:
        contents.append(decision.candidates[0].content)
        for call in calls:
            args = dict(call.args or {})
            if call.name == "finance_search":
                logger.info("stage=finance_search_call_requested query_length=%d", len(args.get("query", query)))
                yield {"type": "tool_start", "tool": "finance_search", "query": args.get("query", query)}
                result = finance_search(args.get("query", query), int(args.get("k", 5)))
                logger.info("stage=finance_search_call_finished")
                yield {
                    "type": "sources",
                    "sources": [
                        {
                            "source": item.get("source", "منبع نامشخص"),
                            "content": item.get("content", ""),
                        }
                        for item in result.get("results", [])
                    ],
                }
            else:
                continue
            yield {"type": "tool_finished", "tool": call.name}
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=getattr(call, "id", None),
                                name=call.name,
                                response={"result": result},
                            )
                        )
                    ],
                )
            )

    # Stream the final answer using the local or current-news evidence gathered above.
    logger.info("stage=gemini_final_response_started used_tool=%s", bool(calls))
    response_stream = client.models.generate_content_stream(
        model=MODEL,
        contents=contents if calls else _contents(history, query),
        config=_answer_config(),
    )
    emitted_text = False
    for chunk in response_stream:
        text = getattr(chunk, "text", None)
        if text:
            emitted_text = True
            yield {"type": "token", "text": text}
    if not emitted_text:
        raise RuntimeError("Gemini did not return a text answer. Please try the request again.")
    logger.info("stage=gemini_final_response_finished")
    yield {"type": "done"}
