from __future__ import annotations

import os
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row


def _pg_url() -> str:
    url = os.getenv("LANGGRAPH_PG_URL")
    if not url:
        raise RuntimeError("LANGGRAPH_PG_URL not configured")
    return url


def _select_one(query: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    with psycopg.connect(_pg_url(), autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return row if row else None


def _select_all(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    with psycopg.connect(_pg_url(), autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _execute(query: str, params: tuple = ()) -> None:
    with psycopg.connect(_pg_url(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)


def create_session(*, user_id: str, thread_id: str, original_input: str) -> str:
    row = _select_one(
        """
        insert into clarifier_sessions(user_id, thread_id, status, original_input)
        values (%s, %s, 'active', %s)
        returning id
        """,
        (user_id, thread_id, original_input),
    )
    if not row or not row.get("id"):
        raise RuntimeError("Failed to create clarifier session")
    return str(row["id"])


def get_session(*, session_id: str, user_id: str) -> Optional[dict[str, Any]]:
    return _select_one(
        """
        select id, user_id, thread_id, status, original_input, final_status, final_summary, enriched_prompt,
               missing_fields, assumptions, turn_count, created_at, updated_at
        from clarifier_sessions
        where id = %s and user_id = %s
        """,
        (session_id, user_id),
    )


def update_turn_count(*, session_id: str, user_id: str, delta: int) -> int:
    row = _select_one(
        """
        update clarifier_sessions
        set turn_count = greatest(0, turn_count + %s),
            updated_at = now()
        where id = %s and user_id = %s
        returning turn_count
        """,
        (delta, session_id, user_id),
    )
    if not row or row.get("turn_count") is None:
        raise RuntimeError("Failed to update turn_count")
    return int(row["turn_count"])


def set_session_status(*, session_id: str, user_id: str, status: str) -> None:
    _execute(
        """
        update clarifier_sessions
        set status = %s, updated_at = now()
        where id = %s and user_id = %s
        """,
        (status, session_id, user_id),
    )


def finalize_session(
    *,
    session_id: str,
    user_id: str,
    status: str,
    final_summary: str,
    enriched_prompt: str,
    missing_fields: list[str],
    assumptions: list[str],
) -> None:
    _execute(
        """
        update clarifier_sessions
        set status = 'finalized',
            final_status = %s,
            final_summary = %s,
            enriched_prompt = %s,
            missing_fields = %s::jsonb,
            assumptions = %s::jsonb,
            updated_at = now()
        where id = %s and user_id = %s
        """,
        (status, final_summary, enriched_prompt, missing_fields, assumptions, session_id, user_id),
    )


def append_message(*, session_id: str, user_id: str, role: str, content: str) -> None:
    # Ensure session exists and is owned by user (defense-in-depth)
    sess = get_session(session_id=session_id, user_id=user_id)
    if not sess:
        raise PermissionError("Forbidden")
    _execute(
        """
        insert into clarifier_messages(session_id, role, content)
        values (%s, %s, %s)
        """,
        (session_id, role, content),
    )
    _execute(
        "update clarifier_sessions set updated_at = now() where id = %s",
        (session_id,),
    )


def list_messages(*, session_id: str, user_id: str, limit: int = 200) -> list[dict[str, Any]]:
    sess = get_session(session_id=session_id, user_id=user_id)
    if not sess:
        raise PermissionError("Forbidden")
    return _select_all(
        """
        select role, content, created_at
        from clarifier_messages
        where session_id = %s
        order by created_at asc
        limit %s
        """,
        (session_id, limit),
    )


