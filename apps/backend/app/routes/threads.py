import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header, status

from app.schemas.threads import (
    ThreadCreate,
    ThreadResponse,
    RunStartRequest,
    RunStartResponse,
    ThreadStateResponse,
    ThreadListResponse,
    ThreadListItem,
)
from app.services import threads as thread_service
from app.auth import decode_token

logger = logging.getLogger(__name__)

threads_router = APIRouter(prefix="/threads", tags=["threads"])

_DEBUG_LOGS = os.getenv("DEBUG_LOGS", "").lower() in ("1", "true", "yes", "on")


async def get_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_token(token)
        return claims.get("sub")
    except Exception:
        return None


@threads_router.get("", response_model=ThreadListResponse)
async def list_threads(user_id: Optional[str] = Depends(get_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    threads = thread_service.list_user_threads(user_id)
    return ThreadListResponse(threads=[ThreadListItem(**t) for t in threads])


@threads_router.post("", status_code=status.HTTP_201_CREATED, response_model=ThreadResponse)
async def create_thread(user_id: Optional[str] = Depends(get_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    thread_id = thread_service.create_thread(user_id)
    return ThreadResponse(thread_id=thread_id)


@threads_router.post("/{thread_id}/runs", status_code=status.HTTP_201_CREATED, response_model=RunStartResponse)
async def start_run(
    thread_id: str,
    payload: RunStartRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    thread = thread_service.get_thread_data(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    owner = thread.get("user_id")
    if not owner or str(owner) != str(user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        run_id = thread_service.start_run(
            thread_id,
            payload.input,
            user_id,
            clarifier_session_id=payload.clarifier_session_id,
            clarifier_summary=payload.clarifier_summary,
        )
    except RuntimeError as exc:
        # Map quota limits to a proper status code instead of 500.
        msg = str(exc)
        if "Daily run limit reached" in msg:
            raise HTTPException(status_code=429, detail=msg)
        raise HTTPException(status_code=500, detail="Failed to start run")
    except PermissionError:
        raise HTTPException(status_code=401, detail="Authentication required")
    except LookupError:
        raise HTTPException(status_code=404, detail="Thread not found")
    return RunStartResponse(run_id=run_id, thread_id=thread_id)


@threads_router.get("/{thread_id}/state", response_model=ThreadStateResponse)
async def get_thread_state(thread_id: str, user_id: Optional[str] = Depends(get_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        state = thread_service.get_thread_state_for_user(thread_id, user_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not state:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return ThreadStateResponse(**state)


@threads_router.websocket("/{thread_id}/stream")
async def stream_thread(websocket: WebSocket, thread_id: str):
    import traceback
    # Authenticate WS using Sec-WebSocket-Protocol if provided (preferred), else fall back.
    offered = websocket.headers.get("sec-websocket-protocol") or ""
    offered_parts = [p.strip() for p in offered.split(",") if p.strip()]
    token: str | None = None
    accept_subprotocol: str | None = None

    # Expected client format: new WebSocket(url, ["bearer", token])
    try:
        for i, part in enumerate(offered_parts):
            if part.lower() == "bearer" and i + 1 < len(offered_parts):
                token = offered_parts[i + 1]
                accept_subprotocol = "bearer"
                break
    except Exception:
        token = None
        accept_subprotocol = None

    # Back-compat fallbacks: query param token, then Authorization header.
    query_params = dict(websocket.query_params)
    if not token:
        token = query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if accept_subprotocol:
        await websocket.accept(subprotocol=accept_subprotocol)
    else:
        await websocket.accept()

    if _DEBUG_LOGS:
        logger.debug("[WS] accepted websocket", extra={"thread_id": thread_id})

    run_id = query_params.get("run_id")
    
    if not token:
        if _DEBUG_LOGS:
            logger.debug("[WS] missing token", extra={"thread_id": thread_id})
        await websocket.close(code=1008, reason="Missing authorization token")
        return
    
    if not run_id:
        if _DEBUG_LOGS:
            logger.debug("[WS] missing run_id", extra={"thread_id": thread_id})
        await websocket.close(code=1008, reason="Missing run_id")
        return
    
    try:
        claims = decode_token(token)
        user_id = claims.get("sub")
        if _DEBUG_LOGS:
            logger.debug("[WS] token decoded", extra={"thread_id": thread_id})
    except Exception as exc:
        logger.info("[WS] token decode failed", extra={"thread_id": thread_id})
        await websocket.close(code=1008, reason=f"Invalid token: {exc}")
        return

    # Authorization hardening: enforce thread ownership
    thread = thread_service.get_thread_data(thread_id) or {}
    owner = thread.get("user_id")
    if not owner or not user_id or str(owner) != str(user_id):
        logger.info("[WS] forbidden: thread owner mismatch", extra={"thread_id": thread_id})
        await websocket.close(code=1008, reason="Forbidden")
        return
    
    # Verify thread exists
    state = thread_service.get_thread_state(thread_id)
    if not state:
        logger.info("[WS] thread not found", extra={"thread_id": thread_id})
        await websocket.close(code=1008, reason="Thread not found")
        return
    
    # Get run data
    run_data = thread_service.get_run(thread_id, run_id)
    if not run_data:
        logger.info("[WS] run not found", extra={"thread_id": thread_id, "run_id": run_id})
        await websocket.send_json({
            "type": "error",
            "error": "Run not found",
        })
        await websocket.close(code=1008, reason="Run not found")
        return

    # Authorization hardening: enforce run ownership (defense-in-depth)
    run_owner = run_data.get("user_id")
    if not run_owner or not user_id or str(run_owner) != str(user_id):
        logger.info("[WS] forbidden: run owner mismatch", extra={"thread_id": thread_id, "run_id": run_id})
        await websocket.close(code=1008, reason="Forbidden")
        return
    
    run_status = run_data.get("status", "queued")
    user_input = run_data.get("user_input", "")
    if _DEBUG_LOGS:
        logger.debug("[WS] run status", extra={"thread_id": thread_id, "run_id": run_id, "status": run_status})
    
    # If run is already completed or failed, send final state immediately
    if run_status in ("completed", "failed"):
        final_state = run_data.get("final_state", {})
        if isinstance(final_state, str):
            try:
                final_state = json.loads(final_state)
            except Exception:
                final_state = {}
        output = None
        if isinstance(final_state, dict):
            output = final_state.get("output")
            if not output:
                design_state = final_state.get("design_state", {})
                design_output = design_state.get("output", {}) if isinstance(design_state, dict) else {}
                if isinstance(design_output, dict):
                    output = design_output.get("formatted_output")
            if not output:
                messages = final_state.get("messages", [])
                if isinstance(messages, list) and messages:
                    last_msg = messages[-1]
                    if hasattr(last_msg, "content"):
                        output = str(last_msg.content)
                    elif isinstance(last_msg, dict) and "content" in last_msg:
                        output = str(last_msg["content"])
        
        await websocket.send_json({
            "type": "values-updated",
            "values": final_state,
            "output": output,
            "run_id": run_id,
        })
        await websocket.send_json({
            "type": "run-completed",
            "run_id": run_id,
            "thread_id": thread_id,
            "status": run_status,
        })
        await websocket.close()
        return
    
    # If run is already running, don't start another execution - just wait for completion
    if run_status == "running":
        if _DEBUG_LOGS:
            logger.debug("[WS] run already running: polling", extra={"thread_id": thread_id, "run_id": run_id})
        # Poll for completion instead of starting new execution
        while True:
            await asyncio.sleep(2)
            thread_data = thread_service.get_thread_data(thread_id) or {}
            for run in thread_data.get("runs", []):
                if run["run_id"] == run_id:
                    current_status = run.get("status", "queued")
                    if current_status in ("completed", "failed"):
                        final_state = run.get("final_state", {})
                        output = None
                        if isinstance(final_state, dict):
                            output = final_state.get("output")
                            if not output:
                                design_state = final_state.get("design_state", {})
                                design_output = design_state.get("output", {}) if isinstance(design_state, dict) else {}
                                if isinstance(design_output, dict):
                                    output = design_output.get("formatted_output")
                        await websocket.send_json({
                            "type": "values-updated",
                            "values": final_state,
                            "output": output,
                            "run_id": run_id,
                        })
                        await websocket.send_json({
                            "type": "run-completed",
                            "run_id": run_id,
                            "thread_id": thread_id,
                            "status": current_status,
                        })
                        await websocket.close()
                        return
                    break
            # Send ping to keep connection alive
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                return
    
    if not user_input:
        logger.info("[WS] run missing input", extra={"thread_id": thread_id, "run_id": run_id})
        await websocket.send_json({
            "type": "error",
            "error": "Run missing input",
        })
        await websocket.close(code=1008, reason="Run missing input")
        return
    
    # Create event queue for streaming
    event_queue = asyncio.Queue()
    
    # Start run execution in background
    execution_task = None
    try:
        # Start execution
        if _DEBUG_LOGS:
            logger.debug("[WS] starting execution task", extra={"thread_id": thread_id, "run_id": run_id})
        metadata_extra: dict[str, str] = {}
        if isinstance(run_data, dict):
            if run_data.get("clarifier_session_id"):
                metadata_extra["clarifier_session_id"] = str(run_data.get("clarifier_session_id"))
            if run_data.get("clarifier_summary"):
                metadata_extra["clarifier_summary"] = str(run_data.get("clarifier_summary"))
        execution_task = asyncio.create_task(
            thread_service.execute_run(thread_id, run_id, user_input, user_id, event_queue, metadata_extra)
        )
        if _DEBUG_LOGS:
            logger.debug("[WS] execution task created", extra={"thread_id": thread_id, "run_id": run_id})

        async def ping_loop():
            while True:
                await asyncio.sleep(30)  # Ping every 30 seconds
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
        
        ping_task = asyncio.create_task(ping_loop())
        
        # Stream events from queue
        try:
            saw_terminal_event = False
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    await websocket.send_json(event)
                    
                    # Close on completion
                    if event.get("type") == "run-completed":
                        saw_terminal_event = True
                        break
                    if event.get("type") == "error":
                        saw_terminal_event = True
                        break
                        
                except asyncio.TimeoutError:
                    # Check if execution is done
                    if execution_task.done():
                        # Check if it failed with an exception
                        try:
                            exc = execution_task.exception()
                        except asyncio.CancelledError:
                            exc = None
                        if exc:
                            logger.info("[WS] execution task failed", extra={"thread_id": thread_id, "run_id": run_id})
                            traceback.print_exception(type(exc), exc, exc.__traceback__)
                            await websocket.send_json({
                                "type": "error",
                                "error": str(exc),
                            })
                            saw_terminal_event = True
                        else:
                            if _DEBUG_LOGS:
                                logger.debug("[WS] execution task done", extra={"thread_id": thread_id, "run_id": run_id})
                        while True:
                            try:
                                pending = event_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                            await websocket.send_json(pending)
                            if pending.get("type") in ("run-completed", "error"):
                                saw_terminal_event = True
                        if not saw_terminal_event:
                            run_row = thread_service.get_run(thread_id, run_id) or {}
                            final_state = run_row.get("final_state") or {}
                            if isinstance(final_state, str):
                                try:
                                    final_state = json.loads(final_state)
                                except Exception:
                                    final_state = {}
                            output = None
                            if isinstance(final_state, dict):
                                output = final_state.get("output")
                                if not output:
                                    design_state = final_state.get("design_state", {})
                                    design_output = design_state.get("output", {}) if isinstance(design_state, dict) else {}
                                    if isinstance(design_output, dict):
                                        output = design_output.get("formatted_output")
                            await websocket.send_json(
                                {"type": "values-updated", "values": final_state, "output": output, "run_id": run_id}
                            )
                            await websocket.send_json(
                                {"type": "run-completed", "run_id": run_id, "thread_id": thread_id, "status": "completed"}
                            )
                            saw_terminal_event = True

                        break
                    continue
                    
        except WebSocketDisconnect:
            if _DEBUG_LOGS:
                logger.debug("[WS] websocket disconnected", extra={"thread_id": thread_id, "run_id": run_id})
        finally:
            ping_task.cancel()
            if execution_task and not execution_task.done():
                execution_task.cancel()
                try:
                    await execution_task
                except asyncio.CancelledError:
                    pass
                    
    except Exception as exc:
        logger.info("[WS] websocket stream error", extra={"thread_id": thread_id, "run_id": run_id})
        traceback.print_exc()
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(exc),
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
