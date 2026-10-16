"""
Capture real job posting fixtures from URLs for regression testing and parser development.

Usage:
    python scripts/capture_fixtures.py [urls.txt]

Reads URLs from urls.txt, fetches each page using the pipeline's HTTP client
and headers, and saves:
    tests/fixtures/real/<provider>/<sha8>.html
    tests/fixtures/real/<provider>/<sha8>.json (sidecar with URL and metadata)
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse

import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.project_files.http_headers import browser_headers
from src.project_files.ats_url_parser import parse_ats_url

KNOWN_PROVIDERS = {
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "ashbyhq.com": "ashby",
    "ashby.com": "ashby",
    "smartrecruiters.com": "smartrecruiters",
    "workable.com": "workable",
    "bamboohr.com": "bamboohr",
    "recruitee.com": "recruitee",
    "teamtailor.com": "teamtailor",
    "personio.com": "personio",
    "personio.de": "personio",
    "jobvite.com": "jobvite",
    "icims.com": "icims",
    "breezy.hr": "breezy",
    "applytojob.com": "jazzhr",
    "jobadder.com": "jobadder",
    "taleo.net": "taleo",
    "avature.net": "avature",
    "myworkdayjobs.com": "workday",
    "jobs.sap.com": "successfactors",
    "jobberman.com": "jobberman",
    "myjobmag.com": "myjobmag",
    "hotnigerianjobs.com": "hotnigerianjobs",
}


def detect_provider(url: str) -> str:
    """Identify the provider name from the ATS parser or domain lookup."""
    try:
        parsed = parse_ats_url(url)
        if parsed and parsed.ats:
            return parsed.ats
    except Exception:
        pass

    netloc = urlparse(url).netloc.lower()
    for domain, provider in KNOWN_PROVIDERS.items():
        if domain in netloc:
            return provider

    # Fallback to secondary domain token if unrecognized
    parts = netloc.split(".")
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"


def capture_url(url: str, output_base: Path, client: httpx.Client) -> Path:
    """Fetch URL and write raw HTML and sidecar JSON metadata."""
    url = url.strip()
    provider = detect_provider(url)
    sha8 = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]

    target_dir = output_base / provider
    target_dir.mkdir(parents=True, exist_ok=True)

    html_file = target_dir / f"{sha8}.html"
    json_file = target_dir / f"{sha8}.json"

    print(f"Fetching [{provider}] {url} -> {html_file.name} ...")
    response = client.get(
        url,
        headers=browser_headers(url),
        timeout=15.0,
        follow_redirects=True,
    )
    response.raise_for_status()

    html_file.write_text(response.text, encoding="utf-8")
    metadata = {
        "url": url,
        "final_url": str(response.url),
        "provider": provider,
        "sha8": sha8,
        "status_code": response.status_code,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    json_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return html_file


def main() -> int:
    urls_file = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "urls.txt"
    if not urls_file.exists():
        print(f"No urls file found at {urls_file}. Create one with one job URL per line.")
        return 1

    urls = [
        line.strip()
        for line in urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not urls:
        print(f"No URLs to fetch in {urls_file}.")
        return 0

    output_base = PROJECT_ROOT / "tests" / "fixtures" / "real"
    output_base.mkdir(parents=True, exist_ok=True)

    success_count = 0
    fail_count = 0

    with httpx.Client() as client:
        for url in urls:
            try:
                capture_url(url, output_base, client)
                success_count += 1
            except Exception as exc:
                print(f"Failed to capture {url}: {exc}")
                fail_count += 1

    print(f"\nDone. Captured {success_count} fixtures ({fail_count} failed).")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
