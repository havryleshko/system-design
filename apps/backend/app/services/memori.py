from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Optional
from memori import Memori
import logging

logger = logging.getLogger(__name__)

def _connection_url() -> str:
    conn = os.getenv("LANGGRAPH_PG_URL")
    return conn


@lru_cache(maxsize=1)
def get_memori() -> Memori:
    conn = _connection_url()
    logger.info("Initialising Memori long-term memory backend")
    return Memori(conn=conn)


def prepare_memori_for_langchain(
    llm: Any,
    *,
    user_id: Optional[str],
    process_id: Optional[str],
) -> None:
    try:
        memori = get_memori()
    except RuntimeError as exc:
        logger.warning("[memori] disabled: %s", exc)
        return

    memori.attribution(entity_id=user_id, process_id=process_id)
    try:
        memori.langchain.register(chatopenai=llm)
    except Exception as exc: 
        logger.warning("[memori] failed to register LangChain client: %s", exc)

