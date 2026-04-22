from __future__ import annotations

import io
import logging
import os
from pathlib import Path
import tempfile
import threading
import wave

from ...config import settings
from .model_assets import configure_model_cache_env

logger = logging.getLogger(__name__)

try:
    from funasr import AutoModel
except Exception:  # pragma: no cover - optional dependency
    AutoModel = None  # type: ignore[assignment]


def _wrap_pcm_as_wav(audio_bytes: bytes, sample_rate: int, channels: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_bytes)
    return buffer.getvalue()


def _extract_text(result: object) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        text = result.get("text")
        return text.strip() if isinstance(text, str) else ""
    if isinstance(result, list):
        for item in result:
            text = _extract_text(item)
            if text:
                return text
    return ""


class OfflineAsrService:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def warmup(self) -> None:
        try:
            self._load_model()
        except Exception:
            logger.exception("offline ASR warmup failed")

    def _load_model(self):
        if settings.voice_offline_engine != "funasr":
            return None
        if AutoModel is None:
            logger.warning("FunASR is not installed, offline ASR will fall back")
            return None
        if self._model is None:
            with self._lock:
                if self._model is None:
                    configure_model_cache_env()
                    Path(settings.voice_model_download_root).mkdir(parents=True, exist_ok=True)
                    self._model = AutoModel(
                        model=settings.voice_funasr_model,
                        vad_model=settings.voice_funasr_vad_model or None,
                        punc_model=settings.voice_funasr_punc_model or None,
                        device=settings.voice_model_device,
                        hub=settings.voice_funasr_hub,
                        disable_update=True,
                    )
        return self._model

    def recognize(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        channels: int,
        audio_format: str,
        first_stage_text: str = "",
    ) -> tuple[str, str]:
        cleaned_first_stage = (first_stage_text or "").strip()
        if settings.voice_search_mock_final:
            return cleaned_first_stage or settings.voice_mock_final_text, "mock"

        model = self._load_model()
        if model is None:
            if cleaned_first_stage:
                return cleaned_first_stage, "first_stage_fallback"
            raise RuntimeError("offline ASR engine unavailable")

        payload = audio_bytes
        if audio_format.lower() in {"pcm", "pcm_s16le"}:
            payload = _wrap_pcm_as_wav(audio_bytes, sample_rate=sample_rate, channels=channels)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_audio.write(payload)
            temp_path = temp_audio.name
        try:
            result = model.generate(
                input=temp_path,
                batch_size_s=300,
            )
            text = _extract_text(result)
            if text:
                return text, "funasr"
            if cleaned_first_stage:
                return cleaned_first_stage, "first_stage_fallback"
            raise RuntimeError("FunASR returned empty text")
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("failed to delete temp audio file: %s", temp_path)


_offline_asr_service = OfflineAsrService()


def get_offline_asr_service() -> OfflineAsrService:
    return _offline_asr_service
