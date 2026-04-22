from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import threading
import uuid

from ...config import settings


class VoiceSessionState(StrEnum):
    INIT = "INIT"
    STREAMING = "STREAMING"
    STOPPED = "STOPPED"
    FINALIZING = "FINALIZING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass(slots=True)
class VoiceSession:
    session_id: str
    user_id: int
    created_at: datetime
    updated_at: datetime
    sample_rate: int
    channels: int
    encoding: str
    state: VoiceSessionState = VoiceSessionState.INIT
    partial_text: str = ""
    first_stage_final_text: str = ""
    audio_chunks: list[bytes] = field(default_factory=list)
    last_partial_at: datetime | None = None
    total_audio_bytes: int = 0
    max_duration_reached: bool = False

    def append_audio(self, chunk: bytes) -> None:
        self.audio_chunks.append(chunk)
        self.total_audio_bytes += len(chunk)
        self.updated_at = datetime.now(timezone.utc)

    @property
    def audio_bytes(self) -> bytes:
        return b"".join(self.audio_chunks)

    @property
    def duration_ms(self) -> int:
        bytes_per_second = max(1, self.sample_rate * self.channels * 2)
        return int(self.total_audio_bytes * 1000 / bytes_per_second)


class VoiceSessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ttl = timedelta(seconds=max(60, settings.voice_session_ttl_seconds))
        self._sessions: dict[str, VoiceSession] = {}

    def create_session(self, user_id: int, sample_rate: int, channels: int, encoding: str) -> VoiceSession:
        now = datetime.now(timezone.utc)
        session = VoiceSession(
            session_id=f"vs_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            created_at=now,
            updated_at=now,
            sample_rate=sample_rate,
            channels=channels,
            encoding=encoding,
            state=VoiceSessionState.STREAMING,
        )
        with self._lock:
            self._purge_expired_locked(now)
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> VoiceSession | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge_expired_locked(now)
            session = self._sessions.get(session_id)
            if session:
                session.updated_at = now
            return session

    def save_session(self, session: VoiceSession) -> VoiceSession:
        with self._lock:
            session.updated_at = datetime.now(timezone.utc)
            self._sessions[session.session_id] = session
        return session

    def mark_done(self, session_id: str, first_stage_final_text: str = "") -> VoiceSession | None:
        session = self.get_session(session_id)
        if not session:
            return None
        session.state = VoiceSessionState.DONE
        session.first_stage_final_text = first_stage_final_text or session.first_stage_final_text
        return self.save_session(session)

    def mark_failed(self, session_id: str) -> VoiceSession | None:
        session = self.get_session(session_id)
        if not session:
            return None
        session.state = VoiceSessionState.FAILED
        return self.save_session(session)

    def _purge_expired_locked(self, now: datetime) -> None:
        expired_ids = [session_id for session_id, session in self._sessions.items() if now - session.updated_at > self._ttl]
        for session_id in expired_ids:
            self._sessions.pop(session_id, None)


_voice_session_manager = VoiceSessionManager()


def get_voice_session_manager() -> VoiceSessionManager:
    return _voice_session_manager
