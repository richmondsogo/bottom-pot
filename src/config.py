from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    serper_api_key: str

    # Search behaviour
    max_results: int = 100
    max_serper_queries_per_search: int = 60
    serper_max_pages: int = 3

    # Timeouts
    ats_request_timeout_seconds: int = 5
    scraper_request_timeout_seconds: int = 10
    search_hard_timeout_seconds: int = 90

    # Nigerian scraper politeness
    scraper_delay_seconds: float = 1.5

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

    # Rate limiting
    rate_limit_per_hour: int = 20  # per IP (legacy)
    rate_limit_search: str = "20/hour"  # per IP on /search

    # Subscriptions
    subscriptions_file: str = "subscriptions.csv"

    log_level: str = "INFO"


settings = Settings()
