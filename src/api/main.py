"""
FastAPI application for Bottom Pot backend.

Provides:
- GET /search (Server-Sent Events streaming job search)
- GET /health (Health check endpoint)
- POST /subscribe (Email subscription logger)
"""

from __future__ import annotations

import asyncio
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.config import settings
from src.project_files.models import (
    DoneEvent,
    ErrorEvent,
    ResultsBatch,
    SearchParams,
    SubscribeRequest,
)
from src.api.allowlist import serialize_event_for_user
from src.api.auth import AdminLoginRequest, create_session_token, verify_admin_cookie
from src.project_files.search_pipeline import SearchOrchestrator

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Bottom Pot API", version="2.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to frontend domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Serve the browser client: prefer compiled frontend/dist, fall back to frontend-old
dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
fallback_dir = Path(__file__).resolve().parents[2] / "frontend-old"
frontend_dir = dist_dir if dist_dir.is_dir() else (fallback_dir if fallback_dir.is_dir() else Path(__file__).resolve().parents[2] / "frontend")


@app.get("/app")
async def serve_app():
    index_file = frontend_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return FileResponse(dist_dir / "index.html")


@app.get("/admin")
async def serve_admin():
    index_file = frontend_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return FileResponse(dist_dir / "index.html")


@app.middleware("http")
async def handle_search_page_navigation(request: Request, call_next):
    if request.url.path == "/search" and request.method == "GET":
        accept = request.headers.get("accept", "")
        # A request is a browser page navigation when Accept contains text/html
        # and does NOT contain text/event-stream. If both are present, the stream wins.
        if "text/html" in accept and "text/event-stream" not in accept:
            response = await serve_app()
            response.headers["Vary"] = "Accept"
            return response

    response = await call_next(request)
    if request.url.path == "/search":
        response.headers["Vary"] = "Accept"
    return response


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path in ("/", "/index.html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


orchestrator = SearchOrchestrator()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/search")
@limiter.limit(settings.rate_limit_search)
async def search(
    request: Request,
    q: str = Query(
        ...,
        min_length=2,
        max_length=100,
        description="Job title, e.g. 'Data Analyst'",
    ),
    location: Optional[str] = Query(None, max_length=100),
    remote: Optional[bool] = Query(None),
    days_back: int = Query(7, ge=1, le=90),
    platforms: Optional[str] = Query(
        None,
        description="Comma-separated: greenhouse,lever,ashby,...",
    ),
    include_nigerian: bool = Query(True),
) -> StreamingResponse:
    """
    Streams job search results progressively using Server-Sent Events (SSE).
    """
    target_platforms = (
        [p.strip().lower() for p in platforms.split(",") if p.strip()]
        if platforms
        else None
    )

    search_params = SearchParams(
        job_title=q,
        location=location,
        remote=remote,
        days_back=days_back,
        include_nigerian_sites=include_nigerian,
    )

    is_admin = verify_admin_cookie(request)

    async def event_generator():
        try:
            async for event_name, event_data in orchestrator.run(
                search_params, target_platforms, is_disconnected=request.is_disconnected
            ):
                if is_admin:
                    payload = event_data.model_dump_json()
                    yield f"event: {event_name}\ndata: {payload}\n\n"
                else:
                    payload = serialize_event_for_user(event_name, event_data)
                    if payload is not None:
                        yield f"event: {event_name}\ndata: {payload}\n\n"
        except Exception as exc:
            err = ErrorEvent(message=f"Search provider error: {exc}", code="PROVIDER_ERROR")
            if is_admin:
                yield f"event: error\ndata: {err.model_dump_json()}\n\n"
            else:
                payload = serialize_event_for_user("error", err)
                if payload is not None:
                    yield f"event: error\ndata: {payload}\n\n"

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # prevents Nginx from buffering SSE
        "Connection": "keep-alive",
    }

    return StreamingResponse(event_generator(), headers=headers)


@app.post("/subscribe", status_code=201)
async def subscribe(body: SubscribeRequest):
    """
    Appends email and optional search query to subscriptions.csv.
    Creates the file if it does not exist.
    """
    file_exists = os.path.isfile(settings.subscriptions_file)
    with open(settings.subscriptions_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["email", "search_query", "subscribed_at"])
        writer.writerow([
            body.email,
            body.search_query or "",
            datetime.now(timezone.utc).isoformat(),
        ])
    return {"subscribed": True}


@app.on_event("startup")
async def log_admin_config_warnings():
    if not settings.admin_password:
        logger.warning("ADMIN_PASSWORD is not set. Admin login is disabled.")


# ── Admin Authentication Endpoints ──────────────────────────────────────────


@app.post("/api/admin/login")
@limiter.limit(settings.rate_limit_admin_login)
async def admin_login(request: Request, body: AdminLoginRequest):
    """
    Authenticates administrator password and issues a signed 7-day httpOnly session cookie.
    If ADMIN_PASSWORD is unset, returns HTTP 503.
    """
    if not settings.admin_password:
        raise HTTPException(
            status_code=503,
            detail="Admin access disabled: ADMIN_PASSWORD is not configured",
        )

    if not secrets.compare_digest(
        body.password.encode("utf-8"), settings.admin_password.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid admin password")

    token = create_session_token(settings.admin_cookie_max_age_seconds)
    is_secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )
    response = JSONResponse(content={"authenticated": True})
    response.set_cookie(
        key=settings.admin_cookie_name,
        value=token,
        max_age=settings.admin_cookie_max_age_seconds,
        httponly=True,
        samesite="lax",
        path="/",
        secure=is_secure,
    )
    return response


@app.post("/api/admin/logout")
async def admin_logout(response: Response):
    """Clears the admin session cookie."""
    response.delete_cookie(key=settings.admin_cookie_name, path="/")
    return {"authenticated": False}


@app.get("/api/admin/verify")
async def admin_verify(request: Request):
    """Verifies that the caller has a valid, signed admin session cookie."""
    if not verify_admin_cookie(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"authenticated": True}


app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
