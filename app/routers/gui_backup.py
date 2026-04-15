from __future__ import annotations

import shutil
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..config import settings
from ..deps import require_admin
from ..models import User
from ..routers.data_management import _db_conn_info, _run_subprocess
from ..services.gui_backup import (
    TEMP_ROOT,
    create_task,
    create_uploads_restore_state,
    get_db_backup_artifact,
    get_db_restore_upload,
    get_manifest_file,
    get_task,
    get_uploads_manifest,
    get_uploads_restore_state,
    is_cancel_requested,
    list_tasks,
    mark_uploads_restore_file,
    new_id,
    request_cancel,
    save_db_backup_artifact,
    save_db_restore_upload,
    save_uploads_manifest,
    set_task_status,
    sha256_file,
    to_task_output,
)

router = APIRouter(prefix="/api", tags=["GUI备份恢复"])


def _ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def _ensure_within(base: Path, target: Path) -> Path:
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    if target_resolved != base_resolved and base_resolved not in target_resolved.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid relative path")
    return target_resolved


def _run_db_backup_task(task_id: str, db_name: str, fmt: str) -> None:
    try:
        if is_cancel_requested(task_id):
            set_task_status(task_id, "cancelled", stage="cancelled", message="cancelled by user", progress=0)
            return
        set_task_status(task_id, "running", stage="db_backup", message="exporting database", progress=10)
        host, port, user, _, default_database = _db_conn_info()
        database = db_name.strip() or default_database

        backup_path = TEMP_ROOT / f"{task_id}.dump"
        command = [
            "pg_dump",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            database,
            "-Fc" if fmt == "custom" else "-Fp",
            "--no-owner",
            "--no-privileges",
            "-f",
            str(backup_path),
        ]
        _run_subprocess(command, error_message="数据库备份失败", target_database=database, tool_name="pg_dump")
        if not backup_path.exists():
            raise RuntimeError("backup output missing")

        file_name = f"whereisit-db-backup-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}{backup_path.suffix or '.dump'}"
        file_size = backup_path.stat().st_size
        file_hash = sha256_file(backup_path)
        save_db_backup_artifact(task_id, path=backup_path, file_name=file_name, size=file_size, sha256=file_hash)
        set_task_status(
            task_id,
            "completed",
            stage="completed",
            message="backup completed",
            progress=100,
            metadata={"fileName": file_name, "size": file_size, "sha256": file_hash},
        )
    except HTTPException as exc:
        set_task_status(
            task_id,
            "failed",
            stage="failed",
            message="backup failed",
            progress=100,
            error_code="DB_BACKUP_FAILED",
            error_message=str(exc.detail),
        )
    except Exception as exc:
        set_task_status(
            task_id,
            "failed",
            stage="failed",
            message="backup failed",
            progress=100,
            error_code="DB_BACKUP_FAILED",
            error_message=str(exc),
        )


def _run_db_restore_task(task_id: str, upload_file_id: str, target_db_name: str) -> None:
    try:
        upload = get_db_restore_upload(upload_file_id)
        if upload is None:
            raise RuntimeError("upload file not found")
        if is_cancel_requested(task_id):
            set_task_status(task_id, "cancelled", stage="cancelled", message="cancelled by user", progress=0)
            return

        set_task_status(task_id, "running", stage="db_restore", message="restoring database", progress=10)
        source_file = Path(str(upload["storagePath"]))
        if not source_file.exists():
            raise RuntimeError("restore source file missing")

        host, port, user, _, default_database = _db_conn_info()
        database = target_db_name.strip() or default_database
        suffix = source_file.suffix.lower()
        if suffix == ".sql":
            command = [
                "psql",
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                database,
                "-v",
                "ON_ERROR_STOP=1",
                "-f",
                str(source_file),
            ]
            _run_subprocess(command, error_message="SQL 备份导入失败", target_database=database, tool_name="psql")
        else:
            command = [
                "pg_restore",
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                database,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--single-transaction",
                str(source_file),
            ]
            _run_subprocess(
                command,
                error_message="数据库还原失败",
                target_database=database,
                tool_name="pg_restore",
            )

        set_task_status(task_id, "completed", stage="completed", message="restore completed", progress=100)
    except HTTPException as exc:
        set_task_status(
            task_id,
            "failed",
            stage="failed",
            message="restore failed",
            progress=100,
            error_code="DB_RESTORE_FAILED",
            error_message=str(exc.detail),
        )
    except Exception as exc:
        set_task_status(
            task_id,
            "failed",
            stage="failed",
            message="restore failed",
            progress=100,
            error_code="DB_RESTORE_FAILED",
            error_message=str(exc),
        )


@router.get("/tasks")
def api_list_tasks(admin: User = Depends(require_admin)):
    del admin
    return _ok({"items": [to_task_output(task) for task in list_tasks()]})


@router.get("/tasks/{task_id}")
def api_get_task(task_id: str, admin: User = Depends(require_admin)):
    del admin
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return _ok(to_task_output(task))


@router.post("/tasks/{task_id}/cancel")
def api_cancel_task(task_id: str, admin: User = Depends(require_admin)):
    del admin
    task = request_cancel(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return _ok({"taskId": task["taskId"], "status": task["status"]})


@router.post("/backup/database")
def api_create_db_backup(payload: dict[str, Any], admin: User = Depends(require_admin)):
    fmt = str(payload.get("format", "custom")).strip().lower()
    if fmt not in {"custom", "plain", "sql"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be custom/plain/sql")
    db_name = str(payload.get("dbName", "")).strip()

    task = create_task("db_backup", admin.username, metadata={"dbName": db_name, "format": fmt})
    set_task_status(task["taskId"], "queued", stage="queued", message="backup queued", progress=1)
    threading.Thread(target=_run_db_backup_task, args=(task["taskId"], db_name, fmt), daemon=True).start()
    return _ok({"taskId": task["taskId"], "status": "queued"})


@router.get("/backup/database/{task_id}/download")
def api_download_db_backup(task_id: str, admin: User = Depends(require_admin)):
    del admin
    artifact = get_db_backup_artifact(task_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="backup artifact not found")
    file_path = Path(str(artifact["path"]))
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="backup file missing")
    return FileResponse(str(file_path), filename=str(artifact["fileName"]), media_type="application/octet-stream")


@router.get("/backup/database/{task_id}/metadata")
def api_db_backup_metadata(task_id: str, admin: User = Depends(require_admin)):
    del admin
    artifact = get_db_backup_artifact(task_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task detail not found")
    return _ok(
        {
            "taskId": task_id,
            "fileName": artifact["fileName"],
            "size": artifact["size"],
            "sha256": artifact["sha256"],
            "metadata": {},
        }
    )


@router.post("/restore/database/upload")
async def api_upload_db_restore_file(file: UploadFile = File(...), admin: User = Depends(require_admin)):
    del admin
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择备份文件")
    suffix = Path(file.filename).suffix or ".dump"
    temp_path = TEMP_ROOT / f"{new_id('dbupload')}{suffix}"
    with temp_path.open("wb") as output:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    file_hash = sha256_file(temp_path)
    file_size = temp_path.stat().st_size
    upload_id = save_db_restore_upload(
        file_name=file.filename,
        size=file_size,
        sha256=file_hash,
        content_type=file.content_type,
        storage_path=temp_path,
    )
    return _ok({"uploadFileId": upload_id, "fileName": file.filename, "size": file_size, "sha256": file_hash})


@router.post("/restore/database")
def api_create_db_restore(payload: dict[str, Any], admin: User = Depends(require_admin)):
    upload_file_id = str(payload.get("uploadFileId", "")).strip()
    target_db_name = str(payload.get("targetDbName", "")).strip()
    restore_mode = str(payload.get("restoreMode", "drop_and_restore")).strip()
    confirm_text = str(payload.get("confirmText", "")).strip()

    if not upload_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="uploadFileId is required")
    if restore_mode == "drop_and_restore" and confirm_text != "CONFIRM RESTORE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="restore requires confirm text: CONFIRM RESTORE")

    upload = get_db_restore_upload(upload_file_id)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="upload file not found")

    task = create_task(
        "db_restore",
        admin.username,
        metadata={"uploadFileId": upload_file_id, "targetDbName": target_db_name, "restoreMode": restore_mode},
    )
    set_task_status(task["taskId"], "queued", stage="queued", message="restore queued", progress=1)
    threading.Thread(
        target=_run_db_restore_task,
        args=(task["taskId"], upload_file_id, target_db_name),
        daemon=True,
    ).start()
    return _ok({"taskId": task["taskId"], "status": "queued"})


@router.post("/backup/uploads/create-manifest")
def api_create_uploads_manifest(payload: dict[str, Any], admin: User = Depends(require_admin)):
    del admin
    scope = str(payload.get("scope", "images")).strip() or "images"
    incremental = bool(payload.get("incremental", False))
    modified_after_value = payload.get("modifiedAfter")
    modified_after: datetime | None = None
    if isinstance(modified_after_value, datetime):
        modified_after = modified_after_value.astimezone(UTC)
    elif modified_after_value is not None:
        modified_after_raw = str(modified_after_value).strip()
        if modified_after_raw and modified_after_raw.lower() != "null":
            text = modified_after_raw.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(text)
                modified_after = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="modifiedAfter must be ISO datetime") from exc

    base = Path(settings.upload_dir)
    base.mkdir(parents=True, exist_ok=True)
    manifest_id = new_id("manifest")
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        if modified_after is not None and modified_at <= modified_after.astimezone(UTC):
            continue
        relative = str(path.relative_to(base)).replace("\\", "/")
        file_id = new_id("file")
        size = path.stat().st_size
        total_bytes += size
        files.append(
            {
                "fileId": file_id,
                "relativePath": relative,
                "size": size,
                "sha256": sha256_file(path),
                "modifiedAt": modified_at.isoformat().replace("+00:00", "Z"),
                "downloadUrl": f"/api/backup/uploads/file/{file_id}",
                "supportsRange": True,
            }
        )
    manifest = {
        "manifestVersion": "1.0",
        "manifestId": manifest_id,
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "scope": scope,
        "isIncremental": incremental,
        "fileCount": len(files),
        "totalBytes": total_bytes,
        "files": files,
    }
    save_uploads_manifest(manifest)
    return _ok(manifest)


@router.get("/backup/uploads/manifest/{manifest_id}")
def api_get_uploads_manifest(manifest_id: str, admin: User = Depends(require_admin)):
    del admin
    manifest = get_uploads_manifest(manifest_id)
    if manifest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="manifest not found")
    return _ok(manifest)


@router.get("/backup/uploads/file/{file_id}")
def api_download_upload_file(file_id: str, admin: User = Depends(require_admin)):
    del admin
    item = get_manifest_file(file_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file not found")
    relative_path = str(item["relativePath"])
    source_file = _ensure_within(Path(settings.upload_dir), Path(settings.upload_dir) / relative_path)
    if not source_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source file missing")
    return FileResponse(str(source_file), filename=source_file.name, media_type="application/octet-stream")


@router.post("/restore/uploads/create-task")
def api_create_uploads_restore_task(payload: dict[str, Any], admin: User = Depends(require_admin)):
    scope = str(payload.get("scope", "images")).strip() or "images"
    overwrite_mode = str(payload.get("overwriteMode", "skip_if_exists")).strip()
    if overwrite_mode not in {"skip_if_exists", "overwrite_if_exists", "overwrite_if_newer"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid overwriteMode")
    file_count = int(payload.get("fileCount", 0))
    total_bytes = int(payload.get("totalBytes", 0))

    task = create_task(
        "uploads_restore",
        admin.username,
        metadata={"scope": scope, "overwriteMode": overwrite_mode, "expectedFileCount": file_count, "expectedTotalBytes": total_bytes},
    )
    create_uploads_restore_state(
        task["taskId"],
        scope=scope,
        overwrite_mode=overwrite_mode,
        file_count=file_count,
        total_bytes=total_bytes,
    )
    set_task_status(task["taskId"], "running", stage="receiving_files", message="ready_for_upload", progress=0)
    return _ok({"taskId": task["taskId"], "status": "running"})


@router.post("/restore/uploads/{task_id}/upload-file")
async def api_upload_restore_file(
    task_id: str,
    relativePath: str = Form(...),
    sha256: str = Form(default=""),
    size: int = Form(default=0),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
):
    del admin
    state = get_uploads_restore_state(task_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")

    base = Path(settings.upload_dir)
    base.mkdir(parents=True, exist_ok=True)
    relative = str(relativePath or "").replace("\\", "/").strip().lstrip("/")
    if not relative:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relativePath is required")
    target = _ensure_within(base, base / relative)
    target.parent.mkdir(parents=True, exist_ok=True)

    exists = target.exists()
    if exists and state["overwriteMode"] == "skip_if_exists":
        updated = mark_uploads_restore_file(task_id, outcome="skipped", file_size=0)
        if updated:
            summary = updated["summary"]
            expected = max(1, int(updated["expectedFileCount"]))
            processed = int(summary["completed"]) + int(summary["skipped"]) + int(summary["failed"])
            set_task_status(task_id, "running", stage="receiving_files", progress=(processed / expected) * 100)
        return _ok({"relativePath": relative, "status": "skipped"})

    if exists and state["overwriteMode"] == "overwrite_if_newer":
        # No remote modifiedAt in API contract, fallback to overwrite behavior.
        pass

    temp_output = Path(tempfile.NamedTemporaryFile(delete=False, dir=str(TEMP_ROOT), suffix=".upload").name)
    try:
        with temp_output.open("wb") as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)

        actual_size = temp_output.stat().st_size
        actual_hash = sha256_file(temp_output)
        if size > 0 and actual_size != size:
            mark_uploads_restore_file(task_id, outcome="failed", file_size=0)
            return {"code": 1, "message": "verify failed", "data": {"relativePath": relative, "status": "failed"}}
        if sha256 and actual_hash != sha256:
            mark_uploads_restore_file(task_id, outcome="failed", file_size=0)
            return {"code": 1, "message": "verify failed", "data": {"relativePath": relative, "status": "failed"}}

        shutil.move(str(temp_output), str(target))
        target.chmod(0o644)
        updated = mark_uploads_restore_file(task_id, outcome="completed", file_size=actual_size)
        if updated:
            summary = updated["summary"]
            expected = max(1, int(updated["expectedFileCount"]))
            processed = int(summary["completed"]) + int(summary["skipped"]) + int(summary["failed"])
            set_task_status(task_id, "running", stage="receiving_files", progress=(processed / expected) * 100)
        return _ok({"relativePath": relative, "status": "completed"})
    finally:
        temp_output.unlink(missing_ok=True)


@router.post("/restore/uploads/{task_id}/complete")
def api_complete_uploads_restore(task_id: str, payload: dict[str, Any], admin: User = Depends(require_admin)):
    del payload
    del admin
    state = get_uploads_restore_state(task_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    summary = state["summary"]
    if int(summary["failed"]) > 0:
        status_name = "partially_completed"
        message = "completed with failures"
    else:
        status_name = "completed"
        message = "completed"
    set_task_status(task_id, status_name, stage="completed", message=message, progress=100, metadata={"summary": summary})
    return _ok({"taskId": task_id, "summary": summary})
