import asyncio
import json
import logging
from typing import Any
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import func, select, text

from .auth import hash_password
from .config import settings
from .database import Base, SessionLocal, engine
from .deps import get_current_user_optional
from .models import House, Item, User, VoiceSearchTerm
from .routers import admin_users, auth, categories, data_management, gui_backup, houses, items, rooms, tags, users, voice_search
from .services.mdns import ServiceDiscoveryBroadcaster
from .services.storage import ensure_upload_dir
from .services.voice_search import (
    ensure_voice_cleaning_lexicon_files,
    get_offline_asr_service,
    get_streaming_asr_service,
    mark_all_items_voice_terms_dirty,
    start_voice_term_index_worker,
    stop_voice_term_index_worker,
)

app = FastAPI(title="WhereIsIt", version="1.0.0")
broadcaster = ServiceDiscoveryBroadcaster()
logger = logging.getLogger(__name__)
app_dir = Path(__file__).resolve().parent
static_dir = app_dir / "static"
templates_dir = app_dir / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
admin_allowed_paths = {"/items", "/locations", "/categories", "/tags", "/users", "/profile"}
user_allowed_paths = {"/items"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")] if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def _ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def _error(status_code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": status_code, "message": message, "data": data}


def _is_envelope(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return "code" in payload and "message" in payload and "data" in payload


@app.middleware("http")
async def api_envelope_middleware(request: Request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        return response
    if isinstance(response, (FileResponse, RedirectResponse)):
        return response

    content_disposition = str(response.headers.get("content-disposition", "")).lower()
    if "attachment" in content_disposition:
        return response

    media_type = str(response.media_type or response.headers.get("content-type", "")).lower()
    if "application/json" not in media_type:
        return response
    if response.status_code >= 400:
        return response

    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)
    body = b"".join(chunks).strip()

    if not body:
        payload: Any = None
    else:
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return response

    content = payload if _is_envelope(payload) else _ok(payload)
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return JSONResponse(
        status_code=response.status_code,
        content=content,
        headers=headers,
    )


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code != status.HTTP_404_NOT_FOUND:
        if request.url.path.startswith("/api/"):
            detail = exc.detail
            if isinstance(detail, str):
                return JSONResponse(status_code=exc.status_code, content=_error(exc.status_code, detail))
            return JSONResponse(status_code=exc.status_code, content=_error(exc.status_code, "Request failed", detail))
        return HTMLResponse(content=str(exc.detail), status_code=exc.status_code)
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=exc.status_code, content=_error(exc.status_code, "Not Found"))
    return FileResponse(str(templates_dir / "not_found.html"), status_code=status.HTTP_404_NOT_FOUND)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Validation Error", exc.errors()),
        )
    return HTMLResponse(content="Validation Error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", exc_info=exc)
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal Server Error"),
        )
    return HTMLResponse(content="Internal Server Error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)
    run_postgres_migrations()
    ensure_upload_dir()
    ensure_voice_cleaning_lexicon_files()
    db = SessionLocal()
    try:
        exists = db.scalar(select(User).where(User.username == settings.default_admin_username))
        if not exists:
            exists = User(
                username=settings.default_admin_username,
                nickname=settings.default_admin_nickname,
                full_name=settings.default_admin_nickname,
                password_hash=hash_password(settings.default_admin_password),
                role="admin",
                is_active=True,
            )
            db.add(exists)
            db.flush()
        else:
            exists.role = "admin"
            exists.is_active = True
            if not exists.full_name:
                exists.full_name = exists.nickname or exists.username
            if settings.sync_default_admin_password:
                exists.password_hash = hash_password(settings.default_admin_password)

        active_houses = list(db.scalars(select(House).where(House.is_active.is_(True)).order_by(House.sort_order.asc(), House.id.asc())))
        exists.accessible_houses = active_houses
        if exists.default_house_id and exists.default_house_id not in {house.id for house in active_houses}:
            exists.default_house_id = None
        item_count = db.scalar(select(func.count()).select_from(Item)) or 0
        indexed_item_count = db.scalar(select(func.count(func.distinct(VoiceSearchTerm.item_id))).select_from(VoiceSearchTerm)) or 0
        if item_count > 0 and indexed_item_count != item_count:
            mark_all_items_voice_terms_dirty(db)
        db.commit()
    finally:
        db.close()
    try:
        await asyncio.to_thread(broadcaster.start)
    except Exception:
        logger.exception("mDNS startup failed, service discovery disabled for this run")
    start_voice_term_index_worker()
    if settings.voice_search_enabled:
        asyncio.create_task(asyncio.to_thread(get_streaming_asr_service().warmup), name="voice-stream-warmup")
        asyncio.create_task(asyncio.to_thread(get_offline_asr_service().warmup), name="voice-offline-warmup")


@app.on_event("shutdown")
async def on_shutdown():
    await stop_voice_term_index_worker()
    try:
        await asyncio.to_thread(broadcaster.stop)
    except Exception:
        logger.exception("mDNS shutdown failed")


Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin_users.router)
app.include_router(categories.router)
app.include_router(tags.router)
app.include_router(houses.router)
app.include_router(rooms.router)
app.include_router(items.router)
app.include_router(voice_search.router)
app.include_router(data_management.router)
app.include_router(gui_backup.router)


@app.get("/")
@app.get("/login")
def public_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def has_page_access(user: User, path: str) -> bool:
    normalized_path = str(path or "").strip().lower() or "/"
    if user.role == "admin":
        return normalized_path in admin_allowed_paths
    return normalized_path in user_allowed_paths


@app.get("/forbidden")
def forbidden_page(current_user: User | None = Depends(get_current_user_optional)):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return FileResponse(str(templates_dir / "forbidden.html"), status_code=403)


@app.get("/items")
@app.get("/locations")
@app.get("/categories")
@app.get("/tags")
@app.get("/profile")
@app.get("/users")
def protected_index(request: Request, current_user: User | None = Depends(get_current_user_optional)):
    if not current_user:
        return HTMLResponse(
            content="""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>未登录</title>
  <style>
    :root { color-scheme: light; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: #f8fafc;
      font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    }
    .notice {
      background: #fff7ed;
      color: #9a3412;
      border: 1px solid #fdba74;
      border-radius: 12px;
      padding: 16px 22px;
      font-size: 18px;
      line-height: 1.5;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }
  </style>
  <meta http-equiv="refresh" content="2;url=/login" />
</head>
<body>
  <div class="notice">未登录或登录已过期，2秒后跳转到登录页...</div>
  <script>
    setTimeout(function () { window.location.replace("/login"); }, 2000);
  </script>
</body>
</html>""",
            status_code=401,
        )
    if not has_page_access(current_user, request.url.path):
        return RedirectResponse(url="/forbidden", status_code=302)
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
def health():
    return {"status": "ok"}


def run_postgres_migrations() -> None:
    statements = [
        "CREATE TABLE IF NOT EXISTS houses (id SERIAL PRIMARY KEY, name VARCHAR(80) UNIQUE NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT NOW())",
        "ALTER TABLE IF EXISTS houses ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS full_name VARCHAR(50) NOT NULL DEFAULT ''",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS default_house_id INTEGER NULL",
        "ALTER TABLE IF EXISTS users DROP COLUMN IF EXISTS phone",
        """DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_accessible_houses') THEN
    CREATE TABLE user_accessible_houses (
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      house_id INTEGER NOT NULL REFERENCES houses(id) ON DELETE CASCADE,
      PRIMARY KEY (user_id, house_id)
    );
  END IF;
END $$""",
        "INSERT INTO user_accessible_houses (user_id, house_id) SELECT u.id, h.id FROM users u CROSS JOIN houses h WHERE h.is_active IS TRUE AND NOT EXISTS (SELECT 1 FROM user_accessible_houses x WHERE x.user_id = u.id AND x.house_id = h.id)",
        "ALTER TABLE IF EXISTS categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE IF EXISTS categories ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE IF EXISTS tags ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE IF EXISTS locations ADD COLUMN IF NOT EXISTS house_id INTEGER NULL",
        "ALTER TABLE IF EXISTS locations ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE IF EXISTS locations ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE IF EXISTS items ADD COLUMN IF NOT EXISTS location_detail TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE IF EXISTS items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()",
        "ALTER TABLE IF EXISTS items ADD COLUMN IF NOT EXISTS voice_terms_dirty_at TIMESTAMP NULL",
        "ALTER TABLE IF EXISTS items ADD COLUMN IF NOT EXISTS voice_terms_last_indexed_at TIMESTAMP NULL",
        "ALTER TABLE IF EXISTS items DROP COLUMN IF EXISTS notes",
        "ALTER TABLE IF EXISTS items DROP COLUMN IF EXISTS purchase_date",
        "ALTER TABLE IF EXISTS items DROP COLUMN IF EXISTS price",
        "ALTER TABLE IF EXISTS item_images ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()",
        """CREATE TABLE IF NOT EXISTS voice_search_terms (
          id SERIAL PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
          term VARCHAR(120) NOT NULL,
          term_type VARCHAR(20) NOT NULL,
          weight INTEGER NOT NULL DEFAULT 0,
          created_at TIMESTAMP NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        """DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_voice_search_term_item_term'
  ) THEN
    ALTER TABLE voice_search_terms
      ADD CONSTRAINT uq_voice_search_term_item_term
      UNIQUE (user_id, item_id, term, term_type);
  END IF;
END $$""",
        "CREATE INDEX IF NOT EXISTS ix_voice_search_terms_user_id ON voice_search_terms(user_id)",
        "CREATE INDEX IF NOT EXISTS ix_voice_search_terms_item_id ON voice_search_terms(item_id)",
        "CREATE INDEX IF NOT EXISTS ix_voice_search_terms_term_type ON voice_search_terms(term_type)",
        "CREATE INDEX IF NOT EXISTS ix_voice_search_terms_term ON voice_search_terms(term)",
        "CREATE INDEX IF NOT EXISTS ix_items_voice_terms_dirty_at ON items(voice_terms_dirty_at)",
        """DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_name = 'users'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_users_default_house'
  ) THEN
    ALTER TABLE users
      ADD CONSTRAINT fk_users_default_house
      FOREIGN KEY (default_house_id) REFERENCES houses(id) ON DELETE SET NULL;
  END IF;
END $$""",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
