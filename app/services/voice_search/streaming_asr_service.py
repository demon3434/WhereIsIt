from __future__ import annotations

from dataclasses import dataclass
import logging
from math import ceil
import threading

import numpy as np

from ...config import settings
from .model_assets import ensure_sherpa_streaming_model
from .session_manager import VoiceSession
from .text_normalizer import normalize_voice_text

logger = logging.getLogger(__name__)

try:
    import sherpa_onnx
except Exception:  # pragma: no cover - optional dependency
    sherpa_onnx = None  # type: ignore[assignment]


@dataclass(slots=True)
class _StreamingSessionContext:
    stream: object


@dataclass(slots=True)
class StreamingDecodeResult:
    text: str
    is_endpoint: bool = False
    is_final: bool = False


class StreamingAsrService:
    def __init__(self) -> None:
        self._recognizer = None
        self._lock = threading.Lock()
        self._sessions: dict[str, _StreamingSessionContext] = {}

    def warmup(self) -> None:
        try:
            self._load_recognizer()
        except Exception:
            logger.exception("streaming ASR warmup failed")

    @staticmethod
    def _mock_partial(session: VoiceSession) -> str:
        steps = [
            settings.voice_mock_final_text[:2],
            settings.voice_mock_final_text[:4],
            settings.voice_mock_final_text,
        ]
        threshold = max(1, ceil(settings.voice_stream_max_seconds * 1000 / max(1, settings.voice_stream_partial_interval_ms)))
        index = min(len(steps) - 1, session.duration_ms // max(500, threshold * 20))
        return steps[index]

    def _load_recognizer(self):
        if settings.voice_stream_engine != "sherpa_onnx":
            return None
        if sherpa_onnx is None:
            logger.warning("sherpa-onnx is not installed, streaming ASR will fall back")
            return None
        if self._recognizer is None:
            with self._lock:
                if self._recognizer is None:
                    model_dir = ensure_sherpa_streaming_model()
                    self._recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
                        tokens=str(model_dir / settings.voice_sherpa_tokens_file),
                        encoder=str(model_dir / settings.voice_sherpa_encoder_file),
                        decoder=str(model_dir / settings.voice_sherpa_decoder_file),
                        num_threads=settings.voice_model_num_threads,
                        sample_rate=settings.voice_stream_sample_rate,
                        feature_dim=80,
                        provider=settings.voice_sherpa_provider,
                        decoding_method="greedy_search",
                    )
        return self._recognizer

    def start_session(self, session: VoiceSession) -> None:
        recognizer = self._load_recognizer()
        if recognizer is None:
            return
        with self._lock:
            self._sessions[session.session_id] = _StreamingSessionContext(stream=recognizer.create_stream())

    def cleanup_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _get_context(self, session_id: str) -> _StreamingSessionContext | None:
        with self._lock:
            return self._sessions.get(session_id)

    @staticmethod
    def _pcm_to_float32(chunk: bytes) -> np.ndarray:
        samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
        return samples / 32768.0

    def feed_audio(self, session: VoiceSession, chunk: bytes) -> StreamingDecodeResult:
        if settings.voice_search_mock_stream:
            return StreamingDecodeResult(text=self._mock_partial(session))

        recognizer = self._load_recognizer()
        context = self._get_context(session.session_id)
        if recognizer is None or context is None:
            return StreamingDecodeResult(text=session.partial_text)

        samples = self._pcm_to_float32(chunk)
        if samples.size == 0:
            return StreamingDecodeResult(text=session.partial_text)

        context.stream.accept_waveform(session.sample_rate, samples)
        while recognizer.is_ready(context.stream):
            recognizer.decode_stream(context.stream)

        result = recognizer.get_result_all(context.stream)
        text = (result.text or "").strip()
        if not text:
            return StreamingDecodeResult(text=session.partial_text)

        normalized = normalize_voice_text(text)
        partial = normalized.display_text or text
        is_endpoint = recognizer.is_endpoint(context.stream)
        logger.debug(
            "voice partial updated session=%s duration_ms=%s partial=%s endpoint=%s final=%s",
            session.session_id,
            session.duration_ms,
            partial,
            is_endpoint,
            bool(result.is_final),
        )
        return StreamingDecodeResult(
            text=partial,
            is_endpoint=is_endpoint,
            is_final=bool(result.is_final),
        )

    def finish_stream(self, session: VoiceSession) -> str:
        if settings.voice_search_mock_stream:
            return session.partial_text or self._mock_partial(session)

        recognizer = self._load_recognizer()
        context = self._get_context(session.session_id)
        if recognizer is None or context is None:
            return session.partial_text

        context.stream.input_finished()
        while recognizer.is_ready(context.stream):
            recognizer.decode_stream(context.stream)

        result = recognizer.get_result_all(context.stream)
        text = (result.text or "").strip()
        normalized = normalize_voice_text(text)
        final_text = normalized.display_text or text or session.partial_text
        if recognizer.is_endpoint(context.stream):
            recognizer.reset(context.stream)
        return final_text


_streaming_asr_service = StreamingAsrService()


def get_streaming_asr_service() -> StreamingAsrService:
    return _streaming_asr_service
