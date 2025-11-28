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
from langchain_openai import OpenAIEmbeddings
from langgraph.store.postgres import PostgresStore

logger = logging.getLogger(__name__)

_STORE_STACK = ExitStack()
atexit.register(_STORE_STACK.close)

_MAX_HISTORY = int(os.getenv("LANGGRAPH_STORE_MAX_MESSAGES", "40"))
_NAMESPACE_ROOT = ("system_design_agent",)
_SEMANTIC_SEARCH_LIMIT = int(os.getenv("LANGGRAPH_STORE_SEMANTIC_LIMIT", "10"))


def _connection_url() -> str:
    conn = os.getenv("LANGGRAPH_PG_URL")
    if not conn:
        raise RuntimeError("LANGGRAPH_PG_URL not configured")
    return conn


@lru_cache(maxsize=1)
def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model="text-embedding-3-small")


@lru_cache(maxsize=1)
def _get_store() -> PostgresStore:
    conn = _connection_url()
    host = urlparse(conn).hostname or "unknown"
    logger.info("Initialising LangGraph Store with embeddings", extra={"host": host})
    try:
        embeddings = _get_embeddings()
        index_config = {
            "dims": 1536,
            "embed": embeddings,
            "fields": ["content"],
        }
        store = _STORE_STACK.enter_context(
            PostgresStore.from_conn_string(conn, index=index_config)
        )
        store.setup()
        logger.info("LangGraph Store ready with semantic search", extra={"host": host})
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


def search_semantic_memory(
    *,
    user_id: Optional[str],
    query: str,
    limit: int = 10,
) -> list[BaseMessage]:
    if not query or not query.strip():
        return []
    
    try:
        store = _get_store()
    except Exception as exc:
        logger.warning("LangGraph Store unavailable, skipping semantic search: %s", exc)
        return []
    
    ns = _namespace(user_id)
    try:
        # Search for semantically similar messages
        results = store.search(
            ns,
            query=query.strip(),
            limit=min(limit, _SEMANTIC_SEARCH_LIMIT),
        )
        
        messages: list[BaseMessage] = []
        seen_keys: set[tuple[str, ...]] = set()
        
        for item in results:
            key = (item.namespace, item.key)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            value = item.value
            if isinstance(value, dict):
                raw_messages = value.get("messages")
                if isinstance(raw_messages, list):
                    for entry in raw_messages:
                        if isinstance(entry, dict):
                            msg = _entry_to_message(entry)
                            if msg is not None:
                                messages.append(msg)
        
        logger.debug(
            "Semantic search found %d messages for query: %s",
            len(messages),
            query[:50],
        )
        return messages
        
    except Exception as exc:
        logger.warning("Semantic search failed: %s", exc)
        return []


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

    # Create content field for semantic search (concatenate all message contents)
    content_parts: list[str] = []
    for entry in history:
        if isinstance(entry, dict):
            content = entry.get("content", "")
            if content:
                role = entry.get("role", "user")
                content_parts.append(f"{role}: {content}")
    content_text = "\n".join(content_parts)

    payload = {
        "messages": history,
        "content": content_text,  # For semantic search embeddings
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        store.put(ns, key, payload)
    except Exception:
        logger.exception("Failed to write long-term memory", extra={"namespace": ns, "key": key})

