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
async def create_thread():
    thread_id = thread_service.create_thread()
    return ThreadResponse(thread_id=thread_id)


@threads_router.post("/{thread_id}/runs", status_code=status.HTTP_201_CREATED, response_model=RunStartResponse)
async def start_run(
    thread_id: str,
    payload: RunStartRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    run_id = thread_service.start_run(thread_id, payload.input, user_id)
    return RunStartResponse(run_id=run_id, thread_id=thread_id)


@threads_router.post("/{thread_id}/runs/{run_id}/resume", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def resume_run(thread_id: str, run_id: str):
    return {"message": "Resume not implemented - clarifiers disabled"}


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
    
    if not token:
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    
    if not token:
        await websocket.close(code=1008, reason="Missing authorization token")
        return
    
    if not run_id:
        await websocket.close(code=1008, reason="Missing run_id")
        return
    
    try:
        claims = decode_token(token)
        user_id = claims.get("sub")
    except Exception as exc:
        await websocket.close(code=1008, reason=f"Invalid token: {exc}")
        return
    
    if not run_id:
        await websocket.close(code=1008, reason="Missing run_id")
        return
    
    # Verify thread exists
    state = thread_service.get_thread_state(thread_id)
    if not state:
        await websocket.close(code=1008, reason="Thread not found")
        return
    
    # Create event queue for streaming
    event_queue = asyncio.Queue()
    
    # Start run execution in background
    execution_task = None
    try:
        # Get user input from thread state
        thread_data = thread_service.get_thread_data(thread_id) or {}
        print(f"[WS] Thread data for {thread_id}: {thread_data}", flush=True)
        user_input = None
        for run in thread_data.get("runs", []):
            if run["run_id"] == run_id:
                user_input = run.get("user_input", "")
                break
        
        print(f"[WS] User input for run {run_id}: {user_input[:100] if user_input else 'None'}...", flush=True)
        
        if not user_input:
            print(f"[WS] ERROR: Run not found or missing input for thread {thread_id}, run {run_id}", flush=True)
            await websocket.send_json({
                "type": "error",
                "error": "Run not found or missing input",
            })
            await websocket.close()
            return
        
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
