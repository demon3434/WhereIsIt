from __future__ import annotations

import asyncio
import logging

from ...config import settings
from ...database import SessionLocal
from .term_index_service import process_pending_voice_terms

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task[None] | None = None


async def _run_worker() -> None:
    poll_seconds = max(1, settings.voice_terms_index_poll_seconds)
    while True:
        try:
            db = SessionLocal()
            try:
                processed = await asyncio.to_thread(process_pending_voice_terms, db)
                if processed:
                    db.commit()
                else:
                    db.rollback()
            except Exception:
                db.rollback()
                logger.exception("voice term index worker failed")
            finally:
                db.close()
        except Exception:
            logger.exception("voice term index worker loop failed")

        await asyncio.sleep(poll_seconds)


def start_voice_term_index_worker() -> None:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_run_worker(), name="voice-term-index-worker")


async def stop_voice_term_index_worker() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    finally:
        _worker_task = None
