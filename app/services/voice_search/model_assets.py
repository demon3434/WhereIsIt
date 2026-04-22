from __future__ import annotations

import logging
import os
from pathlib import Path
import tarfile
import threading

from ...config import settings
import requests

try:
    from huggingface_hub import hf_hub_download
except Exception:  # pragma: no cover - optional dependency
    hf_hub_download = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
_download_lock = threading.Lock()


def configure_model_cache_env() -> None:
    root = Path(settings.voice_model_download_root)
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MODELSCOPE_CACHE", str(root / "modelscope"))
    os.environ.setdefault("HF_HOME", str(root / "huggingface"))


def _safe_extract_tar(archive_path: Path, destination: Path) -> None:
    with tarfile.open(archive_path, "r:*") as archive:
        resolved_destination = destination.resolve()
        for member in archive.getmembers():
            member_path = (destination / member.name).resolve()
            if resolved_destination not in member_path.parents and member_path != resolved_destination:
                raise RuntimeError(f"unsafe archive member: {member.name}")
        archive.extractall(destination)


def _derive_archive_dir_name(archive_name: str) -> str:
    for suffix in (".tar.bz2", ".tar.gz", ".tgz", ".zip"):
        if archive_name.endswith(suffix):
            return archive_name[: -len(suffix)]
    return Path(archive_name).stem


def _download_file(url: str, destination: Path) -> None:
    tmp_path = destination.with_suffix(destination.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        expected_size = int(response.headers.get("Content-Length", "0") or 0)
        written_size = 0
        with tmp_path.open("wb") as output_file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                output_file.write(chunk)
                written_size += len(chunk)
    if expected_size and written_size != expected_size:
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError(f"incomplete download: expected {expected_size}, got {written_size}")
    tmp_path.replace(destination)


def _required_sherpa_files() -> list[str]:
    return [
        settings.voice_sherpa_tokens_file,
        settings.voice_sherpa_encoder_file,
        settings.voice_sherpa_decoder_file,
    ]


def ensure_sherpa_streaming_model() -> Path:
    configure_model_cache_env()

    if settings.voice_sherpa_model_dir:
        model_dir = Path(settings.voice_sherpa_model_dir)
        if model_dir.is_dir():
            return model_dir
        raise RuntimeError(f"sherpa model dir not found: {model_dir}")

    root = Path(settings.voice_model_download_root) / "sherpa-onnx"
    root.mkdir(parents=True, exist_ok=True)
    repo_id = settings.voice_sherpa_hf_repo.strip()
    if repo_id:
        model_dir = root / repo_id.split("/")[-1]
    else:
        url = settings.voice_sherpa_model_url.strip()
        if not url:
            raise RuntimeError("VOICE_SHERPA model source is not configured")
        archive_name = url.rsplit("/", 1)[-1]
        model_dir = root / _derive_archive_dir_name(archive_name)

    required_files = _required_sherpa_files()
    tokens_file = model_dir / settings.voice_sherpa_tokens_file
    encoder_file = model_dir / settings.voice_sherpa_encoder_file
    decoder_file = model_dir / settings.voice_sherpa_decoder_file
    if tokens_file.is_file() and encoder_file.is_file() and decoder_file.is_file():
        return model_dir

    with _download_lock:
        if tokens_file.is_file() and encoder_file.is_file() and decoder_file.is_file():
            return model_dir

        if repo_id:
            if hf_hub_download is None:
                raise RuntimeError("huggingface_hub is required when VOICE_SHERPA_HF_REPO is configured")
            logger.info("downloading sherpa model files from Hugging Face repo %s into %s", repo_id, model_dir)
            model_dir.mkdir(parents=True, exist_ok=True)
            for filename in required_files:
                hf_hub_download(
                    repo_id=repo_id,
                    filename=filename,
                    local_dir=str(model_dir),
                    local_dir_use_symlinks=False,
                )
        else:
            archive_path = root / archive_name
            if not archive_path.exists():
                logger.info("downloading sherpa model from %s", url)
                _download_file(url, archive_path)

            try:
                logger.info("extracting sherpa model archive %s", archive_path)
                _safe_extract_tar(archive_path, root)
            except (tarfile.TarError, EOFError) as exc:
                logger.warning("sherpa model archive is corrupted, re-downloading: %s", exc)
                archive_path.unlink(missing_ok=True)
                _download_file(url, archive_path)
                _safe_extract_tar(archive_path, root)

        if not tokens_file.is_file() or not encoder_file.is_file() or not decoder_file.is_file():
            raise RuntimeError(f"sherpa model files are incomplete under {model_dir}")

    return model_dir
