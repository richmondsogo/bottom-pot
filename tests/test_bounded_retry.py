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


@pytest.mark.anyio
async def test_throttle_queued_waiters_recheck_429_and_concurrent_200_preserves_backoff():
    """
    Deterministic regression test using asyncio.Event barriers:
    - Requests pass initial checks and queue behind per-host semaphore.
    - One in-flight request returns 429 Retry-After.
    - Another already-in-flight request returns 200 OK without clearing active 429 backoff.
    - Queued waiters abort with HostRateLimitedError after acquiring semaphores (0 transport calls),
      releasing both semaphores cleanly.
    - Requests succeed after deadline expiry and reset exponential backoff on 200 recovery.
    """
    from unittest.mock import patch

    from src.config import settings
    from src.project_files.http_resilience import (
        HostRateLimitedError,
        resilience_manager,
        throttled_get,
    )

    resilience_manager.reset()
    host = "apply.workable.com"
    url = f"https://{host}/api/v2/accounts/acme/jobs/ABC"
    clock = {"now": 1_700_000_000.0}

    in_flight_entered = 0
    all_three_in_flight = asyncio.Event()
    allow_req0_429 = asyncio.Event()
    allow_req1_200 = asyncio.Event()
    allow_req2_200 = asyncio.Event()
    transport_calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight_entered
        tag = request.headers.get("x-test-tag", "")
        transport_calls.append(tag)
        in_flight_entered += 1
        if in_flight_entered == 3:
            all_three_in_flight.set()
        if tag == "req0":
            await allow_req0_429.wait()
            return httpx.Response(429, headers={"Retry-After": "15"})
        if tag == "req1":
            await allow_req1_200.wait()
            return httpx.Response(200, json={"ok": True})
        if tag == "req2":
            await allow_req2_200.wait()
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"ok": True})

    # Wrap host_sem.acquire so we deterministically observe queued tasks waiting on it
    host_sem = resilience_manager._get_host_semaphore(host)
    orig_acquire = host_sem.acquire
    waiting_on_sem = 0
    two_queued = asyncio.Event()

    async def tracked_acquire():
        nonlocal waiting_on_sem
        if host_sem.locked():
            waiting_on_sem += 1
            if waiting_on_sem >= 2:
                two_queued.set()
        return await orig_acquire()

    host_sem.acquire = tracked_acquire  # type: ignore[method-assign]

    async def _call(client: httpx.AsyncClient, tag: str):
        return await throttled_get(client, url, headers={"x-test-tag": tag})

    with patch("time.time", side_effect=lambda: clock["now"]):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            t0 = asyncio.create_task(_call(client, "req0"))
            t1 = asyncio.create_task(_call(client, "req1"))
            t2 = asyncio.create_task(_call(client, "req2"))
            await asyncio.wait_for(all_three_in_flight.wait(), timeout=2.0)

            # Queue t3 & t4 behind the full host semaphore; both pass pre-semaphore checks now
            t3 = asyncio.create_task(_call(client, "req3"))
            t4 = asyncio.create_task(_call(client, "req4"))
            await asyncio.wait_for(two_queued.wait(), timeout=2.0)

            # Let req0 fail with 429 Retry-After=15 AND req1 immediately succeed with 200
            allow_req0_429.set()
            r0 = await t0
            assert r0.status_code == 429
            assert resilience_manager.is_host_rate_limited(host) is True
            assert resilience_manager._host_rate_limit_backoff[host] == 15.0

            allow_req1_200.set()
            r1 = await t1
            assert r1.status_code == 200
            # Concurrent 200 must NOT cancel the active Retry-After=15 deadline
            assert resilience_manager.is_host_rate_limited(host) is True
            assert resilience_manager._host_rate_limit_backoff[host] == 15.0

            allow_req2_200.set()
            r2 = await t2
            assert r2.status_code == 200
            assert resilience_manager.is_host_rate_limited(host) is True

            # Queued t3 & t4 must reject via post-semaphore recheck without hitting HTTP transport
            with pytest.raises(HostRateLimitedError):
                await t3
            with pytest.raises(HostRateLimitedError):
                await t4

            assert "req3" not in transport_calls
            assert "req4" not in transport_calls

            # Both global and host semaphores must be completely released after HostRateLimitedError
            assert host_sem._value == settings.per_host_concurrency_limit
            assert resilience_manager._get_global_semaphore()._value == settings.global_concurrency_limit

            # Advance clock past Retry-After deadline -> request proceeds and recovery resets backoff
            clock["now"] += 16.0
            assert resilience_manager.is_host_rate_limited(host) is False
            r5 = await throttled_get(client, url, headers={"x-test-tag": "req5"})
            assert r5.status_code == 200
            assert "req5" in transport_calls
            assert host not in resilience_manager._host_rate_limited_until
            assert host not in resilience_manager._host_rate_limit_backoff

    resilience_manager.reset()


@pytest.mark.anyio
async def test_throttle_queued_waiters_recheck_circuit_breaker_after_semaphore():
    """
    Deterministic regression test: requests queued behind host semaphore abort with
    CircuitBreakerOpenError without reaching HTTP transport if in-flight failures trip the breaker.
    """
    from unittest.mock import patch

    from src.config import settings
    from src.project_files.http_resilience import resilience_manager, throttled_get

    resilience_manager.reset()
    host = "apply.workable.com"
    url = f"https://{host}/api/v2/accounts/acme/jobs/DEF"
    clock = {"now": 1_700_000_000.0}

    # Pre-seed threshold - 2 failures so host is still open when tasks queue
    for _ in range(max(0, settings.circuit_breaker_failure_threshold - 2)):
        resilience_manager.record_failure(host)
    assert resilience_manager.is_host_open(host) is True

    in_flight = 0
    all_three_in_flight = asyncio.Event()
    allow_503_a = asyncio.Event()
    allow_503_b = asyncio.Event()
    allow_200_c = asyncio.Event()
    transport_calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal in_flight
        tag = request.headers.get("x-test-tag", "")
        transport_calls.append(tag)
        in_flight += 1
        if in_flight == 3:
            all_three_in_flight.set()
        if tag == "req0":
            await allow_503_a.wait()
            return httpx.Response(503)
        if tag == "req1":
            await allow_503_b.wait()
            return httpx.Response(503)
        if tag == "req2":
            await allow_200_c.wait()
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"ok": True})

    host_sem = resilience_manager._get_host_semaphore(host)
    orig_acquire = host_sem.acquire
    waiting_on_sem = 0
    two_queued = asyncio.Event()

    async def tracked_acquire():
        nonlocal waiting_on_sem
        if host_sem.locked():
            waiting_on_sem += 1
            if waiting_on_sem >= 2:
                two_queued.set()
        return await orig_acquire()

    host_sem.acquire = tracked_acquire  # type: ignore[method-assign]

    async def _call(client: httpx.AsyncClient, tag: str):
        return await throttled_get(client, url, headers={"x-test-tag": tag})

    with patch("time.time", side_effect=lambda: clock["now"]):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            t0 = asyncio.create_task(_call(client, "req0"))
            t1 = asyncio.create_task(_call(client, "req1"))
            t2 = asyncio.create_task(_call(client, "req2"))
            await asyncio.wait_for(all_three_in_flight.wait(), timeout=2.0)

            t3 = asyncio.create_task(_call(client, "req3"))
            t4 = asyncio.create_task(_call(client, "req4"))
            await asyncio.wait_for(two_queued.wait(), timeout=2.0)

            # Release two 503 responses to trip the circuit breaker
            allow_503_a.set()
            allow_503_b.set()
            r0, r1 = await asyncio.gather(t0, t1)
            assert r0.status_code == 503 and r1.status_code == 503
            assert resilience_manager.is_host_open(host) is False

            # Queued t3 & t4 must fail post-semaphore check without calling HTTP transport
            with pytest.raises(CircuitBreakerOpenError):
                await t3
            with pytest.raises(CircuitBreakerOpenError):
                await t4

            allow_200_c.set()
            r2 = await t2
            assert r2.status_code == 200

            assert "req3" not in transport_calls
            assert "req4" not in transport_calls
            assert host_sem._value == settings.per_host_concurrency_limit
            assert resilience_manager._get_global_semaphore()._value == settings.global_concurrency_limit

    resilience_manager.reset()


@pytest.mark.anyio
async def test_rate_limit_exponential_backoff_doubles_across_expiry_and_resets_after_success():
    """
    Verify expired deadline state does not wipe exponential backoff prior to recovery,
    active backoff survives concurrent record_success(), and backoff resets after 200 recovery.
    """
    from unittest.mock import patch

    from src.project_files.http_resilience import resilience_manager, throttled_get

    resilience_manager.reset()
    host = "apply.workable.com"
    url = f"https://{host}/api/v2/accounts/acme/jobs/GHI"
    clock = {"now": 1_700_000_000.0}
    outcomes = [
        httpx.Response(429, text="rate limited"),
        httpx.Response(429, text="still limited"),
        httpx.Response(200, json={"ok": True}),
        httpx.Response(429, text="later limit"),
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return outcomes.pop(0)

    with patch("time.time", side_effect=lambda: clock["now"]):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            r1 = await throttled_get(client, url)
            assert r1.status_code == 429
            assert resilience_manager._host_rate_limit_backoff[host] == 5.0

            # Backoff expires without Retry-After; next 429 must double to 10.0s
            clock["now"] += 6.0
            assert resilience_manager.is_host_rate_limited(host) is False
            r2 = await throttled_get(client, url)
            assert r2.status_code == 429
            assert resilience_manager._host_rate_limit_backoff[host] == 10.0

            # Concurrent 200 before new deadline must preserve active backoff
            clock["now"] += 2.0
            resilience_manager.record_success(host)
            assert resilience_manager.is_host_rate_limited(host) is True
            assert resilience_manager._host_rate_limit_backoff[host] == 10.0

            # After deadline expires, successful 200 clears state & resets exponential backoff
            clock["now"] += 9.0
            r3 = await throttled_get(client, url)
            assert r3.status_code == 200
            assert host not in resilience_manager._host_rate_limited_until
            assert host not in resilience_manager._host_rate_limit_backoff

            clock["now"] += 1.0
            r4 = await throttled_get(client, url)
            assert r4.status_code == 429
            assert resilience_manager._host_rate_limit_backoff[host] == 5.0

    resilience_manager.reset()

