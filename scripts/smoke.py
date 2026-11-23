"""
Read-only offline smoke check for Bottom Pot beta readiness.

Boots the FastAPI ASGI app against a disposable SQLite database in an isolated
temporary directory (never touching operational `data/` or `subscriptions.csv`)
with offline mocked discovery results, and verifies:
1. GET /health
2. GET / (UI shell)
3. GET /search SSE streaming (country selection, freshness tiers, apply links, redaction)
4. POST /api/eligibility/evaluate (backend-authoritative multi-country verdicts)
5. Client-equivalent filtering & detail payload completeness

Usage:
    python scripts/smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _configure_disposable_environment(tmp_dir: Path) -> None:
    """Force ADR 0030 isolation before importing settings or storage singletons."""
    db_path = tmp_dir / "smoke-cache.sqlite"
    subs_path = tmp_dir / "smoke-subscriptions.csv"
    os.environ["BOTTOM_POT_TEST_MODE"] = "1"
    os.environ["BOTTOM_POT_ALLOW_OPERATIONAL_DB"] = "0"
    os.environ.pop("BOTTOM_POT_DATA_DIR", None)
    os.environ["SQLITE_DB_PATH"] = str(db_path)
    os.environ["SUBSCRIPTIONS_FILE"] = str(subs_path)
    os.environ.setdefault("SERPER_API_KEY", "smoke-test-serper-placeholder")


def _build_offline_fixture_jobs():
    from src.core.models import JobEligibility, JobListing
    from src.extraction.eligibility_extractor import apply_applicant_country_assessment
    from src.extraction.freshness import compute_freshness

    now = datetime.now(timezone.utc)
    fresh_iso = (now - timedelta(days=5)).isoformat()
    stale_iso = (now - timedelta(days=180)).isoformat()

    ww_elig = JobEligibility(
        classification="worldwide",
        global_remote_explicit=True,
        objective_scope_label="Worldwide remote",
    )
    us_only_elig = JobEligibility(
        classification="country_restricted",
        allowed_residence_countries=["United States"],
        allowed_country_codes=["US"],
        residence_restriction_confirmed=True,
        objective_scope_label="US only",
    )

    jobs = [
        JobListing(
            id="ashby:supabase:smoke-1",
            provider="ashby",
            ats_source="ashby",
            data_source="api",
            title="Senior Backend Engineer",
            company="Supabase",
            company_slug="supabase",
            company_domain="supabase.com",
            location="Remote",
            is_remote=True,
            employment_type="full_time",
            work_model="remote",
            description="Work asynchronously across timezones building Postgres cloud tooling.",
            requirements="Python, SQL, distributed systems.",
            posted_at=fresh_iso,
            first_seen_at=fresh_iso,
            last_verified_at=now.isoformat(),
            scraped_at=now,
            freshness=compute_freshness(posted_at=fresh_iso, now=now),
            apply_url="https://jobs.ashbyhq.com/supabase/smoke-1",
            source_url="https://jobs.ashbyhq.com/supabase/smoke-1",
            query_used="engineer",
            eligibility=ww_elig,
        ),
        JobListing(
            id="greenhouse:uscorp:smoke-2",
            provider="greenhouse",
            ats_source="greenhouse",
            data_source="api",
            title="Staff Systems Engineer",
            company="US Corp",
            company_slug="uscorp",
            company_domain="uscorp.example",
            location="Remote (US Only)",
            is_remote=True,
            employment_type="full_time",
            work_model="remote",
            description="Must be authorized to work and reside in the United States.",
            requirements="Rust, Go, Kubernetes.",
            posted_at=stale_iso,
            first_seen_at=stale_iso,
            last_verified_at=now.isoformat(),
            scraped_at=now,
            freshness=compute_freshness(posted_at=stale_iso, now=now),
            apply_url="https://boards.greenhouse.io/uscorp/jobs/2",
            source_url="https://boards.greenhouse.io/uscorp/jobs/2",
            query_used="engineer",
            eligibility=us_only_elig,
        ),
    ]
    return [apply_applicant_country_assessment(job, "NG") for job in jobs]


def _parse_sse_events(body_text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    cur_event = ""
    cur_data: list[str] = []
    for line in body_text.splitlines():
        if line.startswith("event:"):
            cur_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            cur_data.append(line.split(":", 1)[1].strip())
        elif not line.strip() and cur_event:
            payload = json.loads("".join(cur_data)) if cur_data else {}
            events.append((cur_event, payload))
            cur_event = ""
            cur_data = []
    if cur_event:
        payload = json.loads("".join(cur_data)) if cur_data else {}
        events.append((cur_event, payload))
    return events


def run_smoke(disposable_dir: Path | None = None) -> dict[str, object]:
    """Execute end-to-end offline API smoke verification against a disposable workspace."""
    with ExitStack() as stack:
        if disposable_dir is None:
            tmp_root = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="bottom-pot-smoke-")))
        else:
            tmp_root = disposable_dir
            tmp_root.mkdir(parents=True, exist_ok=True)

        if "src.core.settings" not in sys.modules:
            _configure_disposable_environment(tmp_root)

        from fastapi.testclient import TestClient

        import src.api.main as api_main
        from src.core.models import DoneEvent, ResultsBatch
        from src.core.settings import settings
        from src.safety.url_safety import StaticDnsResolver, use_dns_resolver
        from src.storage.cache_store import cache_store
        from src.storage.company_board_registry import company_board_registry

        smoke_db = str(tmp_root / "smoke-cache.sqlite")
        smoke_subs = str(tmp_root / "smoke-subscriptions.csv")
        prev_db = settings.sqlite_db_path
        prev_subs = settings.subscriptions_file
        prev_cache_db = cache_store.db_path
        prev_reg_db = company_board_registry.db_path

        try:
            settings.sqlite_db_path = smoke_db
            settings.subscriptions_file = smoke_subs
            cache_store.db_path = smoke_db
            company_board_registry.db_path = smoke_db
            cache_store._ensure_db()
            company_board_registry._ensure_db()

            sample_jobs = _build_offline_fixture_jobs()

            async def _mock_run(params, *args, **kwargs):
                yield ("results", ResultsBatch(batch=sample_jobs, total_so_far=len(sample_jobs)))
                yield (
                    "done",
                    DoneEvent(
                        total=len(sample_jobs),
                        search_time_ms=12,
                        serper_queries_used=0,
                        providers_searched=["ashby", "greenhouse"],
                        providers_skipped=[],
                        cached=False,
                        partial=False,
                    ),
                )

            stack.enter_context(
                use_dns_resolver(
                    StaticDnsResolver(
                        {
                            "jobs.ashbyhq.com": "93.184.216.34",
                            "boards.greenhouse.io": "93.184.216.34",
                        }
                    )
                )
            )
            stack.enter_context(patch.object(api_main.orchestrator, "run", side_effect=_mock_run))

            client = TestClient(api_main.app)

            # 1. Health endpoint
            health_res = client.get("/health")
            assert health_res.status_code == 200, f"/health returned {health_res.status_code}"
            health = health_res.json()
            assert health.get("status") == "ok", f"Unexpected /health status: {health}"
            assert health.get("monitored_provider_count") == 9

            # 2. Frontend landing page served
            index_res = client.get("/")
            assert index_res.status_code == 200
            assert "Bottom Pot" in index_res.text

            # 3. SSE /search with country selection
            sse_res = client.get("/search?q=engineer&applicant_country=NG&days_back=30")
            assert sse_res.status_code == 200
            events = _parse_sse_events(sse_res.text)
            batch_jobs = [job for name, data in events if name == "results" for job in data.get("batch", [])]
            done_events = [data for name, data in events if name == "done"]
            assert len(batch_jobs) == 2, f"Expected 2 jobs, got {len(batch_jobs)}"
            assert len(done_events) == 1
            # Anonymous stream must strip admin-only fields
            assert "serper_calls" not in done_events[0]

            # 4. Eligibility evaluation endpoint across NG vs US
            eval_ng = client.post(
                "/api/eligibility/evaluate",
                json={
                    "applicant_country": "NG",
                    "jobs": [
                        {
                            "id": j["id"],
                            "eligibility": j.get("eligibility"),
                            "work_model": j.get("work_model"),
                            "location": j.get("location"),
                        }
                        for j in batch_jobs
                    ],
                },
            )
            assert eval_ng.status_code == 200
            ng_map = eval_ng.json()["assessments"]
            assert ng_map["ashby:supabase:smoke-1"]["status"] == "eligible"
            assert ng_map["greenhouse:uscorp:smoke-2"]["status"] == "restricted"

            eval_us = client.post(
                "/api/eligibility/evaluate",
                json={
                    "applicant_country": "US",
                    "jobs": [
                        {
                            "id": batch_jobs[1]["id"],
                            "eligibility": batch_jobs[1].get("eligibility"),
                            "work_model": batch_jobs[1].get("work_model"),
                            "location": batch_jobs[1].get("location"),
                        }
                    ],
                },
            )
            assert eval_us.status_code == 200
            assert eval_us.json()["assessments"]["greenhouse:uscorp:smoke-2"]["status"] == "eligible"

            # 5. Filtering, detail fields, and valid apply links
            eligible_remote = [
                j
                for j in batch_jobs
                if j["work_model"] == "remote" and ng_map[j["id"]]["status"] == "eligible"
            ]
            assert len(eligible_remote) == 1
            detail = eligible_remote[0]
            assert detail["title"] == "Senior Backend Engineer"
            assert detail["description"]
            assert detail["apply_url"].startswith("https://")
            assert detail["company_domain"] == "supabase.com"
            assert detail["freshness"] == "fresh"

            return {
                "health": health,
                "streamed_jobs": len(batch_jobs),
                "eligible_for_ng": len(eligible_remote),
            }
        finally:
            settings.sqlite_db_path = prev_db
            settings.subscriptions_file = prev_subs
            cache_store.db_path = prev_cache_db
            company_board_registry.db_path = prev_reg_db


def main() -> int:
    summary = run_smoke()
    print(
        "Smoke check PASSED "
        f"(providers={summary['health']['monitored_provider_count']}, "
        f"streamed={summary['streamed_jobs']}, eligible_ng={summary['eligible_for_ng']})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
