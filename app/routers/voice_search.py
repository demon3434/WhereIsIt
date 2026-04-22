from __future__ import annotations

import asyncio
import base64
import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from ..auth import parse_token
from ..config import settings
from ..database import SessionLocal, get_db
from ..deps import get_current_user
from ..models import User
from ..services.voice_search import (
    build_query_plan,
    VoiceSearchTermSnapshot,
    get_offline_asr_service,
    get_streaming_asr_service,
    get_voice_session_manager,
    load_voice_search_term_snapshot,
    normalize_voice_text,
    search_items_for_voice,
)
from ..services.voice_search.session_manager import VoiceSessionState

router = APIRouter(prefix="/api/voice-search", tags=["voice-search"])
logger = logging.getLogger(__name__)


def _max_audio_bytes(sample_rate: int, channels: int) -> int:
    return max(1, settings.voice_stream_max_seconds * sample_rate * channels * 2)


def _require_voice_enabled() -> None:
    if not settings.voice_search_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="voice search disabled")


def _resolve_websocket_user(websocket: WebSocket) -> User:
    token: str | None = websocket.query_params.get("token")
    auth_header = websocket.headers.get("authorization")
    cookie_header = websocket.headers.get("cookie", "")

    if not token and auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token and cookie_header:
        for cookie in cookie_header.split(";"):
            key, _, value = cookie.strip().partition("=")
            if key == settings.auth_cookie_name:
                token = value
                break

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")

    user_id = parse_token(token)
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user disabled")
        db.expunge(user)
        return user
    finally:
        db.close()


@router.post("/finalize")
@router.post("/final")
async def finalize_voice_search(
    session_id: str | None = Form(default=None),
    first_stage_text: str | None = Form(default=None),
    audio: UploadFile | None = File(default=None),
    audio_format: str = Form(default="wav"),
    sample_rate: int = Form(default=16000),
    channels: int = Form(default=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_voice_enabled()

    offline_asr_service = get_offline_asr_service()
    session_manager = get_voice_session_manager()

    session = None
    audio_bytes = b""
    resolved_sample_rate = sample_rate
    resolved_channels = channels
    resolved_format = audio_format.lower()

    if session_id:
        session = session_manager.get_session(session_id)
        if not session or session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="voice search session not found")
        if not session.audio_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="voice search audio is empty")
        session.state = VoiceSessionState.FINALIZING
        session_manager.save_session(session)
        audio_bytes = session.audio_bytes
        resolved_sample_rate = session.sample_rate
        resolved_channels = session.channels
        resolved_format = "pcm_s16le"

    if audio is not None:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="voice search audio is empty")
        if audio.filename and "." in audio.filename:
            resolved_format = audio.filename.rsplit(".", 1)[-1].lower()

    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing voice search audio or session")

    offline_started = time.perf_counter()
    try:
        final_text, asr_mode = await asyncio.to_thread(
            offline_asr_service.recognize,
            audio_bytes,
            resolved_sample_rate,
            resolved_channels,
            resolved_format,
            first_stage_text or (session.partial_text if session else ""),
        )
    except Exception as exc:
        logger.exception("voice finalize ASR failed")
        if session:
            session_manager.mark_failed(session.session_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"voice offline ASR error: {exc}") from exc
    offline_ms = int((time.perf_counter() - offline_started) * 1000)

    normalized = normalize_voice_text(final_text)
    snapshot = load_voice_search_term_snapshot(db, current_user.id)
    plan = build_query_plan(
        final_text=normalized.display_text,
        normalized_query=normalized.query_text,
        snapshot=snapshot,
    )

    search_started = time.perf_counter()
    try:
        items = search_items_for_voice(db, current_user, plan)
    except Exception as exc:
        logger.exception("voice item search failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"voice search error: {exc}") from exc
    search_ms = int((time.perf_counter() - search_started) * 1000)

    logger.info(
        "voice search finalized session=%s user_id=%s asr_mode=%s final_text=%s normalized_query=%s result_count=%s",
        session.session_id if session else None,
        current_user.id,
        asr_mode,
        final_text,
        plan.normalized_query,
        len(items),
    )

    if session:
        session.first_stage_final_text = first_stage_text or session.partial_text
        session.partial_text = session.first_stage_final_text
        session_manager.mark_done(session.session_id, first_stage_final_text=session.first_stage_final_text)

    return {
        "session_id": session.session_id if session else None,
        "first_stage_text": first_stage_text or (session.partial_text if session else ""),
        "final_text": final_text,
        "normalized_query": plan.normalized_query,
        "keywords": plan.keywords,
        "items": items,
        "timing": {
            "offline_asr_ms": offline_ms,
            "search_ms": search_ms,
        },
        "debug": {
            "asr_mode": asr_mode,
            "audio_format": resolved_format,
            "audio_duration_ms": int(len(audio_bytes) * 1000 / max(1, resolved_sample_rate * resolved_channels * 2))
            if resolved_format in {"pcm", "pcm_s16le"}
            else None,
        },
    }


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    if not settings.voice_search_enabled:
        await websocket.close(code=1008, reason="voice search disabled")
        return

    try:
        current_user = _resolve_websocket_user(websocket)
    except HTTPException as exc:
        await websocket.close(code=1008, reason=str(exc.detail))
        return

    await websocket.accept()
    session_manager = get_voice_session_manager()
    streaming_service = get_streaming_asr_service()
    session = None

    try:
        while True:
            payload = await websocket.receive_json()
            message_type = payload.get("type")

            if message_type == "start":
                sample_rate = int(payload.get("sample_rate") or payload.get("sampleRate") or settings.voice_stream_sample_rate)
                channels = int(payload.get("channels") or settings.voice_stream_channels)
                encoding = str(payload.get("encoding") or payload.get("format") or "pcm_s16le")
                if sample_rate != settings.voice_stream_sample_rate or channels != settings.voice_stream_channels:
                    await websocket.send_json({"type": "error", "message": "unsupported audio format"})
                    continue
                session = session_manager.create_session(
                    user_id=current_user.id,
                    sample_rate=sample_rate,
                    channels=channels,
                    encoding=encoding,
                )
                try:
                    await asyncio.to_thread(streaming_service.start_session, session)
                except Exception as exc:
                    logger.exception("voice stream session init failed")
                    session_manager.mark_failed(session.session_id)
                    await websocket.send_json({"type": "error", "message": f"voice stream init error: {exc}"})
                    await websocket.close(code=1011, reason="voice stream init error")
                    return
                await websocket.send_json({"type": "session", "session_id": session.session_id})
                continue

            if message_type == "audio":
                if session is None:
                    await websocket.send_json({"type": "error", "message": "voice session not started"})
                    continue
                chunk_data = payload.get("data") or payload.get("payload")
                if not chunk_data:
                    continue
                chunk = base64.b64decode(chunk_data)
                max_audio_bytes = _max_audio_bytes(session.sample_rate, session.channels)
                remaining_bytes = max(0, max_audio_bytes - session.total_audio_bytes)
                if remaining_bytes <= 0:
                    if not session.max_duration_reached:
                        session.max_duration_reached = True
                        session_manager.save_session(session)
                        await websocket.send_json(
                            {
                                "type": "limit_reached",
                                "session_id": session.session_id,
                                "message": "voice session max duration reached",
                                "max_seconds": settings.voice_stream_max_seconds,
                            }
                        )
                    continue

                accepted_chunk = chunk[:remaining_bytes]
                truncated = len(accepted_chunk) < len(chunk)
                session.append_audio(accepted_chunk)
                if truncated:
                    session.max_duration_reached = True
                session_manager.save_session(session)

                try:
                    decode_result = await asyncio.to_thread(streaming_service.feed_audio, session, accepted_chunk)
                except Exception as exc:
                    logger.exception("voice stream partial decode failed")
                    session_manager.mark_failed(session.session_id)
                    await websocket.send_json({"type": "error", "message": f"voice stream decode error: {exc}"})
                    await websocket.close(code=1011, reason="voice stream decode error")
                    return

                now_ms = int(time.time() * 1000)
                last_partial_ms = int(session.last_partial_at.timestamp() * 1000) if session.last_partial_at else 0
                should_push_partial = (
                    decode_result.text
                    and decode_result.text != session.partial_text
                    and (
                        now_ms - last_partial_ms >= settings.voice_stream_partial_interval_ms
                        or decode_result.is_endpoint
                        or decode_result.is_final
                        or truncated
                    )
                )
                if should_push_partial:
                    session.partial_text = decode_result.text
                    session.last_partial_at = session.updated_at
                    session_manager.save_session(session)
                    await websocket.send_json(
                        {"type": "partial", "text": decode_result.text, "session_id": session.session_id}
                    )
                if truncated:
                    await websocket.send_json(
                        {
                            "type": "limit_reached",
                            "session_id": session.session_id,
                            "message": "voice session max duration reached",
                            "max_seconds": settings.voice_stream_max_seconds,
                        }
                    )
                continue

            if message_type == "stop":
                if session is None:
                    await websocket.send_json({"type": "error", "message": "voice session not started"})
                    continue
                session.state = VoiceSessionState.STOPPED
                try:
                    session.first_stage_final_text = await asyncio.to_thread(streaming_service.finish_stream, session)
                except Exception as exc:
                    logger.exception("voice stream finalize failed")
                    session_manager.mark_failed(session.session_id)
                    await websocket.send_json({"type": "error", "message": f"voice stream finalize error: {exc}"})
                    await websocket.close(code=1011, reason="voice stream finalize error")
                    return
                session.partial_text = session.first_stage_final_text
                session_manager.save_session(session)
                if session.first_stage_final_text:
                    await websocket.send_json(
                        {
                            "type": "partial",
                            "text": session.first_stage_final_text,
                            "session_id": session.session_id,
                        }
                    )
                await websocket.send_json(
                    {
                        "type": "finalizing",
                        "session_id": session.session_id,
                        "text": session.first_stage_final_text,
                    }
                )
                continue

            await websocket.send_json({"type": "error", "message": "unsupported voice message type"})
    except WebSocketDisconnect:
        if session is not None and session.state not in {VoiceSessionState.DONE, VoiceSessionState.FAILED}:
            session_manager.save_session(session)
    finally:
        if session is not None:
            await asyncio.to_thread(streaming_service.cleanup_session, session.session_id)
