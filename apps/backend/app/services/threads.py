from __future__ import annotations
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from uuid import uuid4, UUID

import psycopg
from psycopg.rows import dict_row
try:
    import sentry_sdk 
except ModuleNotFoundError:
    sentry_sdk = None 

from langchain_core.messages import HumanMessage, BaseMessage

from app.agent.system_design.graph import get_compiled_graph_with_checkpointer
from app.storage.memory import add_event, record_node_tokens

logger = logging.getLogger(__name__)

def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


_RUN_SEMAPHORE: asyncio.Semaphore | None = None


def _run_semaphore() -> asyncio.Semaphore:
    global _RUN_SEMAPHORE
    if _RUN_SEMAPHORE is None:
        _RUN_SEMAPHORE = asyncio.Semaphore(_get_int_env("RUN_CONCURRENCY_LIMIT", 1))
    return _RUN_SEMAPHORE

def _pg_url() -> str:
    url = os.getenv("LANGGRAPH_PG_URL")
    if not url:
        raise RuntimeError("LANGGRAPH_PG_URL not configured")
    return url


def _run_select(query: str, params: tuple = ()) -> list[dict]:
    with psycopg.connect(_pg_url(), autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _run_execute(query: str, params: tuple = ()) -> None:
    with psycopg.connect(_pg_url(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)


def _serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return state
    
    result = {}
    for key, value in state.items():
        if key == "messages" and isinstance(value, list):
            result[key] = [
                {"role": getattr(msg, "type", "unknown"), "content": getattr(msg, "content", str(msg))}
                if isinstance(msg, BaseMessage)
                else msg
                for msg in value
            ]
        elif key == "stream_messages" and isinstance(value, list):
            result[key] = [
                {"role": getattr(msg, "type", "unknown"), "content": getattr(msg, "content", str(msg))}
                if isinstance(msg, BaseMessage)
                else msg
                for msg in value
            ]
        elif isinstance(value, dict):
            result[key] = _serialize_state(value)
        else:
            result[key] = value
    return result


def get_thread_data(thread_id: str) -> Optional[Dict[str, Any]]:
    rows = _run_select(
        "select thread_id, user_id, current_run_id, created_at from threads where thread_id = %s",
        (thread_id,),
    )
    if not rows:
        return None
    return rows[0]


def get_run(thread_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    rows = _run_select(
        """
        select run_id, thread_id, status, final_state, user_input, created_at, updated_at
        from runs
        where thread_id = %s and run_id = %s
        """,
        (thread_id, run_id),
    )
    if not rows:
        return None
    return rows[0]


def create_thread(user_id: Optional[str] = None) -> str:
    thread_id = str(uuid4())
    _run_execute(
        "insert into threads(thread_id, user_id, current_run_id) values (%s, %s, null) on conflict (thread_id) do nothing",
        (thread_id, user_id),
    )
    return thread_id


def _enforce_daily_run_limit(user_id: Optional[str]) -> None:
    limit = _get_int_env("RUN_DAILY_LIMIT", 3)
    if limit <= 0:
        return
    if not user_id:
        return
    try:
        uid = UUID(str(user_id))
    except Exception:
        # If user_id isn't a UUID, skip enforcement rather than breaking runs.
        return

    now = datetime.now(timezone.utc)
    period_month = now.strftime("%Y-%m")
    today = now.strftime("%Y-%m-%d")

    row = _run_select(
        "select runs_day, runs_used_day from usage_counters where user_id = %s and period_month = %s",
        (uid, period_month),
    )
    runs_day = row[0].get("runs_day") if row else None
    runs_used_day = int(row[0].get("runs_used_day") or 0) if row else 0

    if runs_day != today:
        runs_used_day = 0
        if row:
            _run_execute(
                "update usage_counters set runs_day = %s, runs_used_day = 0, updated_at = now() where user_id = %s and period_month = %s",
                (today, uid, period_month),
            )

    if runs_used_day >= limit:
        raise RuntimeError(f"Daily run limit reached ({limit}/day). Try again tomorrow.")

    if row:
        _run_execute(
            "update usage_counters set runs_used_day = runs_used_day + 1, updated_at = now() where user_id = %s and period_month = %s",
            (uid, period_month),
        )
    else:
        _run_execute(
            "insert into usage_counters(user_id, period_month, runs_day, runs_used_day) values (%s, %s, %s, 1)",
            (uid, period_month, today),
        )


def start_run(thread_id: str, user_input: str, user_id: Optional[str] = None) -> str:
    _enforce_daily_run_limit(user_id)

    # Ensure thread exists
    if not get_thread_data(thread_id):
        create_thread(user_id)

    run_id = str(uuid4())
    _run_execute(
        """
        insert into runs(run_id, thread_id, user_id, status, user_input)
        values (%s, %s, %s, 'queued', %s)
        """,
        (run_id, thread_id, user_id, user_input),
    )
    _run_execute(
        "update threads set current_run_id = %s where thread_id = %s",
        (run_id, thread_id),
    )
    return run_id


async def execute_run(
    thread_id: str,
    run_id: str,
    user_input: str,
    user_id: Optional[str] = None,
    ws_queue: Optional[asyncio.Queue] = None,
) -> Dict[str, Any]:
    print(f"[EXEC] execute_run called for thread {thread_id}, run {run_id}", flush=True)
    sem = _run_semaphore()
    timeout_s = _get_int_env("RUN_TIMEOUT_SECONDS", 420)

    try:
        async with sem:
            if timeout_s > 0:
                async with asyncio.timeout(timeout_s):
                    return await _execute_run_body(thread_id, run_id, user_input, user_id, ws_queue)
            return await _execute_run_body(thread_id, run_id, user_input, user_id, ws_queue)

    except (TimeoutError, asyncio.TimeoutError) as exc:
        msg = f"Run timed out after {timeout_s}s"
        logger.exception(msg)

        # Mark failed for polling clients
        _run_execute(
            "update runs set status = 'failed', updated_at = now() where run_id = %s",
            (run_id,),
        )

        if ws_queue:
            await ws_queue.put({"type": "error", "error": msg, "run_id": run_id})

        if sentry_sdk is not None:
            try:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("thread_id", thread_id)
                    scope.set_tag("run_id", run_id)
                    if user_id:
                        scope.set_user({"id": str(user_id)})
                    sentry_sdk.capture_exception(exc)
            except Exception:
                pass

        raise RuntimeError(msg) from exc

    except Exception as exc:
        print(f"[EXEC] Run execution failed: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        logger.exception(f"Run execution failed: {exc}")

        # Report to Sentry with useful correlation tags (safe: no PII by default).
        # Never let observability break the run failure path.
        if sentry_sdk is not None:
            try:
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("thread_id", thread_id)
                    scope.set_tag("run_id", run_id)
                    if user_id:
                        scope.set_user({"id": str(user_id)})
                    sentry_sdk.capture_exception(exc)
            except Exception:
                pass

        _run_execute(
            "update runs set status = 'failed', updated_at = now() where run_id = %s",
            (run_id,),
        )
        
        if ws_queue:
            await ws_queue.put({
                "type": "error",
                "error": str(exc),
                "run_id": run_id,
            })
        
        raise
        
async def _execute_run_body(
    thread_id: str,
    run_id: str,
    user_input: str,
    user_id: Optional[str],
    ws_queue: Optional[asyncio.Queue],
) -> Dict[str, Any]:
    print(f"[EXEC] Loading compiled graph with checkpointer...", flush=True)
    compiled_graph = await get_compiled_graph_with_checkpointer()
    print(f"[EXEC] Graph loaded successfully", flush=True)

    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "metadata": {
            "user_id": user_id,
            "thread_id": thread_id,
            "run_id": run_id,
        },
        "recursion_limit": 100,
    }

    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "goal": user_input,
        "metadata": {
            "user_id": user_id,
            "thread_id": thread_id,
            "run_id": run_id,
        },
    }
    _run_execute(
        "update runs set status = 'running', updated_at = now() where run_id = %s",
        (run_id,),
    )

    print(f"[EXEC] Starting graph execution with astream_events...", flush=True)
    try:
        async for event in compiled_graph.astream_events(
            initial_state,
            version="v2",
            config=config,
        ):
            event_type = event.get("event")
            event_name = event.get("name")

            if ws_queue and event_type == "on_chain_stream":
                # Stream message deltas
                data = event.get("data", {})
                if "chunk" in data:
                    chunk = data["chunk"]
                    if isinstance(chunk, dict) and "messages" in chunk:
                        for msg in chunk["messages"]:
                            if hasattr(msg, "content"):
                                await ws_queue.put({
                                    "type": "message-delta",
                                    "content": msg.content,
                                    "run_id": run_id,
                                })
    except Exception as stream_exc:
        print(f"[EXEC] astream_events failed: {stream_exc}", flush=True)
        import traceback
        traceback.print_exc()
        logger.warning(f"astream_events failed: {stream_exc}")

    print(f"[EXEC] Getting final state from checkpointer...", flush=True)
    final_state = await compiled_graph.aget_state(config)
    if final_state and hasattr(final_state, 'values'):
        final_state = final_state.values
        print(
            f\"[EXEC] Got final state with keys: {list(final_state.keys()) if isinstance(final_state, dict) else 'not a dict'}\",
            flush=True,
        )
    else:
        print(f"[EXEC] aget_state returned no values, falling back to ainvoke...", flush=True)
        final_state = await compiled_graph.ainvoke(initial_state, config=config)

    # Extract final output
    output = None
    values = {}

    if isinstance(final_state, dict):
        values = final_state

        # Log what we have in the state for debugging
        state_output = final_state.get("output")
        print(
            f\"[EXEC] final_state.output type: {type(state_output)}, value preview: {str(state_output)[:200] if state_output else 'None'}...\",
            flush=True,
        )

        output = final_state.get("output")
        if isinstance(output, str) and output.strip():
            print(f"[EXEC] Using output from state: {len(output)} chars", flush=True)
        else:
            design_state = final_state.get("design_state", {})
            design_output = design_state.get("output", {})
            if isinstance(design_output, dict):
                formatted = design_output.get("formatted_output")
                if isinstance(formatted, str) and formatted.strip():
                    output = formatted
                    print(f"[EXEC] Using design_state.output.formatted_output: {len(output)} chars", flush=True)
            if not output:
                messages = final_state.get("messages", [])
                if messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, "content"):
                        output = str(last_msg.content)
                        print(f"[EXEC] Using last message content: {len(output)} chars", flush=True)
                    elif isinstance(last_msg, dict) and "content" in last_msg:
                        output = str(last_msg["content"])
                        print(f"[EXEC] Using last message dict content: {len(output)} chars", flush=True)

    serialized_values = _serialize_state(values)

    _run_execute(
        """
        update runs
        set status = 'completed',
            final_state = %s,
            updated_at = now()
        where run_id = %s
        """,
        (json.dumps(serialized_values), run_id),
    )
    _run_execute(
        "update threads set current_run_id = %s where thread_id = %s",
        (run_id, thread_id),
    )
    if ws_queue:
        await ws_queue.put({
            "type": "values-updated",
            "values": serialized_values,
            "output": output,
            "run_id": run_id,
        })

        await ws_queue.put({
            "type": "run-completed",
            "run_id": run_id,
            "thread_id": thread_id,
            "status": "completed",
        })

    return {
        "status": "completed",
        "values": values,
        "output": output,
    }


def get_thread_state(thread_id: str) -> Optional[Dict[str, Any]]:
    runs = _run_select(
        """
        select run_id, status, final_state
        from runs
        where thread_id = %s
        order by created_at desc
        limit 1
        """,
        (thread_id,),
    )
    if not runs:
        return None

    row = runs[0]
    final_state = row.get("final_state")
    if isinstance(final_state, str):
        try:
            final_state = json.loads(final_state)
        except Exception:
            final_state = {}
    if final_state is None:
        final_state = {}

    output = None
    if isinstance(final_state, dict):
        output = final_state.get("output")
        if not output:
            design_state = final_state.get("design_state", {})
            design_output = design_state.get("output", {})
            if isinstance(design_output, dict):
                output = design_output.get("formatted_output")
        if not output and final_state.get("messages"):
            messages = final_state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    output = str(last_msg.content)
                elif isinstance(last_msg, dict) and "content" in last_msg:
                    output = str(last_msg["content"])

    return {
        "thread_id": thread_id,
        "run_id": str(row.get("run_id")) if row.get("run_id") is not None else "",
        "status": row.get("status", "queued"),
        "values": final_state,
        "output": output,
    }


def list_user_threads(user_id: str) -> list[Dict[str, Any]]:
    rows = _run_select(
        """
        SELECT DISTINCT ON (t.thread_id)
            t.thread_id,
            t.created_at,
            r.user_input,
            r.status
        FROM threads t
        LEFT JOIN runs r ON r.thread_id = t.thread_id
        WHERE t.user_id = %s
        ORDER BY t.thread_id, r.created_at DESC
        """,
        (user_id,),
    )
    sorted_rows = sorted(rows, key=lambda x: x.get("created_at") or "", reverse=True)
    
    result = []
    for row in sorted_rows:
        thread_id = row.get("thread_id")
        user_input = row.get("user_input") or ""
        title = user_input.split("\n")[0][:50]
        if len(user_input) > 50 or "\n" in user_input:
            title += "..."
        
        result.append({
            "thread_id": str(thread_id) if thread_id is not None else "",
            "title": title if title else "Untitled",
            "status": row.get("status") or "queued",
            "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
        })
    
    return result
