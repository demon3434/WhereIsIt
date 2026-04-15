from __future__ import annotations

import hashlib
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TEMP_ROOT = Path(tempfile.gettempdir()) / "whereisit-gui"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)

_TASKS: dict[str, dict[str, Any]] = {}
_DB_BACKUP_FILES: dict[str, dict[str, Any]] = {}
_DB_RESTORE_UPLOADS: dict[str, dict[str, Any]] = {}
_UPLOADS_MANIFESTS: dict[str, dict[str, Any]] = {}
_UPLOADS_FILE_INDEX: dict[str, dict[str, str]] = {}
_UPLOADS_RESTORE_TASKS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()


def now_utc() -> datetime:
    return datetime.now(UTC)


def iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def create_task(task_type: str, created_by: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    task_id = new_id("task")
    task = {
        "taskId": task_id,
        "taskType": task_type,
        "status": "created",
        "stage": "created",
        "createdAt": now_utc(),
        "startedAt": None,
        "finishedAt": None,
        "createdBy": created_by,
        "message": "",
        "progress": {"percent": 0.0},
        "errorCode": None,
        "errorMessage": None,
        "metadata": metadata or {},
        "cancelRequested": False,
    }
    with _LOCK:
        _TASKS[task_id] = task
    return task


def set_task_status(
    task_id: str,
    status: str,
    *,
    stage: str | None = None,
    message: str | None = None,
    progress: float | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return None
        if status == "running" and task["startedAt"] is None:
            task["startedAt"] = now_utc()
        if status in {"completed", "failed", "cancelled", "partially_completed"}:
            task["finishedAt"] = now_utc()
        task["status"] = status
        if stage is not None:
            task["stage"] = stage
        if message is not None:
            task["message"] = message
        if progress is not None:
            task["progress"] = {"percent": max(0.0, min(100.0, float(progress)))}
        if error_code is not None:
            task["errorCode"] = error_code
        if error_message is not None:
            task["errorMessage"] = error_message
        if metadata is not None:
            task["metadata"] = metadata
        return dict(task)


def request_cancel(task_id: str) -> dict[str, Any] | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return None
        task["cancelRequested"] = True
        if task["status"] in {"created", "queued"}:
            task["status"] = "cancelled"
            task["stage"] = "cancelled"
            task["message"] = "cancelled by user"
            task["finishedAt"] = now_utc()
        elif task["status"] == "running":
            task["message"] = "cancel requested, waiting for current step"
        return dict(task)


def is_cancel_requested(task_id: str) -> bool:
    with _LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return False
        return bool(task.get("cancelRequested"))


def get_task(task_id: str) -> dict[str, Any] | None:
    with _LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return None
        return dict(task)


def list_tasks() -> list[dict[str, Any]]:
    with _LOCK:
        rows = [dict(item) for item in _TASKS.values()]
    rows.sort(key=lambda item: item["createdAt"], reverse=True)
    return rows


def to_task_output(task: dict[str, Any]) -> dict[str, Any]:
    result = dict(task)
    result["createdAt"] = iso_datetime(task.get("createdAt"))
    result["startedAt"] = iso_datetime(task.get("startedAt"))
    result["finishedAt"] = iso_datetime(task.get("finishedAt"))
    return result


def save_db_backup_artifact(task_id: str, *, path: Path, file_name: str, size: int, sha256: str) -> None:
    with _LOCK:
        _DB_BACKUP_FILES[task_id] = {
            "path": str(path),
            "fileName": file_name,
            "size": size,
            "sha256": sha256,
        }


def get_db_backup_artifact(task_id: str) -> dict[str, Any] | None:
    with _LOCK:
        row = _DB_BACKUP_FILES.get(task_id)
        if row is None:
            return None
        return dict(row)


def save_db_restore_upload(*, file_name: str, size: int, sha256: str, content_type: str | None, storage_path: Path) -> str:
    upload_id = new_id("upload")
    with _LOCK:
        _DB_RESTORE_UPLOADS[upload_id] = {
            "uploadFileId": upload_id,
            "fileName": file_name,
            "size": size,
            "sha256": sha256,
            "contentType": content_type,
            "storagePath": str(storage_path),
            "uploadedAt": now_utc(),
        }
    return upload_id


def get_db_restore_upload(upload_id: str) -> dict[str, Any] | None:
    with _LOCK:
        row = _DB_RESTORE_UPLOADS.get(upload_id)
        if row is None:
            return None
        return dict(row)


def save_uploads_manifest(manifest: dict[str, Any]) -> None:
    manifest_id = str(manifest["manifestId"])
    files = manifest.get("files", [])
    with _LOCK:
        _UPLOADS_MANIFESTS[manifest_id] = manifest
        for file_item in files:
            file_id = str(file_item["fileId"])
            _UPLOADS_FILE_INDEX[file_id] = {
                "manifestId": manifest_id,
                "relativePath": str(file_item["relativePath"]),
            }


def get_uploads_manifest(manifest_id: str) -> dict[str, Any] | None:
    with _LOCK:
        row = _UPLOADS_MANIFESTS.get(manifest_id)
        if row is None:
            return None
        return dict(row)


def get_manifest_file(file_id: str) -> dict[str, str] | None:
    with _LOCK:
        row = _UPLOADS_FILE_INDEX.get(file_id)
        if row is None:
            return None
        return dict(row)


def create_uploads_restore_state(task_id: str, *, scope: str, overwrite_mode: str, file_count: int, total_bytes: int) -> None:
    with _LOCK:
        _UPLOADS_RESTORE_TASKS[task_id] = {
            "taskId": task_id,
            "scope": scope,
            "overwriteMode": overwrite_mode,
            "expectedFileCount": int(file_count),
            "expectedTotalBytes": int(total_bytes),
            "summary": {
                "completed": 0,
                "skipped": 0,
                "failed": 0,
                "uploadedBytes": 0,
            },
        }


def get_uploads_restore_state(task_id: str) -> dict[str, Any] | None:
    with _LOCK:
        row = _UPLOADS_RESTORE_TASKS.get(task_id)
        if row is None:
            return None
        return {
            **row,
            "summary": dict(row["summary"]),
        }


def mark_uploads_restore_file(task_id: str, *, outcome: str, file_size: int) -> dict[str, Any] | None:
    with _LOCK:
        row = _UPLOADS_RESTORE_TASKS.get(task_id)
        if row is None:
            return None
        summary = row["summary"]
        if outcome == "completed":
            summary["completed"] += 1
            summary["uploadedBytes"] += max(0, int(file_size))
        elif outcome == "skipped":
            summary["skipped"] += 1
        else:
            summary["failed"] += 1
        return {
            **row,
            "summary": dict(summary),
        }
