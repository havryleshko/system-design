import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header, status

from app.schemas.threads import (
    ThreadCreate,
    ThreadResponse,
    RunStartRequest,
    RunStartResponse,
    ThreadStateResponse,
)
from app.services import threads as thread_service
from app.auth import decode_token

logger = logging.getLogger(__name__)

threads_router = APIRouter(prefix="/threads", tags=["threads"])


async def get_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_token(token)
        return claims.get("sub")
    except Exception:
        return None


@threads_router.post("", status_code=status.HTTP_201_CREATED, response_model=ThreadResponse)
async def create_thread(user_id: Optional[str] = Depends(get_user_id)):
    thread_id = thread_service.create_thread(user_id)
    return ThreadResponse(thread_id=thread_id)


@threads_router.post("/{thread_id}/runs", status_code=status.HTTP_201_CREATED, response_model=RunStartResponse)
async def start_run(
    thread_id: str,
    payload: RunStartRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    run_id = thread_service.start_run(thread_id, payload.input, user_id)
    return RunStartResponse(run_id=run_id, thread_id=thread_id)


@threads_router.get("/{thread_id}/state", response_model=ThreadStateResponse)
async def get_thread_state(thread_id: str):
    state = thread_service.get_thread_state(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return ThreadStateResponse(**state)


@threads_router.websocket("/{thread_id}/stream")
async def stream_thread(websocket: WebSocket, thread_id: str):
    import traceback
    print(f"[WS] WebSocket handler called for thread {thread_id}", flush=True)
    await websocket.accept()
    print(f"[WS] WebSocket accepted for thread {thread_id}", flush=True)

    query_params = dict(websocket.query_params)
    token = query_params.get("token")
    run_id = query_params.get("run_id")
    print(f"[WS] Query params - run_id: {run_id}, token present: {bool(token)}", flush=True)
    
    if not token:
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            print(f"[WS] Got token from auth header", flush=True)
    
    if not token:
        print(f"[WS] Missing token, closing with 1008", flush=True)
        await websocket.close(code=1008, reason="Missing authorization token")
        return
    
    if not run_id:
        print(f"[WS] Missing run_id, closing with 1008", flush=True)
        await websocket.close(code=1008, reason="Missing run_id")
        return
    
    try:
        claims = decode_token(token)
        user_id = claims.get("sub")
        print(f"[WS] Token decoded, user_id: {user_id}", flush=True)
    except Exception as exc:
        print(f"[WS] Token decode failed: {exc}, closing with 1008", flush=True)
        await websocket.close(code=1008, reason=f"Invalid token: {exc}")
        return
    
    # Verify thread exists
    state = thread_service.get_thread_state(thread_id)
    print(f"[WS] Thread state: {state}", flush=True)
    if not state:
        print(f"[WS] Thread not found, closing with 1008", flush=True)
        await websocket.close(code=1008, reason="Thread not found")
        return
    
    # Get run data
    run_data = thread_service.get_run(thread_id, run_id)
    print(f"[WS] Run data for {thread_id}/{run_id}: {run_data}", flush=True)
    if not run_data:
        print(f"[WS] ERROR: Run not found for thread {thread_id}, run {run_id}", flush=True)
        await websocket.send_json({
            "type": "error",
            "error": "Run not found",
        })
        await websocket.close(code=1008, reason="Run not found")
        return
    
    run_status = run_data.get("status", "queued")
    user_input = run_data.get("user_input", "")
    print(f"[WS] Run {run_id} status: {run_status}, input: {user_input[:100] if user_input else 'None'}...", flush=True)
    
    # If run is already completed or failed, send final state immediately
    if run_status in ("completed", "failed"):
        print(f"[WS] Run already {run_status}, sending final state", flush=True)
        final_state = run_data.get("final_state", {})
        if isinstance(final_state, str):
            try:
                final_state = json.loads(final_state)
            except Exception:
                final_state = {}
        output = final_state.get("output") if isinstance(final_state, dict) else None
        
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
        print(f"[WS] Run already running, will poll for completion", flush=True)
        # Poll for completion instead of starting new execution
        while True:
            await asyncio.sleep(2)
            thread_data = thread_service.get_thread_data(thread_id) or {}
            for run in thread_data.get("runs", []):
                if run["run_id"] == run_id:
                    current_status = run.get("status", "queued")
                    if current_status in ("completed", "failed"):
                        final_state = run.get("final_state", {})
                        output = final_state.get("output") if isinstance(final_state, dict) else None
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
        print(f"[WS] ERROR: Run missing input for thread {thread_id}, run {run_id}", flush=True)
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
        print(f"[WS] Starting execution task for thread {thread_id}, run {run_id}", flush=True)
        execution_task = asyncio.create_task(
            thread_service.execute_run(thread_id, run_id, user_input, user_id, event_queue)
        )
        print(f"[WS] Execution task created for thread {thread_id}, run {run_id}", flush=True)

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
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=1.0)
                    await websocket.send_json(event)
                    
                    # Close on completion
                    if event.get("type") == "run-completed":
                        break
                    if event.get("type") == "error":
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
                            print(f"[WS] Execution task failed with exception: {exc}", flush=True)
                            traceback.print_exception(type(exc), exc, exc.__traceback__)
                            await websocket.send_json({
                                "type": "error",
                                "error": str(exc),
                            })
                        else:
                            print(f"[WS] Execution task done without exception", flush=True)
                        break
                    continue
                    
        except WebSocketDisconnect:
            print(f"[WS] WebSocket disconnected for thread {thread_id}, run {run_id}", flush=True)
        finally:
            ping_task.cancel()
            if execution_task and not execution_task.done():
                execution_task.cancel()
                try:
                    await execution_task
                except asyncio.CancelledError:
                    pass
                    
    except Exception as exc:
        print(f"[WS] WebSocket stream error: {exc}", flush=True)
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
