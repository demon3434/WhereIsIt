from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import Date, DateTime, Time, create_engine, inspect, text
from sqlalchemy.engine import Connection, make_url
from starlette.background import BackgroundTask

from ..config import settings
from ..database import Base, engine
from ..deps import require_admin
from ..models import User
from ..services.db_executor import DbError, run_backup, run_restore
from ..services.storage import ensure_upload_dir

router = APIRouter(prefix="/api/admin/data", tags=["数据管理"])

BACKUP_VERSION = 1
TABLES_EXPORT_ORDER = [
    "houses",
    "users",
    "user_accessible_houses",
    "categories",
    "tags",
    "locations",
    "items",
    "item_images",
    "item_tags",
    "operation_logs",
]
TABLES_TRUNCATE_ORDER = [
    "item_tags",
    "user_accessible_houses",
    "operation_logs",
    "item_images",
    "items",
    "locations",
    "tags",
    "categories",
    "users",
    "houses",
]


def _db_conn_info() -> tuple[str, str, str, str, str]:
    url = make_url(settings.database_url)
    host = url.host or "db"
    port = str(url.port or 5432)
    user = url.username or settings.postgres_user
    password = url.password or settings.postgres_password
    database = url.database or settings.postgres_db
    return (
        host,
        port,
        user,
        password,
        database,
    )


def _query_db_major_version(database: str) -> int:
    url = make_url(settings.database_url).set(database=database)
    temp_engine = create_engine(url, pool_pre_ping=True)
    try:
        with temp_engine.connect() as conn:
            version_num = conn.execute(text("SHOW server_version_num")).scalar_one_or_none()
            if version_num is not None:
                value = int(str(version_num))
                return value // 10000

            version_text = str(conn.execute(text("SHOW server_version")).scalar_one()).strip()
            major_text = version_text.split(".", maxsplit=1)[0]
            return int(major_text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"无法获取目标数据库版本: {database}. {exc}",
        ) from exc
    finally:
        temp_engine.dispose()


def _extract_pg_tool_major(version_text: str) -> int:
    match = re.search(r"(\d+)(?:\.\d+)?", version_text)
    if not match:
        raise ValueError(f"无法解析 PostgreSQL 工具版本: {version_text}")
    return int(match.group(1))


def _tool_major_version(tool_name: str) -> int:
    try:
        result = subprocess.run([tool_name, "--version"], capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"缺少 PostgreSQL 客户端命令: {tool_name}",
        ) from exc
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0 or not output:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"无法检测 PostgreSQL 客户端版本: {tool_name}",
        )
    try:
        return _extract_pg_tool_major(output)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def _assert_pg_tool_major_matches_db(tool_name: str, database: str) -> None:
    db_major = _query_db_major_version(database)
    tool_major = _tool_major_version(tool_name)
    if db_major != tool_major:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"PostgreSQL 工具版本不匹配: 数据库主版本={db_major}, {tool_name} 主版本={tool_major}。"
                f"请使用与数据库同主版本的客户端工具后重试。"
            ),
        )


def _run_subprocess(
    command: list[str], *, error_message: str, target_database: str | None = None, tool_name: str | None = None
) -> None:
    _, _, _, password, _ = _db_conn_info()
    env = {**os.environ, "PGPASSWORD": password}
    pg_tool = tool_name or (command[0] if command else "")
    if not pg_tool:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无效的子进程命令")
    if target_database:
        _assert_pg_tool_major_matches_db(pg_tool, target_database)
    try:
        result = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="缺少 PostgreSQL 客户端命令，请先在应用镜像安装 postgresql-client",
        ) from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() or error_message
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _parse_datetime(raw: str) -> datetime | str:
    value = str(raw or "").strip()
    if not value:
        return raw
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return raw


def _deserialize_value(value: Any, column_type: Any) -> Any:
    if value is None:
        return None
    if isinstance(column_type, DateTime) and isinstance(value, str):
        return _parse_datetime(value)
    if isinstance(column_type, Date) and isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(column_type, Time) and isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError:
            return value
    return value


def _existing_tables(conn: Connection) -> set[str]:
    return set(inspect(conn).get_table_names())


def _dump_table_rows(conn: Connection, table_name: str) -> list[dict[str, Any]]:
    rows = conn.execute(text(f'SELECT * FROM "{table_name}"')).mappings().all()
    return [{key: _serialize_value(value) for key, value in row.items()} for row in rows]


def _safe_upload_file_path(relative_path: str) -> Path:
    base = Path(settings.upload_dir).resolve()
    candidate = (base / relative_path).resolve()
    if candidate != base and base not in candidate.parents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法路径")
    return candidate


def _normalize_upload_name(filename: str) -> str:
    parts = [part for part in Path(str(filename or "").replace("\\", "/")).parts if part not in ("", ".", "..")]
    if not parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件名无效")
    return "/".join(parts)


def _truncate_tables(conn: Connection) -> None:
    existing = _existing_tables(conn)
    names = [name for name in TABLES_TRUNCATE_ORDER if name in existing]
    if not names:
        return
    quoted = ", ".join(f'"{name}"' for name in names)
    conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))


def _insert_table_rows(conn: Connection, table_name: str, rows: Any) -> None:
    table = Base.metadata.tables.get(table_name)
    if table is None:
        return
    if not isinstance(rows, list) or not rows:
        return

    valid_columns = {column.name: column.type for column in table.columns}
    payload: list[dict[str, Any]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            continue
        row: dict[str, Any] = {}
        for key, value in raw_row.items():
            if key not in valid_columns:
                continue
            row[key] = _deserialize_value(value, valid_columns[key])
        if row:
            payload.append(row)

    if payload:
        conn.execute(table.insert(), payload)


def _reset_table_sequence(conn: Connection, table_name: str) -> None:
    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence(:table_name, 'id'),
                COALESCE((SELECT MAX(id) FROM %s), 0),
                COALESCE((SELECT MAX(id) FROM %s), 0) > 0
            )
            """
            % (f'"{table_name}"', f'"{table_name}"')
        ),
        {"table_name": table_name},
    )


def _reset_sequences(conn: Connection) -> None:
    for table_name in TABLES_EXPORT_ORDER:
        table = Base.metadata.tables.get(table_name)
        if table is None or "id" not in table.columns:
            continue
        _reset_table_sequence(conn, table_name)


def _write_upload_to_temp_file(upload: UploadFile, suffix: str = "") -> str:
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp.name
    try:
        upload.file.seek(0)
        shutil.copyfileobj(upload.file, temp)
    finally:
        temp.close()
    return temp_path


@router.get("/export/db")
def export_database_fast(admin: User = Depends(require_admin)):
    del admin
    _, _, _, _, database = _db_conn_info()

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".dump")
    backup_path = temp.name
    temp.close()

    try:
        run_backup(database, "custom", Path(backup_path))
    except DbError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "errorCode": exc.code,
                "message": str(exc),
                "context": exc.context,
            },
        ) from exc

    filename = f"whereisit-db-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.dump"
    return FileResponse(
        backup_path,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(lambda: Path(backup_path).unlink(missing_ok=True)),
    )


@router.post("/import/db")
async def import_database_fast(file: UploadFile = File(...), admin: User = Depends(require_admin)):
    del admin
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择数据库备份文件")

    suffix = Path(file.filename).suffix.lower()
    temp_path = _write_upload_to_temp_file(file, suffix=suffix)

    _, _, _, _, database = _db_conn_info()
    try:
        run_restore(database, Path(temp_path))
    except DbError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "errorCode": exc.code,
                "message": str(exc),
                "context": exc.context,
            },
        ) from exc
    finally:
        Path(temp_path).unlink(missing_ok=True)

    return {"message": "数据库已通过高性能模式全量还原"}


@router.get("/export/db-json")
def export_database_json(admin: User = Depends(require_admin)):
    del admin
    payload: dict[str, Any] = {
        "version": BACKUP_VERSION,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "app": "WhereIsIt",
        "tables": {},
    }
    with engine.connect() as conn:
        existing = _existing_tables(conn)
        for table_name in TABLES_EXPORT_ORDER:
            if table_name in existing:
                payload["tables"][table_name] = _dump_table_rows(conn, table_name)
            else:
                payload["tables"][table_name] = []

    filename = f"whereisit-db-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    return Response(
        content=json.dumps(payload, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import/db-json")
async def import_database_json(file: UploadFile = File(...), admin: User = Depends(require_admin)):
    del admin
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择 JSON 备份文件")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备份文件为空")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备份文件格式错误，仅支持 JSON") from exc

    tables = payload.get("tables") if isinstance(payload, dict) else None
    if not isinstance(tables, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="备份文件缺少 tables 字段")

    with engine.begin() as conn:
        _truncate_tables(conn)
        for table_name in TABLES_EXPORT_ORDER:
            _insert_table_rows(conn, table_name, tables.get(table_name, []))
        _reset_sequences(conn)

    return {"message": "数据库已通过 JSON 模式全量还原"}


@router.get("/export/images/manifest")
def export_images_manifest(admin: User = Depends(require_admin)):
    del admin
    ensure_upload_dir()
    base = Path(settings.upload_dir)
    files = [path for path in base.rglob("*") if path.is_file()]
    files.sort(key=lambda path: str(path.relative_to(base)).replace("\\", "/"))
    result = [
        {
            "path": str(path.relative_to(base)).replace("\\", "/"),
            "size": path.stat().st_size,
        }
        for path in files
    ]
    return {"count": len(result), "files": result}


@router.get("/export/images/download")
def export_image_file(path: str = Query(...), admin: User = Depends(require_admin)):
    del admin
    normalized = _normalize_upload_name(path)
    target = _safe_upload_file_path(normalized)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    return FileResponse(str(target), media_type="application/octet-stream", filename=target.name)


@router.post("/import/images")
async def import_images(
    files: list[UploadFile] = File(...),
    conflict: str = Query(default="overwrite"),
    admin: User = Depends(require_admin),
):
    del admin
    if conflict not in {"overwrite", "skip", "rename"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="冲突策略非法")

    ensure_upload_dir()
    saved = 0
    skipped = 0
    renamed = 0
    base = Path(settings.upload_dir).resolve()

    for upload in files:
        name = upload.filename or ""
        normalized = _normalize_upload_name(name)
        target = _safe_upload_file_path(normalized)
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            if conflict == "skip":
                skipped += 1
                continue
            if conflict == "rename":
                stem = target.stem
                suffix = target.suffix
                counter = 1
                while True:
                    candidate = target.with_name(f"{stem}_{counter}{suffix}")
                    if not candidate.exists():
                        target = candidate
                        renamed += 1
                        break
                    counter += 1

        with target.open("wb") as output:
            shutil.copyfileobj(upload.file, output)
        saved += 1

    total_files = len(files)
    return {
        "message": "图片导入完成",
        "total": total_files,
        "saved": saved,
        "skipped": skipped,
        "renamed": renamed,
        "target_dir": str(base),
    }
