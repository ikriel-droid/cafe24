from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.db.session import bootstrap_database, reset_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_database(force=True)
    yield
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


app.include_router(api_router, prefix=settings.api_prefix)

web_out_dir = Path(__file__).resolve().parents[2] / "web" / "out"
if web_out_dir.exists():
    app.mount("/", StaticFiles(directory=web_out_dir, html=True), name="web")
