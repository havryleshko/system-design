from __future__ import annotations
from functools import lru_cache
import os
from typing import Any, Optional, Type, TypeVar
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel
try:
    from langchain_openai import ChatOpenAI
except Exception: 
    ChatOpenAI = None  

T = TypeVar("T", bound=BaseModel)


def _to_message(x: Any) -> BaseMessage:
    if isinstance(x, BaseMessage):
        return x
    if isinstance(x, str):
        return HumanMessage(content=x)
    if isinstance(x, dict):
        role = (x.get("role") or "user").lower()
        content = x.get("content", "")
        if role == "system":
            return SystemMessage(content=str(content))
        if role in ("assistant", "ai"):
            return AIMessage(content=str(content))
        return HumanMessage(content=str(content))
    return HumanMessage(content=str(x))


def normalize_messages(messages: list[Any]) -> list[BaseMessage]:
    return [_to_message(m) for m in (messages or [])]


@lru_cache(maxsize=4)
def make_llm(model: str | None = None) -> "ChatOpenAI":
    if ChatOpenAI is None:
        raise RuntimeError("langchain-openai is not installed. Install backend requirements.")
    model_name = model or os.getenv("CHAT_OPENAI_MODEL", "gpt-4o-mini")
    max_out = int(os.getenv("CHAT_OPENAI_MAX_OUTPUT_TOKENS", "4000"))
    temperature = float(os.getenv("CHAT_OPENAI_TEMPERATURE", "0.2"))
    return ChatOpenAI(model=model_name, max_tokens=max_out, temperature=temperature)


def call_llm_structured(
    messages: list[Any],
    schema: Type[T],
    *,
    retries: int = 2,
    model: str | None = None,
) -> T:
    ms = normalize_messages(messages)
    last_exc: Optional[Exception] = None
    for attempt in range(max(1, retries + 1)):
        try:
            llm = make_llm(model=model)
            raw_msg = None
            try:
                runnable = llm.with_structured_output(schema, include_raw=True)
                out = runnable.invoke(ms)
                raw_msg = out.get("raw")
                parsed = out.get("parsed")
                parsing_error = out.get("parsing_error")
                if parsing_error:
                    raise parsing_error
            except TypeError:
                # Older langchain versions may not support include_raw
                runnable = llm.with_structured_output(schema)
                parsed = runnable.invoke(ms)

            if not isinstance(parsed, schema):
                parsed = schema.model_validate(parsed)

            # Best-effort: if the model returned additional chatter in raw, we ignore it
            _ = raw_msg
            return parsed
        except Exception as exc:
            last_exc = exc
            if attempt < max(1, retries + 1) - 1:
                # Repair retry: explicitly nudge the model to comply
                ms = ms + [
                    SystemMessage(
                        content=(
                            "Your last response did not match the required schema.\n"
                            "Return ONLY a valid structured output for the schema. Do not add extra keys.\n"
                            f"Validation/parsing error: {str(exc)[:900]}"
                        )
                    )
                ]
                continue
            raise

    raise last_exc or RuntimeError("call_llm_structured failed")

