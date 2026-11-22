"""
Offline fixture builders and transport harnesses for the 9 monitored ATS providers.

Every provider registered in ``BOARD_ADAPTERS`` must have a matching spec here.
All payloads reuse checked-in fixtures under ``tests/fixtures/real/`` and run
100% offline with zero live network or DNS calls.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Callable
import xml.etree.ElementTree as ET

import httpx

from src.safety.url_safety import StaticDnsResolver
from src.storage.company_board_registry import CompanyBoard

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "real"


def _load_json(rel_path: str) -> Any:
    return json.loads((FIXTURES_ROOT / rel_path).read_text(encoding="utf-8"))


def _load_bytes(rel_path: str) -> bytes:
    return (FIXTURES_ROOT / rel_path).read_bytes()


def _pad_description(text: str, marker: str) -> str:
    base = (text or "").strip()
    if len(base) < 320:
        base = f"{base} " + ("Operational engineering context and collaboration details. " * 6)
    return f"{base} {marker}"


def _reverse_dict_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _reverse_dict_keys(v) for k, v in reversed(list(obj.items()))}
    if isinstance(obj, list):
        return [_reverse_dict_keys(v) for v in obj]
    return obj


def _noise_text(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    return f"  {collapsed.replace(' ', '   ')} \n "


@dataclass(frozen=True)
class ProviderConformanceSpec:
    provider: str
    board_token: str
    company_name: str
    board_url: str
    primary_host: str
    extra_dns_hosts: tuple[str, ...]
    supports_http_304: bool
    has_description_in_snapshot: bool
    expected_missing_threshold: int
    build_transport: Callable[[str, dict[str, Any]], httpx.MockTransport]

    def make_board(
        self,
        *,
        board_id: int = 1,
        etag: str | None = None,
        last_modified: str | None = None,
        content_fingerprint: str | None = None,
    ) -> CompanyBoard:
        return CompanyBoard(
            id=board_id,
            company_name=self.company_name,
            company_slug=self.board_token,
            ats_provider=self.provider,
            board_token=self.board_token,
            board_url=self.board_url,
            discovery_source="conformance_test",
            source_posting_url=None,
            first_discovered_at=1000.0,
            last_discovered_at=1000.0,
            verification_status="verified",
            monitoring_capability="supported",
            etag=etag,
            last_modified=last_modified,
            content_fingerprint=content_fingerprint,
            company_logo_checked_at=1000.0,
        )

    def dns_records(self, ip: str = "93.184.216.34") -> dict[str, str]:
        hosts = {self.primary_host, *self.extra_dns_hosts}
        return {h: ip for h in sorted(hosts)}

    def resolver(self, ip: str = "93.184.216.34") -> StaticDnsResolver:
        return StaticDnsResolver(self.dns_records(ip=ip))


def _oversized_body_for_provider(provider: str, size_bytes: int) -> bytes:
    pad = b"x" * size_bytes
    if provider == "lever":
        return b'[{"pad":"' + pad + b'"}]'
    if provider in ("greenhouse", "ashby", "workable"):
        return b'{"jobs":[],"pad":"' + pad + b'"}'
    if provider == "recruitee":
        return b'{"offers":[],"pad":"' + pad + b'"}'
    if provider == "smartrecruiters":
        return b'{"offset":0,"limit":100,"totalFound":0,"content":[],"pad":"' + pad + b'"}'
    if provider == "pinpointhq":
        return b'{"data":[],"pad":"' + pad + b'"}'
    if provider == "teamtailor":
        return b'<?xml version="1.0"?><rss version="2.0"><channel><!--' + pad + b"--></channel></rss>"
    if provider == "personio":
        return b'<?xml version="1.0"?><workzag-jobs><!--' + pad + b"--></workzag-jobs>"
    return b"{" + b" " * size_bytes + b"}"


def _common_error_response(mode: str, request: httpx.Request, *, provider: str = "") -> httpx.Response | None:
    if mode == "http_500":
        return httpx.Response(500, request=request)
    if mode == "http_404":
        return httpx.Response(404, request=request)
    if mode == "http_429":
        return httpx.Response(429, headers={"Retry-After": "5"}, request=request)
    if mode == "timeout":
        raise httpx.ReadTimeout("simulated timeout", request=request)
    if mode == "network":
        raise httpx.ConnectError("simulated network error", request=request)
    if mode == "cancelled":
        raise asyncio.CancelledError()
    if mode == "malformed":
        return httpx.Response(200, content=b"{corrupted<<<payload", request=request)
    if mode == "oversized_content_length":
        body = _oversized_body_for_provider(provider, 4 * 1024 * 1024)
        return httpx.Response(
            200,
            headers={"Content-Length": str(len(body))},
            content=body,
            request=request,
        )
    if mode == "oversized_stream":
        body = _oversized_body_for_provider(provider, 3 * 1024 * 1024 + 8192)
        return httpx.Response(200, content=body, request=request)
    return None


def _transport_from_payload_fn(
    responder: Callable[[httpx.Request, str, dict[str, Any]], httpx.Response],
    mode: str,
    state: dict[str, Any] | None = None,
    *,
    provider: str = "",
) -> httpx.MockTransport:
    ctx = state if state is not None else {}

    def _handler(request: httpx.Request) -> httpx.Response:
        ctx["calls"] = ctx.get("calls", 0) + 1
        err_resp = _common_error_response(mode, request, provider=provider)
        if err_resp is not None:
            return err_resp
        return responder(request, mode, ctx)

    return httpx.MockTransport(_handler)


# ---------------------------------------------------------------------------
# Per-provider offline fixture responders
# ---------------------------------------------------------------------------

def _greenhouse_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    base = _load_json("step54_employers/greenhouse_wikimedia.json")
    jobs = deepcopy(base["jobs"][:3])
    etag = '"gh-v1"'
    last_mod = "Wed, 01 Jul 2026 00:00:00 GMT"

    if mode == "conditional_304" and request.headers.get("If-None-Match") == etag:
        return httpx.Response(304, headers={"ETag": etag, "Last-Modified": last_mod})
    if mode == "empty":
        return httpx.Response(200, json={"jobs": []})
    if mode == "missing_root_shape":
        return httpx.Response(200, json={"meta": {"total": 1}})
    if mode == "duplicate_ids":
        dup = deepcopy(jobs[0])
        return httpx.Response(200, json={"jobs": [jobs[0], dup]})
    if mode == "neutral_adr0001":
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 900001,
                        "title": "Operations Specialist",
                        "absolute_url": "https://job-boards.greenhouse.io/wikimedia/jobs/900001",
                        "location": {"name": ""},
                        "content": "Coordinate internal operations workflows and maintain schedules.",
                        "updated_at": "2026-10-01T10:00:00Z",
                    }
                ]
            },
        )
    if mode == "reordered_whitespace_noise":
        noisy = deepcopy(list(reversed(jobs)))
        noisy[0]["title"] = _noise_text(noisy[0]["title"])
        noisy = _reverse_dict_keys(noisy)
        return httpx.Response(200, json={"jobs": noisy}, headers={"ETag": etag})
    if mode == "edited_title":
        edited = deepcopy(jobs)
        edited[0]["title"] = "Principal Communications Lead (Updated)"
        return httpx.Response(200, json={"jobs": edited})
    if mode == "edited_deep_description":
        edited = deepcopy(jobs)
        edited[0]["content"] = _pad_description(edited[0].get("content") or "", "DEEP_EDIT_MARKER_GH")
        return httpx.Response(200, json={"jobs": edited})
    if mode == "subset_one":
        return httpx.Response(200, json={"jobs": jobs[:1]}, headers={"ETag": '"gh-v2"'})
    if mode == "truncated_snapshot":
        return httpx.Response(500)
    return httpx.Response(200, json={"jobs": jobs}, headers={"ETag": etag, "Last-Modified": last_mod})


def _lever_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    j1 = _load_json("lever/api_1cb2b7f2.json")
    j2 = _load_json("lever/api_624ad7e8.json")
    j2["hostedUrl"] = f"https://jobs.lever.co/tpgsi/{j2['id']}"
    j2["applyUrl"] = f"https://jobs.lever.co/tpgsi/{j2['id']}/apply"
    jobs = [j1, j2]
    etag = '"lv-v1"'
    last_mod = "Wed, 01 Jul 2026 00:00:00 GMT"

    if mode == "conditional_304" and request.headers.get("If-None-Match") == etag:
        return httpx.Response(304, headers={"ETag": etag, "Last-Modified": last_mod})
    if mode == "empty":
        return httpx.Response(200, json=[])
    if mode == "missing_root_shape":
        return httpx.Response(200, json={"jobs": jobs})
    if mode == "duplicate_ids":
        return httpx.Response(200, json=[j1, deepcopy(j1)])
    if mode == "neutral_adr0001":
        return httpx.Response(
            200,
            json=[
                {
                    "id": "00000000-0000-0000-0000-000000000901",
                    "text": "Operations Specialist",
                    "hostedUrl": "https://jobs.lever.co/tpgsi/00000000-0000-0000-0000-000000000901",
                    "applyUrl": "https://jobs.lever.co/tpgsi/00000000-0000-0000-0000-000000000901/apply",
                    "categories": {},
                    "descriptionPlain": "Coordinate internal operations workflows and maintain schedules.",
                    "createdAt": 1793046171052,
                }
            ],
        )
    if mode == "reordered_whitespace_noise":
        noisy = deepcopy(list(reversed(jobs)))
        noisy[0]["text"] = _noise_text(noisy[0]["text"])
        noisy = _reverse_dict_keys(noisy)
        return httpx.Response(200, json=noisy, headers={"ETag": etag})
    if mode == "edited_title":
        edited = deepcopy(jobs)
        edited[0]["text"] = "Staff Full-Stack Software Engineer (Updated)"
        return httpx.Response(200, json=edited)
    if mode == "edited_deep_description":
        edited = deepcopy(jobs)
        edited[0]["descriptionPlain"] = _pad_description(
            edited[0].get("descriptionPlain") or "", "DEEP_EDIT_MARKER_LEVER"
        )
        return httpx.Response(200, json=edited)
    if mode == "subset_one":
        return httpx.Response(200, json=jobs[:1], headers={"ETag": '"lv-v2"'})
    if mode == "truncated_snapshot":
        return httpx.Response(500)
    return httpx.Response(200, json=jobs, headers={"ETag": etag, "Last-Modified": last_mod})


def _ashby_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    base = _load_json("ashby/plaid_board_sample.json")
    jobs = deepcopy(base["jobs"][:3])
    etag = '"ab-v1"'
    last_mod = "Wed, 01 Jul 2026 00:00:00 GMT"

    if mode == "conditional_304" and request.headers.get("If-None-Match") == etag:
        return httpx.Response(304, headers={"ETag": etag, "Last-Modified": last_mod})
    if mode == "empty":
        return httpx.Response(200, json={"jobs": []})
    if mode == "missing_root_shape":
        return httpx.Response(200, json={"apiVersion": "1"})
    if mode == "duplicate_ids":
        return httpx.Response(200, json={"jobs": [jobs[0], deepcopy(jobs[0])]})
    if mode == "neutral_adr0001":
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": "neutral-ashby-1",
                        "title": "Operations Specialist",
                        "jobUrl": "https://jobs.ashbyhq.com/plaid/neutral-ashby-1",
                        "location": "",
                        "descriptionPlain": "Coordinate internal operations workflows and maintain schedules.",
                        "publishedAt": "2026-10-01T10:00:00Z",
                    }
                ]
            },
        )
    if mode == "reordered_whitespace_noise":
        noisy = deepcopy(list(reversed(jobs)))
        noisy[0]["title"] = _noise_text(noisy[0]["title"])
        noisy = _reverse_dict_keys(noisy)
        return httpx.Response(200, json={"jobs": noisy}, headers={"ETag": etag})
    if mode == "edited_title":
        edited = deepcopy(jobs)
        edited[0]["title"] = "Principal Strategic Initiatives (Updated)"
        return httpx.Response(200, json={"jobs": edited})
    if mode == "edited_deep_description":
        edited = deepcopy(jobs)
        edited[0]["descriptionPlain"] = _pad_description(
            edited[0].get("descriptionPlain") or "", "DEEP_EDIT_MARKER_ASHBY"
        )
        return httpx.Response(200, json={"jobs": edited})
    if mode == "subset_one":
        return httpx.Response(200, json={"jobs": jobs[:1]}, headers={"ETag": '"ab-v2"'})
    if mode == "truncated_snapshot":
        return httpx.Response(500)
    return httpx.Response(200, json={"jobs": jobs}, headers={"ETag": etag, "Last-Modified": last_mod})


def _workable_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    url_str = str(request.url)
    widget = _load_json("workable/widget_verneek.json")
    # Pick 2 jobs including 3DBA754691 (whose real detail fixture exists)
    selected = [j for j in widget["jobs"] if j.get("shortcode") in ("A8DB68FCC3", "3DBA754691")]
    widget_base = {"name": widget.get("name", "Verneek"), "jobs": deepcopy(selected)}
    detail_real = _load_json("workable/job_verneek_3DBA754691.json")
    etag = '"wk-v1"'
    last_mod = "Wed, 01 Jul 2026 00:00:00 GMT"

    if "/api/v2/accounts/" in url_str:
        sc = url_str.rstrip("/").rsplit("/", 1)[-1]
        if sc == "neutral01":
            return httpx.Response(
                200,
                json={
                    "id": 99901,
                    "shortcode": "neutral01",
                    "title": "Operations Specialist",
                    "state": "published",
                    "location": {"country": "", "city": ""},
                    "description": "<p>Coordinate internal operations workflows and maintain schedules.</p>",
                },
            )
        detail = deepcopy(detail_real)
        detail["shortcode"] = sc
        for j in selected:
            if j.get("shortcode") == sc:
                detail["title"] = j["title"]
        return httpx.Response(200, json=detail)

    if mode == "conditional_304" and request.headers.get("If-None-Match") == etag:
        return httpx.Response(304, headers={"ETag": etag, "Last-Modified": last_mod})
    if mode == "empty":
        return httpx.Response(200, json={"name": "Verneek", "jobs": []})
    if mode == "missing_root_shape":
        return httpx.Response(200, json={"name": "Verneek"})
    if mode == "duplicate_ids":
        return httpx.Response(200, json={"name": "Verneek", "jobs": [selected[0], deepcopy(selected[0])]})
    if mode == "neutral_adr0001":
        return httpx.Response(
            200,
            json={
                "name": "Verneek",
                "jobs": [
                    {
                        "title": "Operations Specialist",
                        "shortcode": "neutral01",
                        "url": "https://apply.workable.com/j/neutral01",
                        "published_on": "2026-10-01",
                        "locations": [],
                    }
                ],
            },
        )
    if mode == "reordered_whitespace_noise":
        noisy_jobs = deepcopy(list(reversed(selected)))
        noisy_jobs[0]["title"] = _noise_text(noisy_jobs[0]["title"])
        noisy_jobs = _reverse_dict_keys(noisy_jobs)
        return httpx.Response(200, json={"name": "Verneek", "jobs": noisy_jobs}, headers={"ETag": etag})
    if mode == "edited_title":
        edited = deepcopy(widget_base)
        edited["jobs"][0]["title"] = "Principal ML Architect (Updated)"
        return httpx.Response(200, json=edited)
    if mode == "edited_deep_description":
        edited = deepcopy(widget_base)
        edited["jobs"][0]["department"] = "Applied Research Systems Updated Division"
        return httpx.Response(200, json=edited)
    if mode == "subset_one":
        return httpx.Response(200, json={"name": "Verneek", "jobs": selected[:1]}, headers={"ETag": '"wk-v2"'})
    if mode == "truncated_snapshot":
        return httpx.Response(500)
    return httpx.Response(200, json=widget_base, headers={"ETag": etag, "Last-Modified": last_mod})


def _recruitee_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    base = _load_json("recruitee/dransay_offers.json")
    offers = deepcopy(base["offers"][:3])
    etag = '"rc-v1"'
    last_mod = "Wed, 01 Jul 2026 00:00:00 GMT"

    if mode == "conditional_304" and request.headers.get("If-None-Match") == etag:
        return httpx.Response(304, headers={"ETag": etag, "Last-Modified": last_mod})
    if mode == "empty":
        return httpx.Response(200, json={"offers": []})
    if mode == "missing_root_shape":
        return httpx.Response(200, json={"data": []})
    if mode == "duplicate_ids":
        return httpx.Response(200, json={"offers": [offers[0], deepcopy(offers[0])]})
    if mode == "neutral_adr0001":
        return httpx.Response(
            200,
            json={
                "offers": [
                    {
                        "id": 900001,
                        "slug": "operations-specialist",
                        "title": "Operations Specialist",
                        "status": "published",
                        "careers_url": "https://dransay.recruitee.com/o/operations-specialist",
                        "description": "<p>Coordinate internal operations workflows and maintain schedules.</p>",
                        "created_at": "2026-10-01T10:00:00Z",
                    }
                ]
            },
        )
    if mode == "reordered_whitespace_noise":
        noisy = deepcopy(list(reversed(offers)))
        noisy[0]["title"] = _noise_text(noisy[0]["title"])
        noisy = _reverse_dict_keys(noisy)
        return httpx.Response(200, json={"offers": noisy}, headers={"ETag": etag})
    if mode == "edited_title":
        edited = deepcopy(offers)
        edited[0]["title"] = "Senior Operations Partner (Updated)"
        return httpx.Response(200, json={"offers": edited})
    if mode == "edited_deep_description":
        edited = deepcopy(offers)
        edited[0]["description"] = _pad_description(
            edited[0].get("description") or "", "DEEP_EDIT_MARKER_RECRUITEE"
        )
        return httpx.Response(200, json={"offers": edited})
    if mode == "subset_one":
        return httpx.Response(200, json={"offers": offers[:1]}, headers={"ETag": '"rc-v2"'})
    if mode == "truncated_snapshot":
        return httpx.Response(500)
    return httpx.Response(200, json={"offers": offers}, headers={"ETag": etag, "Last-Modified": last_mod})


def _smartrecruiters_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    url_str = str(request.url)
    list_base = _load_json("smartrecruiters/nearmap_postings.json")
    detail_real = _load_json("smartrecruiters/nearmap_744000161158698_detail.json")
    subset = deepcopy(list_base["content"][:2])
    base_page = {"offset": 0, "limit": 100, "totalFound": len(subset), "content": subset}

    if "/postings/" in url_str:
        pid = url_str.rstrip("/").split("/")[-1].split("?")[0]
        if pid == "9999990001":
            return httpx.Response(
                200,
                json={
                    "id": "9999990001",
                    "name": "Operations Specialist",
                    "postingUrl": "https://jobs.smartrecruiters.com/Nearmap/9999990001",
                    "applyUrl": "https://jobs.smartrecruiters.com/Nearmap/9999990001/apply",
                    "releasedDate": "2026-10-01T10:00:00.000Z",
                    "location": {},
                    "jobAd": {"sections": {"jobDescription": {"text": "<p>Coordinate internal operations workflows and maintain schedules.</p>"}}},
                    "visibility": "PUBLIC",
                    "company": {"name": "Nearmap", "identifier": "Nearmap"},
                },
            )
        d = deepcopy(detail_real)
        d["id"] = pid
        for item in subset:
            if str(item["id"]) == pid:
                d["name"] = item["name"]
        return httpx.Response(200, json=d)

    if mode == "empty":
        return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 0, "content": []})
    if mode == "missing_root_shape":
        return httpx.Response(200, json={"content": subset})
    if mode == "duplicate_ids":
        return httpx.Response(
            200,
            json={"offset": 0, "limit": 100, "totalFound": 2, "content": [subset[0], deepcopy(subset[0])]},
        )
    if mode == "neutral_adr0001":
        return httpx.Response(
            200,
            json={
                "offset": 0,
                "limit": 100,
                "totalFound": 1,
                "content": [
                    {
                        "id": "9999990001",
                        "name": "Operations Specialist",
                        "visibility": "PUBLIC",
                        "releasedDate": "2026-10-01T10:00:00.000Z",
                        "ref": "https://api.smartrecruiters.com/v1/companies/Nearmap/postings/9999990001",
                        "company": {"identifier": "Nearmap", "name": "Nearmap"},
                    }
                ],
            },
        )
    if mode == "reordered_whitespace_noise":
        noisy = deepcopy(list(reversed(subset)))
        noisy[0]["name"] = _noise_text(noisy[0]["name"])
        noisy = _reverse_dict_keys(noisy)
        return httpx.Response(
            200,
            json={"offset": 0, "limit": 100, "totalFound": len(noisy), "content": noisy},
        )
    if mode == "edited_title":
        edited = deepcopy(subset)
        edited[0]["name"] = "Principal Enterprise Account Executive (Updated)"
        return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": len(edited), "content": edited})
    if mode == "edited_deep_description":
        edited = deepcopy(subset)
        edited[0]["customField"] = [{"fieldId": "deep", "valueLabel": "DEEP_EDIT_MARKER_SR"}]
        return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": len(edited), "content": edited})
    if mode == "subset_one":
        return httpx.Response(200, json={"offset": 0, "limit": 100, "totalFound": 1, "content": subset[:1]})
    if mode == "truncated_snapshot":
        offset = int(request.url.params.get("offset", "0"))
        if offset == 0:
            p0 = _load_json("smartrecruiters/scalable_postings_p0.json")
            # Normalize company identifier to nearmap for token match while testing mid-pagination truncation
            for entry in p0["content"]:
                entry["company"] = {"identifier": "Nearmap", "name": "Nearmap"}
                entry["ref"] = f"https://api.smartrecruiters.com/v1/companies/Nearmap/postings/{entry['id']}"
            return httpx.Response(200, json=p0)
        return httpx.Response(500)
    return httpx.Response(200, json=base_page)


def _trim_teamtailor_xml(xml_bytes: bytes, *, count: int | None = None, reverse: bool = False, noise: bool = False, dup: bool = False, edit_title: bool = False, edit_deep_desc: bool = False) -> bytes:
    ET.register_namespace("tt", "https://teamtailor.com/locations")
    root = ET.fromstring(xml_bytes.decode("utf-8"))
    channel = root.find("channel")
    assert channel is not None
    items = list(channel.findall("item"))
    if count is not None:
        items = items[:count]
    for old in list(channel.findall("item")):
        channel.remove(old)
    if dup and items:
        items = [items[0], deepcopy(items[0])]
    if reverse:
        items = list(reversed(items))
    for idx, it in enumerate(items):
        if noise and idx == 0:
            t_el = it.find("title")
            if t_el is not None and t_el.text:
                t_el.text = _noise_text(t_el.text)
            d_el = it.find("description")
            if d_el is not None and d_el.text:
                d_el.text = _noise_text(d_el.text)
        if edit_title and idx == 0:
            t_el = it.find("title")
            if t_el is not None:
                t_el.text = "Principal Audit Manager (Updated)"
        if edit_deep_desc and idx == 0:
            d_el = it.find("description")
            if d_el is not None:
                d_el.text = _pad_description(d_el.text or "", "DEEP_EDIT_MARKER_TT")
        channel.append(it)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _teamtailor_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    raw = _load_bytes("teamtailor/gravita_rss.xml")
    etag = '"tt-v1"'
    last_mod = "Wed, 01 Jul 2026 00:00:00 GMT"
    url_str = str(request.url)

    if mode == "truncated_snapshot":
        if "/jobs.rss" in url_str:
            ET.register_namespace("tt", "https://teamtailor.com/locations")
            root = ET.fromstring(raw.decode("utf-8"))
            ch = root.find("channel")
            assert ch is not None
            template = ch.findall("item")[0]
            for old in list(ch.findall("item")):
                ch.remove(old)
            for idx in range(100):
                item_el = deepcopy(template)
                link_el = item_el.find("link")
                guid_el = item_el.find("guid")
                if link_el is not None:
                    link_el.text = f"https://careers.gravita.com/jobs/{8670000 + idx}-role-{idx}"
                if guid_el is not None:
                    guid_el.text = f"guid-{idx}"
                ch.append(item_el)
            return httpx.Response(200, content=ET.tostring(root, encoding="utf-8", xml_declaration=True))
        return httpx.Response(500)

    if mode == "conditional_304" and request.headers.get("If-None-Match") == etag:
        return httpx.Response(304, headers={"ETag": etag, "Last-Modified": last_mod})
    if mode == "empty":
        empty_rss = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<rss version="2.0"><channel><title>Gravita</title></channel></rss>'
        )
        return httpx.Response(200, content=empty_rss)
    if mode == "missing_root_shape":
        return httpx.Response(200, content=b'<?xml version="1.0"?><rss version="2.0"></rss>')
    if mode == "duplicate_ids":
        return httpx.Response(200, content=_trim_teamtailor_xml(raw, count=1, dup=True))
    if mode == "neutral_adr0001":
        neutral_rss = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<rss version="2.0"><channel><title>Gravita</title>'
            b"<item><title>Operations Specialist</title>"
            b"<link>https://careers.gravita.com/jobs/9000001-operations-specialist</link>"
            b"<description>&lt;p&gt;Coordinate internal operations workflows and maintain schedules.&lt;/p&gt;</description>"
            b"<pubDate>Thu, 01 Oct 2026 10:00:00 +0000</pubDate>"
            b"</item></channel></rss>"
        )
        return httpx.Response(200, content=neutral_rss)
    if mode == "reordered_whitespace_noise":
        return httpx.Response(
            200,
            content=_trim_teamtailor_xml(raw, count=3, reverse=True, noise=True),
            headers={"ETag": etag},
        )
    if mode == "edited_title":
        return httpx.Response(200, content=_trim_teamtailor_xml(raw, count=3, edit_title=True))
    if mode == "edited_deep_description":
        return httpx.Response(200, content=_trim_teamtailor_xml(raw, count=3, edit_deep_desc=True))
    if mode == "subset_one":
        return httpx.Response(200, content=_trim_teamtailor_xml(raw, count=1), headers={"ETag": '"tt-v2"'})
    return httpx.Response(
        200,
        content=_trim_teamtailor_xml(raw, count=3),
        headers={"ETag": etag, "Last-Modified": last_mod},
    )


def _trim_personio_xml(
    xml_bytes: bytes,
    *,
    count: int | None = None,
    reverse: bool = False,
    noise: bool = False,
    dup: bool = False,
    edit_title: bool = False,
    edit_deep_desc: bool = False,
    id_override: str | None = None,
) -> bytes:
    root = ET.fromstring(xml_bytes.decode("utf-8"))
    positions = list(root.findall("position"))
    if count is not None:
        positions = positions[:count]
    for old in list(root.findall("position")):
        root.remove(old)
    if dup and positions:
        positions = [positions[0], deepcopy(positions[0])]
    if reverse:
        positions = list(reversed(positions))
    for idx, pos in enumerate(positions):
        if id_override and idx == 0:
            id_el = pos.find("id")
            if id_el is not None:
                id_el.text = id_override
        if noise and idx == 0:
            name_el = pos.find("name")
            if name_el is not None and name_el.text:
                name_el.text = _noise_text(name_el.text)
            for v_el in pos.findall("./jobDescriptions/jobDescription/value"):
                if v_el.text:
                    v_el.text = _noise_text(v_el.text)
        if edit_title and idx == 0:
            name_el = pos.find("name")
            if name_el is not None:
                name_el.text = "Lead CNC Specialist (Updated)"
        if edit_deep_desc and idx == 0:
            val_el = pos.find("./jobDescriptions/jobDescription/value")
            if val_el is None:
                jds = pos.find("jobDescriptions")
                if jds is None:
                    jds = ET.SubElement(pos, "jobDescriptions")
                jd = ET.SubElement(jds, "jobDescription")
                val_el = ET.SubElement(jd, "value")
            val_el.text = _pad_description(val_el.text or "", "DEEP_EDIT_MARKER_PERSONIO")
        root.append(pos)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _personio_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    en_raw = _load_bytes("personio/saeki_xml_en.xml")
    def_raw = _load_bytes("personio/saeki_xml_default.xml")
    is_en = "language=en" in str(request.url)
    en_etag = '"pe-en-v1"'
    def_etag = '"pe-def-v1"'
    req_inm = request.headers.get("If-None-Match")

    if mode == "conditional_304":
        expected = en_etag if is_en else def_etag
        if req_inm == expected:
            return httpx.Response(304, headers={"ETag": expected})
    if mode == "empty":
        empty_file = "personio/traviangames_xml_empty_en.xml" if is_en else "personio/traviangames_xml_empty.xml"
        return httpx.Response(200, content=_load_bytes(empty_file))
    if mode == "missing_root_shape":
        return httpx.Response(200, content=b'<?xml version="1.0"?><wrong-root></wrong-root>')
    if mode == "duplicate_ids":
        return httpx.Response(200, content=_trim_personio_xml(en_raw, count=1, dup=True))
    if mode == "truncated_snapshot":
        if is_en:
            # Remove description from first item to force default /xml fallback
            root = ET.fromstring(_trim_personio_xml(en_raw, count=1).decode("utf-8"))
            jds = root.find("./position/jobDescriptions")
            if jds is not None:
                root.find("./position").remove(jds)
            return httpx.Response(200, content=ET.tostring(root, encoding="utf-8", xml_declaration=True))
        return httpx.Response(200, content=_trim_personio_xml(def_raw, count=1, id_override="9999999"))
    if mode == "neutral_adr0001":
        neutral_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b"<workzag-jobs><position>"
            b"<id>900001</id><name>Operations Specialist</name>"
            b"<office></office>"
            b"<jobDescriptions><jobDescription><name>Overview</name>"
            b"<value>Coordinate internal operations workflows and maintain schedules.</value>"
            b"</jobDescription></jobDescriptions>"
            b"<createdAt>2026-10-01T10:00:00+00:00</createdAt>"
            b"</position></workzag-jobs>"
        )
        return httpx.Response(200, content=neutral_xml)
    if mode == "reordered_whitespace_noise":
        src_raw = en_raw if is_en else def_raw
        return httpx.Response(
            200,
            content=_trim_personio_xml(src_raw, count=3, reverse=True, noise=True),
            headers={"ETag": en_etag if is_en else def_etag},
        )
    if mode == "edited_title":
        src_raw = en_raw if is_en else def_raw
        return httpx.Response(200, content=_trim_personio_xml(src_raw, count=3, edit_title=True))
    if mode == "edited_deep_description":
        src_raw = en_raw if is_en else def_raw
        return httpx.Response(200, content=_trim_personio_xml(src_raw, count=3, edit_deep_desc=True))
    if mode == "subset_one":
        src_raw = en_raw if is_en else def_raw
        return httpx.Response(200, content=_trim_personio_xml(src_raw, count=1), headers={"ETag": '"pe-v2"'})
    src_raw = en_raw if is_en else def_raw
    return httpx.Response(
        200,
        content=_trim_personio_xml(src_raw, count=3),
        headers={"ETag": en_etag if is_en else def_etag},
    )


def _pinpoint_responder(request: httpx.Request, mode: str, state: dict[str, Any]) -> httpx.Response:
    base = _load_json("pinpointhq/bizimply_postings.json")
    items = deepcopy(base["data"])
    etag = 'W/"pp-v1"'
    last_mod = "Wed, 01 Jul 2026 00:00:00 GMT"

    if mode == "conditional_304" and request.headers.get("If-None-Match") == etag:
        return httpx.Response(304, headers={"ETag": etag, "Last-Modified": last_mod})
    if mode == "empty":
        return httpx.Response(200, json=_load_json("pinpointhq/calligo_postings_empty.json"))
    if mode == "missing_root_shape":
        return httpx.Response(200, json={"meta": {"total": 2}})
    if mode == "duplicate_ids":
        return httpx.Response(200, json={"data": [items[0], deepcopy(items[0])]})
    if mode == "neutral_adr0001":
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "900001",
                        "title": "Operations Specialist",
                        "url": "https://bizimply.pinpointhq.com/en/postings/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "path": "/en/postings/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                        "location": {},
                        "description": "<p>Coordinate internal operations workflows and maintain schedules.</p>",
                    }
                ]
            },
        )
    if mode == "reordered_whitespace_noise":
        noisy = deepcopy(list(reversed(items)))
        noisy[0]["title"] = _noise_text(noisy[0]["title"])
        noisy[0]["description"] = _noise_text(noisy[0].get("description") or "")
        noisy = _reverse_dict_keys(noisy)
        return httpx.Response(200, json={"data": noisy}, headers={"ETag": etag})
    if mode == "edited_title":
        edited = deepcopy(items)
        edited[0]["title"] = "Principal Account Executive (Updated)"
        return httpx.Response(200, json={"data": edited})
    if mode == "edited_deep_description":
        edited = deepcopy(items)
        edited[0]["description"] = _pad_description(
            edited[0].get("description") or "", "DEEP_EDIT_MARKER_PINPOINT"
        )
        return httpx.Response(200, json={"data": edited})
    if mode == "subset_one":
        return httpx.Response(200, json={"data": items[:1]}, headers={"ETag": 'W/"pp-v2"'})
    if mode == "truncated_snapshot":
        return httpx.Response(500)
    return httpx.Response(200, json={"data": items}, headers={"ETag": etag, "Last-Modified": last_mod})


def _make_transport_factory(
    responder: Callable[[httpx.Request, str, dict[str, Any]], httpx.Response],
    *,
    provider: str = "",
):
    def _build(mode: str, state: dict[str, Any] | None = None) -> httpx.MockTransport:
        return _transport_from_payload_fn(responder, mode, state, provider=provider)

    return _build


PROVIDER_SPECS: dict[str, ProviderConformanceSpec] = {
    "greenhouse": ProviderConformanceSpec(
        provider="greenhouse",
        board_token="wikimedia",
        company_name="Wikimedia Foundation",
        board_url="https://boards.greenhouse.io/wikimedia",
        primary_host="boards-api.greenhouse.io",
        extra_dns_hosts=(),
        supports_http_304=True,
        has_description_in_snapshot=True,
        expected_missing_threshold=1,
        build_transport=_make_transport_factory(_greenhouse_responder, provider="greenhouse"),
    ),
    "lever": ProviderConformanceSpec(
        provider="lever",
        board_token="tpgsi",
        company_name="Turning Point Global Solutions",
        board_url="https://jobs.lever.co/tpgsi",
        primary_host="api.lever.co",
        extra_dns_hosts=(),
        supports_http_304=True,
        has_description_in_snapshot=True,
        expected_missing_threshold=1,
        build_transport=_make_transport_factory(_lever_responder, provider="lever"),
    ),
    "ashby": ProviderConformanceSpec(
        provider="ashby",
        board_token="plaid",
        company_name="Plaid",
        board_url="https://jobs.ashbyhq.com/plaid",
        primary_host="api.ashbyhq.com",
        extra_dns_hosts=(),
        supports_http_304=True,
        has_description_in_snapshot=True,
        expected_missing_threshold=1,
        build_transport=_make_transport_factory(_ashby_responder, provider="ashby"),
    ),
    "workable": ProviderConformanceSpec(
        provider="workable",
        board_token="verneek",
        company_name="Verneek",
        board_url="https://apply.workable.com/verneek",
        primary_host="apply.workable.com",
        extra_dns_hosts=(),
        supports_http_304=True,
        has_description_in_snapshot=False,
        expected_missing_threshold=1,
        build_transport=_make_transport_factory(_workable_responder, provider="workable"),
    ),
    "recruitee": ProviderConformanceSpec(
        provider="recruitee",
        board_token="dransay",
        company_name="Dransay",
        board_url="https://dransay.recruitee.com",
        primary_host="dransay.recruitee.com",
        extra_dns_hosts=(),
        supports_http_304=True,
        has_description_in_snapshot=True,
        expected_missing_threshold=1,
        build_transport=_make_transport_factory(_recruitee_responder, provider="recruitee"),
    ),
    "smartrecruiters": ProviderConformanceSpec(
        provider="smartrecruiters",
        board_token="nearmap",
        company_name="Nearmap",
        board_url="https://jobs.smartrecruiters.com/Nearmap",
        primary_host="api.smartrecruiters.com",
        extra_dns_hosts=(),
        supports_http_304=False,
        has_description_in_snapshot=False,
        expected_missing_threshold=2,
        build_transport=_make_transport_factory(_smartrecruiters_responder, provider="smartrecruiters"),
    ),
    "teamtailor": ProviderConformanceSpec(
        provider="teamtailor",
        board_token="gravita",
        company_name="Gravita",
        board_url="https://gravita.teamtailor.com",
        primary_host="gravita.teamtailor.com",
        extra_dns_hosts=("careers.gravita.com",),
        supports_http_304=True,
        has_description_in_snapshot=True,
        expected_missing_threshold=2,
        build_transport=_make_transport_factory(_teamtailor_responder, provider="teamtailor"),
    ),
    "personio": ProviderConformanceSpec(
        provider="personio",
        board_token="saeki",
        company_name="SAEKI Robotics",
        board_url="https://saeki.jobs.personio.com",
        primary_host="saeki.jobs.personio.com",
        extra_dns_hosts=(),
        supports_http_304=True,
        has_description_in_snapshot=True,
        expected_missing_threshold=2,
        build_transport=_make_transport_factory(_personio_responder, provider="personio"),
    ),
    "pinpointhq": ProviderConformanceSpec(
        provider="pinpointhq",
        board_token="bizimply",
        company_name="Bizimply",
        board_url="https://bizimply.pinpointhq.com",
        primary_host="bizimply.pinpointhq.com",
        extra_dns_hosts=(),
        supports_http_304=True,
        has_description_in_snapshot=True,
        expected_missing_threshold=2,
        build_transport=_make_transport_factory(_pinpoint_responder, provider="pinpointhq"),
    ),
}

ALL_PROVIDERS: tuple[str, ...] = tuple(PROVIDER_SPECS.keys())
