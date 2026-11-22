"""Authoritative backend settings and ATS platform configuration.

Unifies runtime environment settings (Pydantic BaseSettings) and the active
ATS platform registry (ATS_PLATFORMS) formerly duplicated in
``src/project_files/config.py``.
"""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.models import ATSConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    serper_api_key: str = ""
    serper_endpoint: str = "https://google.serper.dev/search"

    # Search behaviour
    max_results: int = 100
    max_serper_queries_per_search: int = 60
    serper_max_pages: int = 3

    # Monitoring & Registry
    monitoring_enabled: bool = False
    monitoring_interval_seconds: int = 300
    monitoring_board_interval_seconds: int = 1800  # 30 min per board default
    monitoring_concurrency_limit: int = 5
    monitoring_batch_size: int = 25

    # Timeouts
    ats_request_timeout_seconds: int = 5
    scraper_request_timeout_seconds: int = 10
    search_hard_timeout_seconds: int = 90
    pinpoint_board_request_timeout_seconds: float = 25.0  # Pinpoint /postings.json feeds observed at ~16-20s

    # Nigerian scraper politeness
    scraper_delay_seconds: float = 5.0

    # In-memory cache
    cache_ttl_seconds: int = 300  # 5 minutes
    in_memory_cache_max_entries: int = 100

    # Serper cost & replay
    serper_daily_budget: int = 200
    serper_mode: str = "live"  # "live" | "cache_only"
    serper_cache_ttl_hours: int = 12
    url_cache_ttl_hours: int = 24
    sqlite_db_path: str = "data/cache.sqlite"

    # Concurrency & Resilience
    global_concurrency_limit: int = 20
    per_host_concurrency_limit: int = 3
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_seconds: int = 600  # 10 minutes
    max_response_bytes: int = 3 * 1024 * 1024  # 3 MB
    recruitee_board_max_response_bytes: int = 16 * 1024 * 1024  # 16 MiB for full-board JSON listings
    pinpoint_board_max_response_bytes: int = 3 * 1024 * 1024  # 3 MiB cap for Pinpoint /postings.json

    # Rate limiting
    rate_limit_per_hour: int = 20  # per IP (legacy)
    rate_limit_search: str = "20/hour"  # per IP on /search
    rate_limit_admin_login: str = "5/minute"  # per IP on /api/admin/login

    # Admin authentication
    admin_password: str = ""
    admin_session_secret: str = ""
    admin_cookie_name: str = "bp_admin_session"
    admin_cookie_max_age_seconds: int = 604800  # 7 days

    # Subscriptions
    subscriptions_file: str = "subscriptions.csv"

    log_level: str = "INFO"


settings = Settings()

# Active ATS platforms used for Google site: discovery and provider reconciliation.
ATS_PLATFORMS: list[ATSConfig] = [
    ATSConfig(name="greenhouse", site_operator="greenhouse.io", label="Greenhouse"),
    ATSConfig(name="lever", site_operator="jobs.lever.co", label="Lever"),
    ATSConfig(name="ashby", site_operator="jobs.ashbyhq.com", label="Ashby"),
    ATSConfig(name="workable", site_operator="apply.workable.com", label="Workable"),
    ATSConfig(name="bamboohr", site_operator="bamboohr.com/careers", label="BambooHR"),
    ATSConfig(name="jobvite", site_operator="jobs.jobvite.com", label="Jobvite"),
    ATSConfig(
        name="smartrecruiters",
        site_operator="jobs.smartrecruiters.com",
        label="SmartRecruiters",
    ),
    ATSConfig(name="icims", site_operator="icims.com", label="iCIMS"),
    ATSConfig(name="personio", site_operator="jobs.personio.com", label="Personio"),
    ATSConfig(name="teamtailor", site_operator="teamtailor.com", label="Teamtailor"),
    ATSConfig(name="recruitee", site_operator="recruitee.com", label="Recruitee"),
    ATSConfig(name="workday", site_operator="myworkdayjobs.com", label="Workday"),
    ATSConfig(name="taleo", site_operator="taleo.net/careersection", label="Taleo"),
    ATSConfig(name="jobadder", site_operator="jobadder.com", label="JobAdder"),
    ATSConfig(name="jazzhr", site_operator="applytojob.com", label="JazzHR"),
    ATSConfig(name="avature", site_operator="avature.net", label="Avature"),
    ATSConfig(
        name="successfactors", site_operator="jobs.sap.com", label="SAP SuccessFactors"
    ),
    ATSConfig(name="pinpointhq", site_operator="pinpointhq.com", label="Pinpoint"),
]

# Legacy module-level constants preserved from src/project_files/config.py.
SERPER_ENDPOINT: str = settings.serper_endpoint
SERPER_MAX_PAGES: int = settings.serper_max_pages
SERPER_API_KEY: str | None = settings.serper_api_key or os.environ.get("SERPER_API_KEY") or None
