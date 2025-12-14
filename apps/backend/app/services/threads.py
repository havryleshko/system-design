from __future__ import annotations
import asyncio
import json
import logging
from typing import Dict, Optional, Any
from uuid import uuid4

from langchain_core.messages import HumanMessage, BaseMessage

from app.agent.system_design.graph import get_compiled_graph_with_checkpointer
from app.storage.memory import add_event, record_node_tokens

logger = logging.getLogger(__name__)
_THREAD_RUNS: Dict[str, Dict[str, Any]] = {}


def _serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return state
    
    result = {}
    for key, value in state.items():
        if key == "messages" and isinstance(value, list):
            # Convert LangChain messages to serializable dicts
            result[key] = [
                {"role": getattr(msg, "type", "unknown"), "content": getattr(msg, "content", str(msg))}
                if isinstance(msg, BaseMessage)
                else msg
                for msg in value
            ]
        elif key == "stream_messages" and isinstance(value, list):
            # Same for stream_messages
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
    return _THREAD_RUNS.get(thread_id)


def create_thread() -> str:
    thread_id = str(uuid4())
    _THREAD_RUNS[thread_id] = {"runs": []}
    return thread_id


def start_run(thread_id: str, user_input: str, user_id: Optional[str] = None) -> str:
    run_id = str(uuid4())
    
    if thread_id not in _THREAD_RUNS:
        _THREAD_RUNS[thread_id] = {"runs": []}
    
    _THREAD_RUNS[thread_id]["runs"].append({
        "run_id": run_id,
        "status": "queued",
        "user_input": user_input,
    })

    _THREAD_RUNS[thread_id]["current_run"] = run_id
    
    return run_id


async def execute_run(
    thread_id: str,
    run_id: str,
    user_input: str,
    user_id: Optional[str] = None,
    ws_queue: Optional[asyncio.Queue] = None,
) -> Dict[str, Any]:
    print(f"[EXEC] execute_run called for thread {thread_id}, run {run_id}", flush=True)
    try:
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
            # Increase recursion limit for complex multi-agent graph
            # Default is 25, but our graph has 5 phases with multiple subnodes each
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
        
        # Update status to running
        if thread_id in _THREAD_RUNS:
            for run in _THREAD_RUNS[thread_id]["runs"]:
                if run["run_id"] == run_id:
                    run["status"] = "running"
                    break
        
        if ws_queue:
            print(f"[EXEC] Sending run-started event to queue", flush=True)
            await ws_queue.put({
                "type": "run-started",
                "run_id": run_id,
                "thread_id": thread_id,
            })
        
        # Stream events from graph execution
        print(f"[EXEC] Starting graph execution with astream_events...", flush=True)
        final_state = None
        try:
            async for event in compiled_graph.astream_events(
                initial_state,
                version="v2",
                config=config,
            ):
                event_type = event.get("event")
                event_name = event.get("name")
                
                if ws_queue:
                    if event_type == "on_chain_start" and event_name:
                        await ws_queue.put({
                            "type": "node-started",
                            "node": event_name,
                            "run_id": run_id,
                        })
                    elif event_type == "on_chain_end" and event_name:
                        await ws_queue.put({
                            "type": "node-completed",
                            "node": event_name,
                            "run_id": run_id,
                        })
                    elif event_type == "on_chain_stream":
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
                
                # Capture final state
                if event_type == "on_chain_end" and event_name == "__end__":
                    final_state = event.get("data", {}).get("output", {})
        except Exception as stream_exc:
            print(f"[EXEC] astream_events failed: {stream_exc}", flush=True)
            import traceback
            traceback.print_exc()
            logger.warning(f"astream_events failed, falling back to ainvoke: {stream_exc}")
        
        # If no events streamed, invoke directly
        if final_state is None:
            final_state = await compiled_graph.ainvoke(initial_state, config=config)
        
        # Extract final output
        final_judgement = None
        output = None
        values = {}
        
        if isinstance(final_state, dict):
            values = final_state
            # Extract final_judgement from eval_state
            eval_state = final_state.get("eval_state", {})
            final_judgement_data = eval_state.get("final_judgement", {})
            if isinstance(final_judgement_data, dict):
                output_field = final_judgement_data.get("output") or final_judgement_data.get("content")
                if output_field:
                    final_judgement = str(output_field)

            output = final_state.get("output") or final_judgement
            messages = final_state.get("messages", [])
            if messages and not final_judgement:
                last_msg = messages[-1]
                if hasattr(last_msg, "content"):
                    final_judgement = str(last_msg.content)
                    output = final_judgement
        # Serialize state for JSON (convert LangChain messages to dicts)
        serialized_values = _serialize_state(values)
        
        if thread_id in _THREAD_RUNS:
            for run in _THREAD_RUNS[thread_id]["runs"]:
                if run["run_id"] == run_id:
                    run["status"] = "completed"
                    run["final_state"] = serialized_values
                    break
        if ws_queue:
            await ws_queue.put({
                "type": "values-updated",
                "values": serialized_values,
                "final_judgement": final_judgement,
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
            "final_judgement": final_judgement,
            "output": output,
        }
        
    except Exception as exc:
        print(f"[EXEC] Run execution failed: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        logger.exception(f"Run execution failed: {exc}")
        if thread_id in _THREAD_RUNS:
            for run in _THREAD_RUNS[thread_id]["runs"]:
                if run["run_id"] == run_id:
                    run["status"] = "failed"
                    break
        
        if ws_queue:
            await ws_queue.put({
                "type": "error",
                "error": str(exc),
                "run_id": run_id,
            })
        
        raise


def get_thread_state(thread_id: str) -> Optional[Dict[str, Any]]:
    if thread_id not in _THREAD_RUNS:
        return None
    
    thread_data = _THREAD_RUNS[thread_id]
    current_run_id = thread_data.get("current_run")
    
    if not current_run_id:
        return {
            "thread_id": thread_id,
            "status": "queued",
        }
    for run in thread_data.get("runs", []):
        if run["run_id"] == current_run_id:
            status = run.get("status", "queued")
            final_state = run.get("final_state", {})
            final_judgement = None
            output = None
            
            if isinstance(final_state, dict):
                eval_state = final_state.get("eval_state", {})
                final_judgement_data = eval_state.get("final_judgement", {})
                if isinstance(final_judgement_data, dict):
                    output_field = final_judgement_data.get("output") or final_judgement_data.get("content")
                    if output_field:
                        final_judgement = str(output_field)
                
                output = final_state.get("output") or final_judgement
                
                if not final_judgement and final_state.get("messages"):
                    messages = final_state.get("messages", [])
                    if messages:
                        last_msg = messages[-1]
                        if hasattr(last_msg, "content"):
                            final_judgement = str(last_msg.content)
                        elif isinstance(last_msg, dict) and "content" in last_msg:
                            final_judgement = str(last_msg["content"])
                        if final_judgement:
                            output = final_judgement
            
            return {
                "thread_id": thread_id,
                "run_id": current_run_id,
                "status": status,
                "values": final_state,
                "final_judgement": final_judgement,
                "output": output,
            }
    
    return {
        "thread_id": thread_id,
        "run_id": current_run_id,
        "status": "queued",
    }
