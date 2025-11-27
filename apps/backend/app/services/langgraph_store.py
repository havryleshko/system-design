from __future__ import annotations

import atexit
import json
import logging
import os
from contextlib import ExitStack
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional
from urllib.parse import urlparse

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.store.postgres import PostgresStore

logger = logging.getLogger(__name__)

_STORE_STACK = ExitStack()
atexit.register(_STORE_STACK.close)

_MAX_HISTORY = int(os.getenv("LANGGRAPH_STORE_MAX_MESSAGES", "40"))
_NAMESPACE_ROOT = ("system_design_agent",)


def _connection_url() -> str:
    conn = os.getenv("LANGGRAPH_PG_URL")
    if not conn:
        raise RuntimeError("LANGGRAPH_PG_URL not configured")
    return conn


@lru_cache(maxsize=1)
def _get_store() -> PostgresStore:
    conn = _connection_url()
    host = urlparse(conn).hostname or "unknown"
    logger.info("Initialising LangGraph Store", extra={"host": host})
    try:
        store = _STORE_STACK.enter_context(PostgresStore.from_conn_string(conn))
        store.setup()
        logger.info("LangGraph Store ready", extra={"host": host})
        return store
    except Exception as e:
        logger.exception(f"Failed to initialise LangGraph Store, {e}", extra={"host": host})
        raise


def _namespace(user_id: Optional[str]) -> tuple[str, ...]:
    if user_id:
        return _NAMESPACE_ROOT + (user_id,)
    return _NAMESPACE_ROOT + ("anonymous",)


def _memory_key(process_id: Optional[str]) -> Optional[str]:
    if not process_id:
        return None
    return process_id


def _coerce_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value or "")


def _entry_to_message(entry: dict[str, Any]) -> BaseMessage | None:
    content = entry.get("content")
    if not content:
        return None
    role = (entry.get("role") or "user").lower()
    if role == "assistant":
        return AIMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    return HumanMessage(content=content)


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, AIMessage):
        return "assistant"
    if isinstance(message, SystemMessage):
        return "system"
    return "user"


def _message_to_entry(
    message: BaseMessage,
    *,
    node: Optional[str],
    run_id: Optional[str],
) -> dict[str, Any]:
    return {
        "role": _message_role(message),
        "content": _coerce_content(getattr(message, "content", "")),
        "ts": datetime.now(timezone.utc).isoformat(),
        "node": node,
        "run_id": run_id,
    }


def load_long_term_messages(
    *,
    user_id: Optional[str],
    process_id: Optional[str],
    limit: int = 12,
) -> list[BaseMessage]:
    key = _memory_key(process_id)
    if key is None:
        return []
    try:
        store = _get_store()
    except Exception as exc:
        logger.warning("LangGraph Store unavailable, skipping load: %s", exc)
        return []

    item = store.get(_namespace(user_id), key)
    if not item:
        return []
    raw_messages = item.value.get("messages")
    if not isinstance(raw_messages, list):
        return []
    trimmed = raw_messages[-limit:] if limit > 0 else raw_messages
    history: list[BaseMessage] = []
    for entry in trimmed:
        if isinstance(entry, dict):
            msg = _entry_to_message(entry)
            if msg is not None:
                history.append(msg)
    return history


def record_long_term_memory(
    *,
    user_id: Optional[str],
    process_id: Optional[str],
    prompt: Optional[BaseMessage],
    response: Optional[BaseMessage],
    run_id: Optional[str],
    node: Optional[str],
) -> None:
    key = _memory_key(process_id)
    if key is None:
        return
    if prompt is None and response is None:
        return
    try:
        store = _get_store()
    except Exception as exc:
        logger.warning("LangGraph Store unavailable, skipping write: %s", exc)
        return

    ns = _namespace(user_id)
    history: list[dict[str, Any]] = []
    existing = store.get(ns, key)
    if existing:
        raw = existing.value.get("messages")
        if isinstance(raw, list):
            history = list(raw)

    if prompt is not None:
        history.append(_message_to_entry(prompt, node=node, run_id=run_id))
    if response is not None:
        history.append(_message_to_entry(response, node=node, run_id=run_id))

    if _MAX_HISTORY > 0 and len(history) > _MAX_HISTORY:
        history = history[-_MAX_HISTORY:]

    payload = {
        "messages": history,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        store.put(ns, key, payload)
    except Exception:
        logger.exception("Failed to write long-term memory", extra={"namespace": ns, "key": key})

