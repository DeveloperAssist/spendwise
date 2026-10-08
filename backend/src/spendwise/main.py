"""The FastAPI application.

uv run spendwise serve     ->  http://127.0.0.1:8000        (the built React app, if present)
                               http://127.0.0.1:8000/docs   (interactive API docs)
"""

import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import auth, imports, insights, transactions
from .config import get_settings

log = logging.getLogger("spendwise")
FRONTEND = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[3] / "frontend" / "dist"))


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SpendWise API",
        version=__version__,
        description="UPI expense tracker with an AI money assistant. Log in with the Authorize button.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_and_timing(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.url.path.startswith("/api"):
            log.info(
                "%s %s -> %s in %.0f ms",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - start) * 1000,
            )
        return response

    for r in (auth.router, transactions.router, imports.router, insights.router):
        app.include_router(r)

    @app.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok", "version": __version__}

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        # unknown /api paths are JSON 404s; every other path is a page of the React app
        if request.url.path.startswith("/api") or not (FRONTEND / "index.html").is_file():
            detail = getattr(exc, "detail", "Not found")
            return JSONResponse({"detail": detail}, status_code=404)
        return FileResponse(FRONTEND / "index.html")

    if (FRONTEND / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")

        @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
        def index():
            return FileResponse(FRONTEND / "index.html")

    return app


app = create_app()
