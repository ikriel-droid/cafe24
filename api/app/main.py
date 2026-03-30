from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.db.session import bootstrap_database, reset_engine
from app.jobs.service import run_background_job_tick


logger = logging.getLogger(__name__)


async def background_job_worker_loop() -> None:
    settings = get_settings()
    poll_seconds = max(settings.background_job_poll_seconds, 0.1)
    while True:
        try:
            await asyncio.to_thread(run_background_job_tick, settings.background_job_batch_size)
        except Exception as exc:  # pragma: no cover - defensive worker logging
            logger.exception("Background job worker loop failed: %s", exc)
        await asyncio.sleep(poll_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_database(force=True)
    worker_task: asyncio.Task[None] | None = None
    if settings.background_job_worker_enabled:
        worker_task = asyncio.create_task(background_job_worker_loop())

    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task
        reset_engine()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=False,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


app.include_router(api_router, prefix=settings.api_prefix)

web_out_dir = Path(__file__).resolve().parents[2] / "web" / "out"
if web_out_dir.exists():
    app.mount("/", StaticFiles(directory=web_out_dir, html=True), name="web")
