from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ..config import settings


@dataclass
class DbError(RuntimeError):
    code: str
    message: str
    context: dict[str, Any]

    def __str__(self) -> str:
        return self.message


@dataclass
class ServerVersion:
    server_version: str
    server_version_num: int
    resolved_major: int


@dataclass
class ExecutionPlan:
    can_proceed: bool
    blocking_reason: str | None
    server_version: str
    server_version_num: int
    resolved_major: int
    selected_strategy: str | None
    selected_tools_image: str | None
    warnings: list[str]
    container_name: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "serverVersion": self.server_version,
            "serverVersionNum": self.server_version_num,
            "resolvedMajor": self.resolved_major,
            "selectedStrategy": self.selected_strategy,
            "selectedToolsImage": self.selected_tools_image,
            "warnings": self.warnings,
            "canProceed": self.can_proceed,
            "blockingReason": self.blocking_reason,
        }


def _db_conn_info(database: str | None = None) -> tuple[str, str, str, str, str]:
    url = make_url(settings.database_url)
    host = url.host or "db"
    port = str(url.port or 5432)
    user = url.username or settings.postgres_user
    password = url.password or settings.postgres_password
    db_name = database or (url.database or settings.postgres_db)
    return host, port, user, password, db_name


def detect_server_version(database: str | None = None) -> ServerVersion:
    target_db = (database or "").strip() or _db_conn_info()[4]
    url = make_url(settings.database_url).set(database=target_db)
    temp_engine = create_engine(url, pool_pre_ping=True)
    try:
        with temp_engine.connect() as conn:
            version_num_raw = conn.execute(text("SHOW server_version_num")).scalar_one_or_none()
            version_text_raw = conn.execute(text("SHOW server_version")).scalar_one_or_none()
    except Exception as exc:
        raise DbError(
            "PG_SERVER_VERSION_DETECT_FAILED",
            f"failed to detect PostgreSQL server version for database '{target_db}': {exc}",
            {"database": target_db},
        ) from exc
    finally:
        temp_engine.dispose()

    try:
        version_num = int(str(version_num_raw))
    except Exception:
        version_num = 0
    version_text = str(version_text_raw or "").strip()
    major = version_num // 10000 if version_num > 0 else _extract_major_from_version(version_text)
    return ServerVersion(server_version=version_text, server_version_num=version_num, resolved_major=major)


def _extract_major_from_version(version_text: str) -> int:
    match = re.search(r"(\d+)", version_text)
    if not match:
        raise DbError(
            "PG_SERVER_VERSION_DETECT_FAILED",
            f"unable to parse PostgreSQL server version text: '{version_text}'",
            {"serverVersion": version_text},
        )
    return int(match.group(1))


def _extract_tool_major(version_text: str) -> int:
    match = re.search(r"(\d+)(?:\.\d+)?", version_text)
    if not match:
        raise ValueError(f"unable to parse PostgreSQL tool version: {version_text}")
    return int(match.group(1))


def _run_capture(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, env=env, check=False)


def _require_docker_available() -> None:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise RuntimeError("docker command is not available")
    probe = _run_capture([docker_bin, "version", "--format", "{{.Server.Version}}"])
    if probe.returncode != 0:
        detail = (probe.stderr or probe.stdout or "").strip()
        raise RuntimeError(f"docker daemon is unreachable: {detail or 'unknown error'}")


def _container_exists(container_name: str) -> bool:
    if not container_name:
        return False
    result = _run_capture(["docker", "inspect", container_name])
    return result.returncode == 0


def _container_from_service_label(service_name: str) -> str | None:
    if not service_name:
        return None
    result = _run_capture(
        [
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.service={service_name}",
            "--format",
            "{{.Names}}",
        ]
    )
    if result.returncode != 0:
        return None
    names = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return names[0] if names else None


def _resolve_pg_container_name() -> str:
    configured_name = str(settings.pg_container_name or "").strip()
    if configured_name and _container_exists(configured_name):
        return configured_name
    by_service = _container_from_service_label(str(settings.pg_service_name or "").strip())
    if by_service:
        return by_service
    if configured_name:
        return configured_name
    raise RuntimeError("unable to locate PostgreSQL container")


def _determine_candidates(exec_mode: str, *, allow_local_fallback: bool) -> list[str]:
    mode = (exec_mode or "auto").strip().lower()
    if mode == "auto":
        return ["docker_exec", "docker_run_tools", "local"] if allow_local_fallback else ["docker_exec", "docker_run_tools"]
    if mode in {"docker_exec", "docker_run_tools", "local"}:
        if mode == "local" and not allow_local_fallback:
            return []
        return [mode]
    return ["docker_exec", "docker_run_tools", "local"] if allow_local_fallback else ["docker_exec", "docker_run_tools"]


def _tool_version_for_local(tool_name: str) -> tuple[int, str]:
    result = _run_capture([tool_name, "--version"])
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"failed to detect local {tool_name} version: {detail or 'unknown error'}")
    text = (result.stdout or result.stderr or "").strip()
    return _extract_tool_major(text), text


def _render_image(template: str, major: int) -> str:
    return template.format(major=major)


def _looks_like_image_not_found(stderr_text: str) -> bool:
    text_lower = stderr_text.lower()
    return (
        "manifest unknown" in text_lower
        or "not found" in text_lower
        or "pull access denied" in text_lower
        or "repository does not exist" in text_lower
    )


def resolve_execution_plan(database: str | None = None, *, allow_local_fallback: bool = True) -> ExecutionPlan:
    version = detect_server_version(database)
    warnings: list[str] = []
    if version.resolved_major > int(settings.pg_tested_max_major):
        warnings.append(
            f"UNTESTED_MAJOR_VERSION: server major {version.resolved_major} is greater than tested max {settings.pg_tested_max_major}"
        )

    candidates = _determine_candidates(settings.pg_exec_mode, allow_local_fallback=allow_local_fallback)
    errors: list[str] = []
    selected_strategy: str | None = None
    selected_tools_image: str | None = None
    container_name: str | None = None

    if not candidates:
        return ExecutionPlan(
            can_proceed=False,
            blocking_reason="local strategy is disabled for this endpoint, but PG_EXEC_MODE is set to local",
            server_version=version.server_version,
            server_version_num=version.server_version_num,
            resolved_major=version.resolved_major,
            selected_strategy=None,
            selected_tools_image=None,
            warnings=warnings,
            container_name=container_name,
        )

    for strategy in candidates:
        try:
            if strategy in {"docker_exec", "docker_run_tools"}:
                _require_docker_available()
                container_name = _resolve_pg_container_name()
            if strategy == "local":
                tool_major, _ = _tool_version_for_local("pg_dump")
                if tool_major != version.resolved_major:
                    raise RuntimeError(
                        f"local pg_dump major {tool_major} does not match server major {version.resolved_major}"
                    )
            if strategy == "docker_run_tools":
                selected_tools_image = _render_image(settings.pg_tools_image_template, version.resolved_major)
            selected_strategy = strategy
            break
        except Exception as exc:
            errors.append(f"{strategy}: {exc}")

    if not selected_strategy:
        return ExecutionPlan(
            can_proceed=False,
            blocking_reason="; ".join(errors) or "no usable execution strategy",
            server_version=version.server_version,
            server_version_num=version.server_version_num,
            resolved_major=version.resolved_major,
            selected_strategy=None,
            selected_tools_image=None,
            warnings=warnings,
            container_name=container_name,
        )

    return ExecutionPlan(
        can_proceed=True,
        blocking_reason=None,
        server_version=version.server_version,
        server_version_num=version.server_version_num,
        resolved_major=version.resolved_major,
        selected_strategy=selected_strategy,
        selected_tools_image=selected_tools_image,
        warnings=warnings,
        container_name=container_name,
    )


def _run_stdout_to_file(command: list[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output_handle:
        process = subprocess.Popen(command, stdout=output_handle, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
    if process.returncode != 0:
        error_text = (stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(error_text or "command failed")


def _run_file_to_stdin(command: list[str], input_path: Path) -> None:
    with input_path.open("rb") as input_handle:
        process = subprocess.Popen(command, stdin=input_handle, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
    if process.returncode != 0:
        error_text = (stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(error_text or "command failed")


def _local_env_with_password(password: str) -> dict[str, str]:
    return {**os.environ, "PGPASSWORD": password}


def _run_local_capture(command: list[str], password: str) -> subprocess.CompletedProcess[str]:
    return _run_capture(command, env=_local_env_with_password(password))


def _run_local_backup(command: list[str], password: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, env=_local_env_with_password(password), check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or "pg_dump failed")


def _run_local_restore(command: list[str], password: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True, env=_local_env_with_password(password), check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or "restore failed")


def _tool_version_from_strategy(plan: ExecutionPlan, tool_name: str, password: str) -> str:
    strategy = plan.selected_strategy
    if strategy == "docker_exec":
        command = [
            "docker",
            "exec",
            "-e",
            f"PGPASSWORD={password}",
            str(plan.container_name),
            tool_name,
            "--version",
        ]
        result = _run_capture(command)
    elif strategy == "docker_run_tools":
        image = str(plan.selected_tools_image)
        command = ["docker", "run", "--rm", image, tool_name, "--version"]
        result = _run_capture(command)
        if result.returncode != 0 and plan.selected_tools_image:
            fallback_image = _render_image(settings.pg_tools_image_fallback_template, plan.resolved_major)
            fallback_result = _run_capture(["docker", "run", "--rm", fallback_image, tool_name, "--version"])
            if fallback_result.returncode == 0:
                plan.selected_tools_image = fallback_image
                result = fallback_result
    else:
        result = _run_local_capture([tool_name, "--version"], password)

    if result.returncode != 0:
        return ""
    return (result.stdout or result.stderr or "").strip()


def run_backup(database: str | None, fmt: str, output_path: Path, *, allow_local_fallback: bool = True) -> dict[str, Any]:
    plan = resolve_execution_plan(database, allow_local_fallback=allow_local_fallback)
    if not plan.can_proceed:
        raise DbError(
            "PG_BACKUP_PREFLIGHT_FAILED",
            plan.blocking_reason or "backup preflight failed",
            plan.to_dict(),
        )

    host, port, user, password, db_name = _db_conn_info(database)
    format_value = (fmt or "custom").strip().lower()
    if format_value == "sql":
        format_value = "plain"
    fmt_flag = "-Fc" if format_value == "custom" else "-Fp"
    common_args = [
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "-d",
        db_name,
        fmt_flag,
        "--no-owner",
        "--no-acl",
    ]
    fallback_used = False

    try:
        if plan.selected_strategy == "docker_exec":
            command = [
                "docker",
                "exec",
                "-e",
                f"PGPASSWORD={password}",
                str(plan.container_name),
                "pg_dump",
                "-h",
                "127.0.0.1",
                "-p",
                "5432",
                "-U",
                user,
                "-d",
                db_name,
                fmt_flag,
                "--no-owner",
                "--no-acl",
                "-f",
                "-",
            ]
            _run_stdout_to_file(command, output_path)
        elif plan.selected_strategy == "docker_run_tools":
            primary_image = _render_image(settings.pg_tools_image_template, plan.resolved_major)
            fallback_image = _render_image(settings.pg_tools_image_fallback_template, plan.resolved_major)
            images = [primary_image] if primary_image == fallback_image else [primary_image, fallback_image]
            last_error = ""
            for idx, image in enumerate(images):
                command = [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    f"container:{plan.container_name}",
                    "-e",
                    f"PGPASSWORD={password}",
                    image,
                    "pg_dump",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    "5432",
                    "-U",
                    user,
                    "-d",
                    db_name,
                    fmt_flag,
                    "--no-owner",
                    "--no-acl",
                    "-f",
                    "-",
                ]
                try:
                    _run_stdout_to_file(command, output_path)
                    plan.selected_tools_image = image
                    fallback_used = idx > 0
                    last_error = ""
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if idx == 0 and _looks_like_image_not_found(last_error):
                        continue
                    if idx > 0 and _looks_like_image_not_found(last_error):
                        raise DbError("PG_TOOLS_IMAGE_NOT_FOUND", last_error, {**plan.to_dict(), "database": db_name})
                    raise
            if last_error:
                raise RuntimeError(last_error)
        else:
            command = ["pg_dump", *common_args, "-f", str(output_path)]
            _run_local_backup(command, password)
    except DbError:
        raise
    except Exception as exc:
        raise DbError(
            "PG_DUMP_FAILED",
            str(exc),
            {**plan.to_dict(), "database": db_name},
        ) from exc

    tool_version = _tool_version_from_strategy(plan, "pg_dump", password)
    return {
        **plan.to_dict(),
        "database": db_name,
        "toolVersion": tool_version,
        "strategy": plan.selected_strategy,
        "fallbackUsed": fallback_used,
    }


def run_restore(database: str | None, source_file: Path, *, allow_local_fallback: bool = True) -> dict[str, Any]:
    plan = resolve_execution_plan(database, allow_local_fallback=allow_local_fallback)
    if not plan.can_proceed:
        raise DbError(
            "PG_RESTORE_PREFLIGHT_FAILED",
            plan.blocking_reason or "restore preflight failed",
            plan.to_dict(),
        )

    host, port, user, password, db_name = _db_conn_info(database)
    suffix = source_file.suffix.lower()
    is_sql = suffix == ".sql"
    fallback_used = False

    try:
        if plan.selected_strategy == "docker_exec":
            if is_sql:
                command = [
                    "docker",
                    "exec",
                    "-i",
                    "-e",
                    f"PGPASSWORD={password}",
                    str(plan.container_name),
                    "psql",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    "5432",
                    "-U",
                    user,
                    "-d",
                    db_name,
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-f",
                    "-",
                ]
            else:
                command = [
                    "docker",
                    "exec",
                    "-i",
                    "-e",
                    f"PGPASSWORD={password}",
                    str(plan.container_name),
                    "pg_restore",
                    "-h",
                    "127.0.0.1",
                    "-p",
                    "5432",
                    "-U",
                    user,
                    "-d",
                    db_name,
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-acl",
                    "--single-transaction",
                    "-",
                ]
            _run_file_to_stdin(command, source_file)
        elif plan.selected_strategy == "docker_run_tools":
            primary_image = _render_image(settings.pg_tools_image_template, plan.resolved_major)
            fallback_image = _render_image(settings.pg_tools_image_fallback_template, plan.resolved_major)
            images = [primary_image] if primary_image == fallback_image else [primary_image, fallback_image]
            last_error = ""
            for idx, image in enumerate(images):
                if is_sql:
                    tool_args = [
                        "psql",
                        "-h",
                        "127.0.0.1",
                        "-p",
                        "5432",
                        "-U",
                        user,
                        "-d",
                        db_name,
                        "-v",
                        "ON_ERROR_STOP=1",
                        "-f",
                        "-",
                    ]
                else:
                    tool_args = [
                        "pg_restore",
                        "-h",
                        "127.0.0.1",
                        "-p",
                        "5432",
                        "-U",
                        user,
                        "-d",
                        db_name,
                        "--clean",
                        "--if-exists",
                        "--no-owner",
                        "--no-acl",
                        "--single-transaction",
                        "-",
                    ]
                command = [
                    "docker",
                    "run",
                    "--rm",
                    "-i",
                    "--network",
                    f"container:{plan.container_name}",
                    "-e",
                    f"PGPASSWORD={password}",
                    image,
                    *tool_args,
                ]
                try:
                    _run_file_to_stdin(command, source_file)
                    plan.selected_tools_image = image
                    fallback_used = idx > 0
                    last_error = ""
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if idx == 0 and _looks_like_image_not_found(last_error):
                        continue
                    if idx > 0 and _looks_like_image_not_found(last_error):
                        raise DbError("PG_TOOLS_IMAGE_NOT_FOUND", last_error, {**plan.to_dict(), "database": db_name})
                    raise
            if last_error:
                raise RuntimeError(last_error)
        else:
            if is_sql:
                command = [
                    "psql",
                    "-h",
                    host,
                    "-p",
                    port,
                    "-U",
                    user,
                    "-d",
                    db_name,
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-f",
                    str(source_file),
                ]
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
                    db_name,
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--no-acl",
                    "--single-transaction",
                    str(source_file),
                ]
            _run_local_restore(command, password)
    except DbError:
        raise
    except Exception as exc:
        raise DbError(
            "PG_RESTORE_FAILED",
            str(exc),
            {**plan.to_dict(), "database": db_name},
        ) from exc

    tool_name = "psql" if is_sql else "pg_restore"
    tool_version = _tool_version_from_strategy(plan, tool_name, password)
    return {
        **plan.to_dict(),
        "database": db_name,
        "toolVersion": tool_version,
        "strategy": plan.selected_strategy,
        "fallbackUsed": fallback_used,
    }
