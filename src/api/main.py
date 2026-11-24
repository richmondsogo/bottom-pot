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
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.api.allowlist import serialize_event_for_user
from src.api.auth import AdminLoginRequest, create_session_token, verify_admin_cookie
from src.core.countries import normalize_country_code
from src.core.exceptions import SafetyError
from src.core.models import (
    EligibilityEvaluateRequest,
    EligibilityEvaluateResponse,
    ErrorEvent,
    SearchParams,
    SubscribeRequest,
)
from src.core.settings import settings
from src.discovery.search_pipeline import SearchOrchestrator
from src.extraction.eligibility_extractor import evaluate_eligibility_for_country
from src.providers.board_adapters import BOARD_ADAPTERS
from src.safety.db_safety import (
    assert_safe_sqlite_db_path,
    assert_safe_subscriptions_path,
    authorize_operational_runtime,
    is_operational_env_enabled,
    is_test_or_disposable_context,
    revoke_operational_runtime,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    monitor_task: asyncio.Task | None = None
    if is_operational_env_enabled() and not is_test_or_disposable_context():
        authorize_operational_runtime("src.api.main:lifespan")
    try:
        assert_safe_sqlite_db_path(settings.sqlite_db_path, operation="startup")
        assert_safe_subscriptions_path(settings.subscriptions_file)
        if not settings.admin_password:
            logger.warning("ADMIN_PASSWORD is not set. Admin login is disabled.")
        elif not settings.admin_session_secret:
            logger.error(
                "ADMIN_PASSWORD is set without ADMIN_SESSION_SECRET. Multi-worker or container restarts will invalidate admin sessions."
            )
        if settings.monitoring_enabled and not is_test_or_disposable_context():
            from src.monitoring.board_monitor import BoardMonitor
            logger.info("[monitor] Independent ATS board monitoring enabled; launching background daemon loop.")
            monitor = BoardMonitor()
            monitor_task = asyncio.create_task(monitor.run_loop(interval=settings.monitoring_interval_seconds))
        yield
    finally:
        if monitor_task is not None and not monitor_task.done():
            monitor_task.cancel()
        revoke_operational_runtime()


class SafeGZipMiddleware:
    """Compress non-streaming HTTP responses while bypassing SSE `/search` streams."""

    def __init__(self, app_asgi, minimum_size: int = 500) -> None:
        self._app = app_asgi
        self._gzip = GZipMiddleware(app_asgi, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            headers = dict(scope.get("headers") or [])
            accept = headers.get(b"accept", b"").decode("latin-1").lower()
            if path == "/search" or "text/event-stream" in accept:
                await self._app(scope, receive, send)
                return
        await self._gzip(scope, receive, send)


def _get_client_ip(request: Request) -> str:
    """Resolve requester IP from forwarded headers only when trust_proxy_headers is enabled."""
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            first_ip = xff.split(",", 1)[0].strip()
            if first_ip:
                return first_ip
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    return get_remote_address(request)


def _parse_cors_origins() -> list[str]:
    origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    return origins or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


limiter = Limiter(key_func=_get_client_ip)
app = FastAPI(title="Bottom Pot API", version="2.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SafeGZipMiddleware, minimum_size=500)
_cors_origins = _parse_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)


# Serve the browser client: prefer compiled frontend/dist, fall back to frontend source directory
dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
frontend_dir = dist_dir if dist_dir.is_dir() else Path(__file__).resolve().parents[2] / "frontend"


def _spa_index_response() -> FileResponse:
    index_file = frontend_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return FileResponse(dist_dir / "index.html")


@app.get("/app")
async def serve_app():
    return _spa_index_response()


@app.get("/product")
async def serve_product():
    return _spa_index_response()


@app.get("/sources")
async def serve_sources():
    return _spa_index_response()


@app.get("/about")
async def serve_about():
    return _spa_index_response()


@app.get("/admin")
async def serve_admin():
    return _spa_index_response()


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
    if request.url.path in ("/", "/index.html", "/app", "/product", "/sources", "/about", "/admin"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif request.url.path.startswith("/assets/") and response.status_code == 200:
        response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


orchestrator = SearchOrchestrator()


@app.get("/health")
async def health():
    """Read-only health and capability endpoint."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "monitored_providers": sorted(BOARD_ADAPTERS.keys()),
        "monitored_provider_count": len(BOARD_ADAPTERS),
        "monitoring_enabled": settings.monitoring_enabled,
        "serper_mode": settings.serper_mode,
        "frontend_built": (dist_dir / "index.html").exists(),
    }


@app.post("/api/eligibility/evaluate", response_model=EligibilityEvaluateResponse)
@limiter.limit(settings.rate_limit_eligibility)
async def evaluate_eligibility(
    request: Request,
    body: EligibilityEvaluateRequest,
) -> EligibilityEvaluateResponse:
    """Stateless backend-authoritative eligibility assessment for an applicant country."""
    normalized_code = normalize_country_code(body.applicant_country)
    if not normalized_code:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported applicant_country code: {body.applicant_country!r}",
        )
    assessments = {
        item.id: evaluate_eligibility_for_country(
            item.eligibility,
            normalized_code,
            work_model=item.work_model,
            location=item.location,
        )
        for item in body.jobs
    }
    return EligibilityEvaluateResponse(
        applicant_country_code=normalized_code,
        assessments=assessments,
    )


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
        description="Comma-separated: greenhouse,lever,ashby,hotnigerianjobs,...",
    ),
    include_nigerian: bool = Query(
        True,
        description="Include Nigerian job boards (can also be specified via platforms)",
    ),
    applicant_country: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 applicant country code (e.g. NG, DE, US)",
    ),
    live_discovery: Optional[bool] = Query(
        None,
        description="Force Phase 2 Serper live discovery even when SERPER_MODE=fallback",
    ),
) -> StreamingResponse:
    """
    Streams job search results progressively using Server-Sent Events (SSE).
    """
    normalized_applicant_country: str | None = None
    if applicant_country is not None and applicant_country.strip():
        normalized_applicant_country = normalize_country_code(applicant_country)
        if not normalized_applicant_country:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported applicant_country code: {applicant_country!r}",
            )

    target_platforms: list[str] | None = (
        [
            p.strip().lower()
            for p in platforms.split(",")
            if p.strip() and p.strip().lower() != "none"
        ]
        if platforms is not None
        else None
    )

    search_params = SearchParams(
        job_title=q,
        location=location,
        remote=remote,
        days_back=days_back,
        applicant_country=normalized_applicant_country,
        include_nigerian_sites=include_nigerian,
        live_discovery=live_discovery,
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
        except SafetyError:
            raise
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


_subscribe_lock = threading.Lock()
_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_csv_cell(value: str) -> str:
    """Neutralize leading spreadsheet formula characters before writing CSV fields."""
    if value and value.startswith(_CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


@app.post("/subscribe", status_code=201)
@limiter.limit(settings.rate_limit_subscribe)
async def subscribe(request: Request, body: SubscribeRequest):
    """
    Appends email and optional search query to subscriptions.csv.
    Creates the file if it does not exist.
    """
    safe_subs_path = assert_safe_subscriptions_path(settings.subscriptions_file)
    safe_email = _sanitize_csv_cell(str(body.email))
    safe_query = _sanitize_csv_cell(body.search_query or "")
    subscribed_at = datetime.now(timezone.utc).isoformat()
    with _subscribe_lock:
        file_exists = os.path.isfile(safe_subs_path)
        with open(safe_subs_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["email", "search_query", "subscribed_at"])
            writer.writerow([safe_email, safe_query, subscribed_at])
    return {"subscribed": True}


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

    samesite = (settings.admin_cookie_samesite or "lax").strip().lower()
    if samesite not in {"lax", "strict", "none"}:
        samesite = "lax"
    token = create_session_token(settings.admin_cookie_max_age_seconds)
    is_secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
        or samesite == "none"
    )
    response = JSONResponse(content={"authenticated": True})
    response.set_cookie(
        key=settings.admin_cookie_name,
        value=token,
        max_age=settings.admin_cookie_max_age_seconds,
        httponly=True,
        samesite=samesite,  # type: ignore[arg-type]
        path="/",
        secure=is_secure,
    )
    return response


@app.post("/api/admin/logout")
async def admin_logout(request: Request, response: Response):
    """Clears the admin session cookie."""
    samesite = (settings.admin_cookie_samesite or "lax").strip().lower()
    if samesite not in {"lax", "strict", "none"}:
        samesite = "lax"
    is_secure = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
        or samesite == "none"
    )
    response.delete_cookie(
        key=settings.admin_cookie_name,
        path="/",
        samesite=samesite,  # type: ignore[arg-type]
        secure=is_secure,
    )
    return {"authenticated": False}


@app.get("/api/admin/verify")
async def admin_verify(request: Request):
    """Verifies that the caller has a valid, signed admin session cookie."""
    if not verify_admin_cookie(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"authenticated": True}


if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
