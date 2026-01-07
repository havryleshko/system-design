from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.routes.threads import get_user_id
from app.schemas.threads import (
    ClarifierFinalizeRequest,
    ClarifierFinalizeResponse,
    ClarifierMessage,
    ClarifierSessionCreateRequest,
    ClarifierSessionCreateResponse,
    ClarifierSessionGetResponse,
    ClarifierTurnRequest,
    ClarifierTurnResponse,
)
from app.services import threads as thread_service
from app.services import clarifier as clarifier_service
from app.agent.system_design.clarifier import run_clarifier


clarifier_router = APIRouter(tags=["clarifier"])

MAX_TURNS = 8
MAX_MESSAGE_CHARS = 4_000


def _truncate(s: str, max_chars: int) -> str:
    s = s or ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n…[truncated]"


@clarifier_router.post(
    "/threads/{thread_id}/clarifier/sessions",
    response_model=ClarifierSessionCreateResponse,
)
async def create_clarifier_session(
    thread_id: str,
    payload: ClarifierSessionCreateRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    original_input = (payload.input or "").strip()
    if not original_input:
        raise HTTPException(status_code=400, detail="Input is required")

    thread = thread_service.get_thread_data(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    if str(thread.get("user_id") or "") != str(user_id):
        raise HTTPException(status_code=403, detail="Forbidden")

    session_id = clarifier_service.create_session(user_id=str(user_id), thread_id=thread_id, original_input=original_input)

    # Generate the first assistant message immediately.
    engine = run_clarifier(
        original_input=original_input,
        transcript=[],
        turn_count=0,
        force_final=False,
    )
    clarifier_service.append_message(
        session_id=session_id,
        user_id=str(user_id),
        role="assistant",
        content=_truncate(engine.assistant_message, MAX_MESSAGE_CHARS),
    )

    return ClarifierSessionCreateResponse(
        session_id=session_id,
        status="active",
        assistant_message=engine.assistant_message,
        turn_count=0,
    )


@clarifier_router.get(
    "/clarifier/sessions/{session_id}",
    response_model=ClarifierSessionGetResponse,
)
async def get_clarifier_session(
    session_id: str,
    user_id: Optional[str] = Depends(get_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    sess = clarifier_service.get_session(session_id=session_id, user_id=str(user_id))
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = clarifier_service.list_messages(session_id=session_id, user_id=str(user_id), limit=200)
    return ClarifierSessionGetResponse(
        session_id=str(sess["id"]),
        thread_id=str(sess["thread_id"]),
        status=str(sess["status"]),
        original_input=str(sess["original_input"]),
        turn_count=int(sess.get("turn_count") or 0),
        final_summary=sess.get("final_summary"),
        enriched_prompt=sess.get("enriched_prompt"),
        missing_fields=sess.get("missing_fields") or [],
        assumptions=sess.get("assumptions") or [],
        messages=[ClarifierMessage(role=m["role"], content=m["content"], created_at=str(m.get("created_at"))) for m in messages],
    )


@clarifier_router.post(
    "/clarifier/sessions/{session_id}/turn",
    response_model=ClarifierTurnResponse,
)
async def clarifier_turn(
    session_id: str,
    payload: ClarifierTurnRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    sess = clarifier_service.get_session(session_id=session_id, user_id=str(user_id))
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(sess.get("status")) != "active":
        raise HTTPException(status_code=409, detail="Session is not active")

    turn_count = int(sess.get("turn_count") or 0)
    if turn_count >= MAX_TURNS:
        raise HTTPException(status_code=409, detail="Max turns reached; finalize to continue")

    msg = _truncate((payload.message or "").strip(), MAX_MESSAGE_CHARS)
    if not msg:
        raise HTTPException(status_code=400, detail="Message is required")

    clarifier_service.append_message(session_id=session_id, user_id=str(user_id), role="user", content=msg)
    new_turn_count = clarifier_service.update_turn_count(session_id=session_id, user_id=str(user_id), delta=1)

    transcript_rows = clarifier_service.list_messages(session_id=session_id, user_id=str(user_id), limit=200)
    transcript = [{"role": r["role"], "content": r["content"]} for r in transcript_rows]

    engine = run_clarifier(
        original_input=str(sess.get("original_input") or ""),
        transcript=transcript,
        turn_count=new_turn_count,
        force_final=False,
    )
    clarifier_service.append_message(
        session_id=session_id,
        user_id=str(user_id),
        role="assistant",
        content=_truncate(engine.assistant_message, MAX_MESSAGE_CHARS),
    )

    if engine.kind == "finalized":
        clarifier_service.finalize_session(
            session_id=session_id,
            user_id=str(user_id),
            status=str(engine.final_status or "draft"),
            final_summary=str(engine.final_summary or ""),
            enriched_prompt=str(engine.enriched_prompt or ""),
            missing_fields=engine.missing_fields or [],
            assumptions=engine.assumptions or [],
        )
        return ClarifierTurnResponse(status="finalized", assistant_message=engine.assistant_message, turn_count=new_turn_count)

    return ClarifierTurnResponse(status="active", assistant_message=engine.assistant_message, turn_count=new_turn_count)


@clarifier_router.post(
    "/clarifier/sessions/{session_id}/finalize",
    response_model=ClarifierFinalizeResponse,
)
async def finalize_clarifier(
    session_id: str,
    payload: ClarifierFinalizeRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    sess = clarifier_service.get_session(session_id=session_id, user_id=str(user_id))
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    if str(sess.get("status")) == "finalized":
        final_status = str(sess.get("final_status") or "draft")
        return ClarifierFinalizeResponse(
            status="ready" if final_status == "ready" else "draft",
            final_summary=str(sess.get("final_summary") or ""),
            enriched_prompt=str(sess.get("enriched_prompt") or ""),
            missing_fields=sess.get("missing_fields") or [],
            assumptions=sess.get("assumptions") or [],
        )

    transcript_rows = clarifier_service.list_messages(session_id=session_id, user_id=str(user_id), limit=200)
    transcript = [{"role": r["role"], "content": r["content"]} for r in transcript_rows]

    # Force final output.
    engine = run_clarifier(
        original_input=str(sess.get("original_input") or ""),
        transcript=transcript,
        turn_count=int(sess.get("turn_count") or 0),
        force_final=True,
    )
    clarifier_service.append_message(
        session_id=session_id,
        user_id=str(user_id),
        role="assistant",
        content=_truncate(engine.assistant_message, MAX_MESSAGE_CHARS),
    )

    # Ensure we always finalize; if engine didn't, create a minimal summary.
    final_summary = str(engine.final_summary or "Proceeding as draft. Requirements captured from clarifier chat.")
    enriched_prompt = str(engine.enriched_prompt or (str(sess.get("original_input") or "") + "\n\nClarifier Summary:\n" + final_summary))
    final_status = str(engine.final_status or ("draft" if payload.proceed_as_draft else "draft"))
    if payload.proceed_as_draft:
        final_status = "draft"

    clarifier_service.finalize_session(
        session_id=session_id,
        user_id=str(user_id),
        status=final_status,
        final_summary=final_summary,
        enriched_prompt=enriched_prompt,
        missing_fields=engine.missing_fields or [],
        assumptions=engine.assumptions or [],
    )

    return ClarifierFinalizeResponse(
        status="draft" if final_status == "draft" else "ready",
        final_summary=final_summary,
        enriched_prompt=enriched_prompt,
        missing_fields=engine.missing_fields or [],
        assumptions=engine.assumptions or [],
    )


