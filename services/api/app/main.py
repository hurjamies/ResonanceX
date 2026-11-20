"""ResonanceX API – local-first FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api import assets, experience, integrations, prompts, system
from app.config import REPO_ROOT, get_settings
from app.database.session import init_db
from app.services.integrations import generation
from app.workers.jobs import runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings().ensure_dirs()
    init_db()
    generation.recover_on_startup()
    runner.start()
    yield
    runner.shutdown()
    generation.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ResonanceX API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (assets.router, experience.router, prompts.router, integrations.router, system.router):
        app.include_router(r)

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError):  # pragma: no cover - defensive
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    dist = REPO_ROOT / "apps" / "web" / "dist"
    if settings.serve_frontend and dist.exists():
        index = dist / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(404)
            candidate = (dist / full_path).resolve()
            if full_path and dist.resolve() in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
