from __future__ import annotations

import json
from pathlib import Path
import re

import httpx
import pytest

from src.project_files.ats_api_client import (
    GreenhouseClient,
    LeverClient,
    AshbyClient,
    SmartRecruitersClient,
    WorkableClient,
    BambooHRClient,
    RecruiteeClient,
)
from src.project_files.ats_url_parser import parse_ats_url, SUPPORTED_ATS_PATTERNS
from src.project_files.config import ATS_PLATFORMS
from src.project_files.models import DoneEvent, SearchParams
from src.project_files.search_pipeline import SearchOrchestrator
from src.project_files.work_model import resolve_work_model

REAL_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "real"


# ---------------------------------------------------------------------------
# 1. Real API Fixtures & Workplace-Type Field Verification
# ---------------------------------------------------------------------------

def test_greenhouse_real_fixture_workplace_field():
    fixture_path = REAL_FIXTURES_DIR / "greenhouse" / "job_8860302002.json"
    assert fixture_path.exists()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert payload.get("id") == 8860302002
    assert "title" in payload
    assert "location" in payload
    # Greenhouse jobs API does not expose an explicit workplace-type enum field
    raw_workplace_type = payload.get("workplace_type") or payload.get("workplaceType")
    assert raw_workplace_type is None


def test_lever_real_fixture_workplace_field():
    fixture_path = REAL_FIXTURES_DIR / "lever" / "job_caadac8e.json"
    assert fixture_path.exists()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Assert workplace-type field exists in the real payload
    assert "workplaceType" in payload
    raw_val = payload["workplaceType"]
    assert raw_val == "remote"
    wm = resolve_work_model(workplace_type=raw_val)
    assert wm.value == "remote"
    assert wm.source == "api_enum"
    assert wm.evidence == "remote"


def test_ashby_real_fixture_workplace_field():
    fixture_path = REAL_FIXTURES_DIR / "ashby" / "linear_board.json"
    assert fixture_path.exists()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    jobs = payload.get("jobs", [])
    assert len(jobs) > 0
    job = next(j for j in jobs if j.get("id") == "d3bc1ced-3ce4-4086-a050-555055dbb1ff")
    # Assert workplace-type field exists in the real payload
    assert "workplaceType" in job
    raw_val = job["workplaceType"]
    assert raw_val == "Remote"
    wm = resolve_work_model(workplace_type=raw_val)
    assert wm.value == "remote"
    assert wm.source == "api_enum"


def test_smartrecruiters_real_fixture_workplace_field():
    fixture_path = REAL_FIXTURES_DIR / "smartrecruiters" / "job_3743990000051828.json"
    assert fixture_path.exists()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    loc = payload.get("location", {})
    assert "city" in loc
    # Verify remoteType mapping: remoteType does not exist in SmartRecruiters posting payload
    # (SmartRecruiters uses boolean 'remote' and 'hybrid' fields)
    assert "remoteType" not in loc
    raw_remote_type = loc.get("remoteType")
    assert raw_remote_type is None


def test_workable_real_fixture_workplace_field():
    fixture_path = REAL_FIXTURES_DIR / "workable" / "job_D94DBAF102.md"
    assert fixture_path.exists()
    content = fixture_path.read_text(encoding="utf-8")

    # Assert workplace line exists in the markdown payload
    match = re.search(r"\*\*Workplace:\*\*\s*(.+)", content, re.IGNORECASE)
    assert match is not None
    raw_val = match.group(1).strip()
    assert raw_val == "on_site"
    wm = resolve_work_model(workplace_type=raw_val)
    assert wm.value == "in_person"
    assert wm.source == "api_enum"


def test_bamboohr_real_fixture_workplace_field():
    fixture_path = REAL_FIXTURES_DIR / "bamboohr" / "deel_list.json"
    assert fixture_path.exists()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    results = payload.get("result", [])
    assert len(results) > 0
    job = next(j for j in results if str(j.get("id")) == "15")
    # Assert locationType field exists in the real payload
    assert "locationType" in job
    raw_val = job["locationType"]
    wm = resolve_work_model(workplace_type=raw_val)
    # The public page https://deel.bamboohr.com/careers/15 has no On-site label
    # (only physical location "Mayfair, London, City of"), so "0" is unverified and returns None
    assert wm.value is None
    assert wm.source is None


def test_recruitee_real_fixture_workplace_field():
    fixture_path = REAL_FIXTURES_DIR / "recruitee" / "offer_2774909.json"
    assert fixture_path.exists()
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    offer = payload.get("offer", payload)
    assert "title" in offer
    # Verify workplace_type mapping: workplace_type key is not present in Recruitee public API
    assert "workplace_type" not in offer
    raw_wt = offer.get("workplace_type")
    assert raw_wt is None


# ---------------------------------------------------------------------------
# 2. End-to-End Client Fetch with Real Payloads
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_all_7_clients_fetch_real_payloads():
    # 1. Greenhouse
    gh_raw = (REAL_FIXTURES_DIR / "greenhouse" / "job_8860302002.json").read_bytes()
    gh_parsed = parse_ats_url("https://boards.greenhouse.io/gitlab/jobs/8860302002")
    assert gh_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=gh_raw))) as client:
        gh_job = await GreenhouseClient().fetch(gh_parsed, client)
    assert gh_job is not None
    assert gh_job.provider == "greenhouse"
    assert gh_job.data_source == "api"

    # 2. Lever
    lever_raw = (REAL_FIXTURES_DIR / "lever" / "job_caadac8e.json").read_bytes()
    lever_parsed = parse_ats_url("https://jobs.lever.co/kinsta/caadac8e-381f-42a2-9801-202b351fff28")
    assert lever_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=lever_raw))) as client:
        lever_job = await LeverClient().fetch(lever_parsed, client)
    assert lever_job is not None
    assert lever_job.work_model == "remote"

    # 3. Ashby
    ashby_raw = (REAL_FIXTURES_DIR / "ashby" / "linear_board.json").read_bytes()
    ashby_parsed = parse_ats_url("https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff")
    assert ashby_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=ashby_raw))) as client:
        ashby_job = await AshbyClient().fetch(ashby_parsed, client)
    assert ashby_job is not None
    assert ashby_job.work_model == "remote"

    # 4. SmartRecruiters
    sr_raw = (REAL_FIXTURES_DIR / "smartrecruiters" / "job_3743990000051828.json").read_bytes()
    sr_parsed = parse_ats_url("https://jobs.smartrecruiters.com/uber/3743990000051828")
    assert sr_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=sr_raw))) as client:
        sr_job = await SmartRecruitersClient().fetch(sr_parsed, client)
    assert sr_job is not None
    assert sr_job.provider == "smartrecruiters"

    # 5. Workable
    workable_raw = (REAL_FIXTURES_DIR / "workable" / "job_D94DBAF102.md").read_bytes()
    workable_parsed = parse_ats_url("https://apply.workable.com/treq/j/D94DBAF102")
    assert workable_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=workable_raw))) as client:
        workable_job = await WorkableClient().fetch(workable_parsed, client)
    assert workable_job is not None
    assert workable_job.work_model == "in_person"

    # 6. BambooHR
    bamboo_raw = (REAL_FIXTURES_DIR / "bamboohr" / "deel_list.json").read_bytes()
    bamboo_parsed = parse_ats_url("https://deel.bamboohr.com/careers/15")
    assert bamboo_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=bamboo_raw))) as client:
        bamboo_job = await BambooHRClient().fetch(bamboo_parsed, client)
    assert bamboo_job is not None
    # BambooHR locationType "0" is unverified on the public job page, so work_model is None
    assert bamboo_job.work_model is None
    assert bamboo_job.raw_workplace_type == "0"

    # 7. Recruitee
    rec_raw = (REAL_FIXTURES_DIR / "recruitee" / "offer_2774909.json").read_bytes()
    rec_parsed = parse_ats_url("https://miaplaza.recruitee.com/o/2774909-academic-dean")
    assert rec_parsed is not None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=rec_raw))) as client:
        rec_job = await RecruiteeClient().fetch(rec_parsed, client)
    assert rec_job is not None
    assert rec_job.provider == "recruitee"


# ---------------------------------------------------------------------------
# 3. Drop-Rule Safety & URL Parser Coverage for Every Platform
# ---------------------------------------------------------------------------

SAMPLE_JOB_URLS: dict[str, str] = {
    "greenhouse": "https://boards.greenhouse.io/gitlab/jobs/8860302002",
    "lever": "https://jobs.lever.co/kinsta/caadac8e-381f-42a2-9801-202b351fff28",
    "ashby": "https://jobs.ashbyhq.com/linear/d3bc1ced-3ce4-4086-a050-555055dbb1ff",
    "workable": "https://apply.workable.com/treq/j/D94DBAF102",
    "bamboohr": "https://deel.bamboohr.com/careers/15",
    "jobvite": "https://jobs.jobvite.com/company/job/o123456",
    "smartrecruiters": "https://jobs.smartrecruiters.com/uber/3743990000051828",
    "icims": "https://jobs.icims.com/jobs/12345/senior-developer",
    "personio": "https://jobs.personio.com/job/software-engineer-12345",
    "teamtailor": "https://lendurai.teamtailor.com/jobs/8531586-software-engineer",
    "recruitee": "https://miaplaza.recruitee.com/o/2774909-academic-dean",
    "breezy": "https://apply.breezy.hr/p/abc12345/frontend-engineer",
    "workday": "https://mycompany.myworkdayjobs.com/en-US/careers/job/Austin/Senior-Engineer_R12345",
    "taleo": "https://company.taleo.net/careersection/ex/jobdetail.ftl?job=123456",
    "jobadder": "https://apply.jobadder.com/au/tech/12345",
    "jazzhr": "https://applytojob.com/apply/abc123xyz",
    "avature": "https://koch.avature.net/en_US/careers/JobDetail/Data-Scientist/194843",
    "successfactors": "https://jobs.sap.com/job/Walldorf-Developer/1234567800",
}


def test_every_platform_has_at_least_one_parsing_job_url():
    for platform in ATS_PLATFORMS:
        assert platform.name in SAMPLE_JOB_URLS, f"Missing sample URL for {platform.name}"
        sample_url = SAMPLE_JOB_URLS[platform.name]
        parsed = parse_ats_url(sample_url)
        assert parsed is not None, f"Failed to parse sample URL for {platform.name}: {sample_url}"
        assert parsed.ats == platform.name, f"Expected ats={platform.name}, got {parsed.ats}"


def test_every_platform_is_in_supported_ats_patterns():
    for platform in ATS_PLATFORMS:
        assert platform.name in SUPPORTED_ATS_PATTERNS


@pytest.mark.anyio
async def test_unsupported_platform_is_not_dropped_but_routed_to_enrich_ats_page():
    orchestrator = SearchOrchestrator()
    unsupported_url = "https://customats.example.com/jobs/view/123"

    html = """
    <html><head><script type="application/ld+json">
    {"@type":"JobPosting","title":"Platform Lead","datePosted":"2026-09-01",
     "hiringOrganization":{"name":"CustomCorp"}}
    </script></head><body><h1>Platform Lead</h1></body></html>
    """

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, text=html)

    async with httpx.AsyncClient(transport=httpx.MockTransport(mock_handler)) as client:
        # Platform 'custom_unknown_ats' is NOT in SUPPORTED_ATS_PATTERNS
        result = await orchestrator._enrich_ats_item(
            platform="custom_unknown_ats",
            item={"link": unsupported_url, "title": "Platform Lead", "snippet": "A job"},
            query_str="test",
            client=client,
        )

    # Must NOT be dropped (i.e. not None)
    assert result is not None
    assert result.title == "Platform Lead"
    assert result.company == "CustomCorp"
    assert orchestrator._dropped_by_platform.get("custom_unknown_ats", 0) == 0


def test_done_event_exposes_dropped_count():
    event = DoneEvent(
        total=10,
        search_time_ms=120,
        serper_queries_used=1,
        providers_searched=["teamtailor", "greenhouse"],
        providers_skipped=[],
        cached=False,
        dropped_count={"teamtailor": 3, "greenhouse": 0},
    )
    assert event.dropped_count == {"teamtailor": 3, "greenhouse": 0}
