"""
Tests for bounded retry policy, delay caps, jitter, Retry-After parsing,
and circuit breaker interaction according to ADR 0029.
"""

import asyncio
from datetime import datetime, timezone
import httpx
import pytest

from src.project_files.extraction_outcome import ExtractionOutcome, ExtractionResult
from src.project_files.http_resilience import CircuitBreakerOpenError, resilience_manager
from src.project_files.retry import (
    _parse_retry_after,
    get_current_attempts,
    with_retry,
)


@pytest.mark.anyio
async def test_retry_on_5xx_succeeds_on_final_attempt():
    """Mocked test: function fails twice with 500, succeeds on 3rd attempt."""
    attempts = 0
    sleeps: list[float] = []

    async def mock_sleep(d: float):
        sleeps.append(d)

    @with_retry(
        max_attempts=3,
        base_delay=0.5,
        sleep_func=mock_sleep,
        rng_func=lambda a, b: b,  # deterministic max jitter
    )
    async def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            req = httpx.Request("GET", "https://api.example.com/jobs")
            resp = httpx.Response(500, request=req)
            raise httpx.HTTPStatusError("Server Error", request=req, response=resp)
        return {"status": "ok"}

    result = await flaky_call()
    assert result == {"status": "ok"}
    assert attempts == 3
    assert len(sleeps) == 2
    assert sleeps[0] == 0.5  # base_delay * 2^0
    assert sleeps[1] == 1.0  # base_delay * 2^1


@pytest.mark.anyio
async def test_retry_cap_holds_and_raises_after_max_attempts():
    """Mocked test: 503 error repeatedly fails; raises after 3 attempts."""
    attempts = 0
    sleeps: list[float] = []

    async def mock_sleep(d: float):
        sleeps.append(d)

    @with_retry(
        max_attempts=3,
        base_delay=0.5,
        sleep_func=mock_sleep,
        rng_func=lambda a, b: b,
    )
    async def always_failing():
        nonlocal attempts
        attempts += 1
        req = httpx.Request("GET", "https://api.example.com/jobs")
        resp = httpx.Response(503, request=req)
        raise httpx.HTTPStatusError("Service Unavailable", request=req, response=resp)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await always_failing()

    assert exc_info.value.response.status_code == 503
    assert attempts == 3
    assert len(sleeps) == 2


@pytest.mark.anyio
async def test_never_retry_404_or_403_or_400():
    """Mocked test: 404, 403, and 400 errors fail immediately without retry."""
    for status in (400, 403, 404):
        attempts = 0
        sleeps: list[float] = []

        @with_retry(
            max_attempts=3,
            sleep_func=lambda d: sleeps.append(d),
        )
        async def client_error():
            nonlocal attempts
            attempts += 1
            req = httpx.Request("GET", "https://api.example.com/jobs")
            resp = httpx.Response(status, request=req)
            raise httpx.HTTPStatusError("Client Error", request=req, response=resp)

        with pytest.raises(httpx.HTTPStatusError):
            await client_error()

        assert attempts == 1
        assert len(sleeps) == 0


@pytest.mark.anyio
async def test_never_retry_circuit_breaker_open():
    """Mocked test: CircuitBreakerOpenError is never retried."""
    attempts = 0
    sleeps: list[float] = []

    @with_retry(
        max_attempts=3,
        sleep_func=lambda d: sleeps.append(d),
    )
    async def tripped_call():
        nonlocal attempts
        attempts += 1
        raise CircuitBreakerOpenError("tripped-host.com")

    with pytest.raises(CircuitBreakerOpenError):
        await tripped_call()

    assert attempts == 1
    assert len(sleeps) == 0


@pytest.mark.anyio
async def test_never_retry_non_idempotent():
    """Mocked test: is_idempotent=False never retries even on 500."""
    attempts = 0
    sleeps: list[float] = []

    @with_retry(
        max_attempts=3,
        is_idempotent=False,
        sleep_func=lambda d: sleeps.append(d),
    )
    async def post_call():
        nonlocal attempts
        attempts += 1
        req = httpx.Request("POST", "https://api.example.com/search")
        resp = httpx.Response(500, request=req)
        raise httpx.HTTPStatusError("Post failed", request=req, response=resp)

    with pytest.raises(httpx.HTTPStatusError):
        await post_call()

    assert attempts == 1
    assert len(sleeps) == 0


@pytest.mark.anyio
async def test_retry_after_seconds_honored_and_capped():
    """Mocked test: Retry-After seconds header is honored and capped at max_delay_per_retry."""
    sleeps: list[float] = []

    async def mock_sleep(d: float):
        sleeps.append(d)

    attempts = 0

    @with_retry(
        max_attempts=3,
        max_delay_per_retry=5.0,
        sleep_func=mock_sleep,
    )
    async def rate_limited_call():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            req = httpx.Request("GET", "https://api.example.com/jobs")
            resp = httpx.Response(429, headers={"Retry-After": "3"}, request=req)
            raise httpx.HTTPStatusError("Rate Limited", request=req, response=resp)
        return {"data": 123}

    res = await rate_limited_call()
    assert res == {"data": 123}
    assert attempts == 2
    assert sleeps == [3.0]


@pytest.mark.anyio
async def test_retry_after_exceeding_budget_gives_up_immediately():
    """Mocked test: Retry-After exceeding remaining budget gives up without sleeping."""
    sleeps: list[float] = []

    @with_retry(
        max_attempts=3,
        max_total_delay=10.0,
        sleep_func=lambda d: sleeps.append(d),
    )
    async def rate_limited_huge():
        req = httpx.Request("GET", "https://api.example.com/jobs")
        resp = httpx.Response(429, headers={"Retry-After": "60"}, request=req)
        raise httpx.HTTPStatusError("Rate Limited", request=req, response=resp)

    with pytest.raises(httpx.HTTPStatusError):
        await rate_limited_huge()

    assert len(sleeps) == 0


def test_parse_retry_after_http_date():
    """Test HTTP date in Retry-After is parsed relative to injected clock."""
    fixed_now = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    http_date = "Sun, 01 Nov 2026 12:00:08 GMT"
    delay = _parse_retry_after(http_date, clock_func=lambda: fixed_now)
    assert delay == 8.0


@pytest.mark.anyio
async def test_retry_with_extraction_result_return():
    """Mocked test: retry function that returns ExtractionResult directly."""
    attempts = 0
    sleeps: list[float] = []

    async def mock_sleep(d: float):
        sleeps.append(d)

    @with_retry(
        max_attempts=3,
        base_delay=0.5,
        sleep_func=mock_sleep,
        rng_func=lambda a, b: b,
    )
    async def fetch_item():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return ExtractionResult(
                outcome=ExtractionOutcome.RATE_LIMITED,
                status_code=429,
                attempts=attempts,
            )
        return ExtractionResult(
            outcome=ExtractionOutcome.SUCCESS,
            status_code=200,
            attempts=attempts,
        )

    res = await fetch_item()
    assert res.outcome == ExtractionOutcome.SUCCESS
    assert attempts == 2
    assert len(sleeps) == 1


@pytest.mark.anyio
async def test_cumulative_delay_cap_bounds_total_sleep():
    """Mocked test: total sleep across retries never exceeds max_total_delay."""
    sleeps: list[float] = []

    @with_retry(
        max_attempts=5,
        base_delay=4.0,  # 4s, 8s, 16s...
        max_delay_per_retry=8.0,
        max_total_delay=10.0,
        sleep_func=lambda d: sleeps.append(d),
        rng_func=lambda a, b: b,
    )
    async def high_delay_call():
        req = httpx.Request("GET", "https://api.example.com/jobs")
        resp = httpx.Response(500, request=req)
        raise httpx.HTTPStatusError("Server Error", request=req, response=resp)

    with pytest.raises(httpx.HTTPStatusError):
        await high_delay_call()

    # Sleep 1: 4.0s (remaining: 6.0s)
    # Sleep 2: min(8.0, 6.0) = 6.0s (remaining: 0.0s)
    # Sleep 3: remaining is 0 -> gives up immediately
    assert sum(sleeps) <= 10.0
    assert sleeps == [4.0, 6.0]


@pytest.mark.anyio
async def test_circuit_breaker_trips_and_blocks_retries():
    """Mocked test: 5 consecutive failures trip circuit breaker; subsequent call fails with CircuitBreakerOpenError."""
    resilience_manager.reset()
    host = "flaky-ats.com"
    url = f"https://{host}/jobs/1"

    # Record 5 failures to trip the circuit breaker
    for _ in range(5):
        resilience_manager.record_failure(host)

    assert not resilience_manager.is_host_open(host)

    attempts = 0
    sleeps: list[float] = []

    @with_retry(
        max_attempts=3,
        sleep_func=lambda d: sleeps.append(d),
    )
    async def request_tripped_host():
        nonlocal attempts
        attempts += 1
        if not resilience_manager.is_host_open(host):
            raise CircuitBreakerOpenError(host)
        return "ok"

    with pytest.raises(CircuitBreakerOpenError):
        await request_tripped_host()

    assert attempts == 1
    assert len(sleeps) == 0
    resilience_manager.reset()

