"""
Nigerian job board scrapers for Jobberman, MyJobMag, NgCareers, and HotNigerianJobs.
Performs direct HTML scraping using httpx and BeautifulSoup.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
import urllib.parse
from datetime import datetime, timezone
from typing import List

from bs4 import BeautifulSoup
import httpx
from loguru import logger

from src.config import settings
from src.project_files.exceptions import BotBlockError, RateLimitError
from src.project_files.field_normalizer import (
    extract_labeled_fields,
    normalize_fields,
    normalize_job_type_from_text,
    parse_datetime,
    resolve_work_model,
)
from src.project_files.models import JobListing, SearchParams

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

CHALLENGE_TITLE_KEYWORDS = [
    "just a moment",
    "attention required",
    "security check",
    "access denied",
    "bot verification",
    "verify you are human",
    "robot or human",
    "cloudflare",
]

CHALLENGE_BODY_PHRASES = [
    "enable cookies and reload the page",
    "checking your browser before accessing",
    "please enable javascript to view this page",
    "complete the security check to continue",
    "unusual traffic from your computer network",
]


def _make_scraped_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _check_bot_block(html: str, site: str) -> None:
    lower_html = html.lower()
    title_match = re.search(r"<title[^>]*>(.*?)</title>", lower_html, re.DOTALL)
    if title_match:
        title_text = title_match.group(1).strip()
        for kw in CHALLENGE_TITLE_KEYWORDS:
            if kw in title_text:
                raise BotBlockError(site)

    if any(
        marker in lower_html
        for marker in (
            'id="challenge-running"',
            'class="cf-browser-verification"',
            'id="challenge-form"',
        )
    ):
        raise BotBlockError(site)

    for phrase in CHALLENGE_BODY_PHRASES:
        if phrase in lower_html:
            raise BotBlockError(site)


def _extract_card_metadata(card: BeautifulSoup) -> dict:
    """Extract only metadata explicitly present in a Nigerian listing card."""
    text = card.get_text(" ", strip=True)
    labeled = extract_labeled_fields(text)
    date_value = None
    date_node = card.select_one("time[datetime], time, [data-posted], [data-date-posted], li#job-date, [id*='date'], span.semibio, .semibio")
    if date_node:
        date_value = date_node.get("datetime") or date_node.get("data-posted") or date_node.get("data-date-posted") or date_node.get_text(" ", strip=True)
    if not date_value:
        date_match = re.search(r"(?:posted|published)\s*(?:on)?\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        date_value = date_match.group(1) if date_match else None

    # Handle partial dates like '13 October'
    if date_value and re.match(r"^\d{1,2}\s+[a-zA-Z]+$", date_value.strip()):
        current_year = datetime.now(timezone.utc).year
        date_value = f"{date_value.strip()} {current_year}"

    # Extract salary if present
    salary_match = re.search(
        r"(?:(?:NGN|₦|\$|£|€)\s*[\d,]+(?:\s*-\s*(?:NGN|₦|\$|£|€|N)?\s*[\d,]+)?(?:\s*/\s*\w+)?)"
        r"|(?:\bSalary\s*:\s*N\s*[\d,]+(?:\s*-\s*N?\s*[\d,]+)?(?:\s+(?:net\s+)?(?:monthly|per\s+month|annually|per\s+annum))?)",
        text,
        re.IGNORECASE,
    )
    salary_str = re.sub(r"^Salary\s*:\s*", "", salary_match.group(0), flags=re.IGNORECASE).strip() if salary_match else None

    json_ld = None
    for script in card.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        values = payload if isinstance(payload, list) else [payload]
        json_ld = next((item for item in values if isinstance(item, dict) and item.get("@type") == "JobPosting"), None)
        if json_ld:
            break

    if json_ld:
        labeled = {**labeled, **extract_labeled_fields(json.dumps(json_ld))}
        if json_ld.get("employmentType"):
            labeled["employment_type"] = json_ld["employmentType"]
        if json_ld.get("jobLocationType"):
            labeled["work_model"] = json_ld["jobLocationType"]
        if json_ld.get("datePosted"):
            date_value = json_ld["datePosted"]
        if json_ld.get("department"):
            labeled["department"] = json_ld["department"] if isinstance(json_ld["department"], str) else json_ld["department"].get("name")

    work_model_cand = labeled.get("work_model")
    if not work_model_cand:
        for elem in card.select("span, div, p"):
            b = elem.get_text(strip=True)
            if 0 < len(b) < 60 and re.search(r"\b(?:remote|hybrid|on-?site|work from home|wfh)\b", b, re.IGNORECASE):
                work_model_cand = b
                break

    fields = normalize_fields(
        title=None,
        snippet=text,
        location=labeled.get("location"),
        employment_type=labeled.get("employment_type"),
        work_model=work_model_cand,
        department=labeled.get("department"),
    )
    return {
        "location": fields["location"],
        "employment_type": fields["employment_type"],
        "work_model": fields["work_model"],
        "work_model_source": fields["work_model_source"],
        "work_model_evidence": fields["work_model_evidence"],
        "department": fields["department"],
        "is_remote": fields["is_remote"],
        "posted_at": parse_datetime(date_value),
        "salary": salary_str,
    }


class BaseScraper:
    site_name: str
    base_url: str

    def get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": self.base_url,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        headers = self.get_headers()
        timeout = httpx.Timeout(settings.scraper_request_timeout_seconds)
        response = await client.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        if response.status_code == 429:
            raise RateLimitError(self.site_name)
        response.raise_for_status()
        html = response.text
        _check_bot_block(html, self.site_name)
        return html

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        raise NotImplementedError


class JobbermanScraper(BaseScraper):
    site_name: str = "jobberman"
    base_url: str = "https://www.jobberman.com"

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        query_param = urllib.parse.quote_plus(params.job_title)
        url = f"{self.base_url}/jobs?q={query_param}"
        if params.location:
            url += f"&l={urllib.parse.quote_plus(params.location)}"

        html = ""
        try:
            html = await self.fetch_html(client, url)
        except RateLimitError:
            logger.warning(f"[{self.site_name}] HTTP 429 encountered. Waiting 5s for single retry.")
            await asyncio.sleep(5)
            try:
                html = await self.fetch_html(client, url)
            except Exception as e:
                logger.warning(f"[{self.site_name}] Retry failed: {e}")
                return listings
        except BotBlockError as e:
            logger.warning(f"[{self.site_name}] Bot block detected: {e}")
            return listings
        except Exception as e:
            logger.warning(f"[{self.site_name}] Scraping error: {e}")
            return listings

        if not html:
            return listings

        try:
            soup = BeautifulSoup(html, "lxml")
            cards = soup.select("article, div[data-cy='listing-cards-components'], div.mx-5, div.flex-grow")
            now = datetime.now(timezone.utc)

            for card in cards:
                title_elem = card.select_one(
                    "a[data-cy='listing-title-link'], a[href*='/listings/'], h3 a, h2 a, a[data-cy='listing-title']"
                )
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")
                if not href or not title:
                    continue
                apply_url = urllib.parse.urljoin(self.base_url, href)

                company_elem = card.select_one(
                    "a[href*='/employer/'], a[href*='/employers/'], p.text-blue-700, p[class*='text-blue'], span[class*='company']"
                )
                company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
                if company in ("Engineering & Technology", "Software & Data", "IT & Telecoms"):
                    alt_elem = card.select_one("a[href*='/employer/'], a[href*='/employers/'], p.text-blue-700")
                    if alt_elem and alt_elem != company_elem:
                        company = alt_elem.get_text(strip=True)

                loc_elem = card.select_one("span[class*='location'], span[class*='badge'], span.text-gray-500")
                loc = loc_elem.get_text(strip=True) if loc_elem else params.location
                metadata = _extract_card_metadata(card)

                listing_id = _make_scraped_id(apply_url)
                listings.append(
                    JobListing(
                        id=listing_id,
                        provider=self.site_name,
                        data_source="scrape",
                        title=title,
                        company=company,
                        company_slug=None,
                        location=loc,
                        is_remote=metadata["is_remote"],
                        employment_type=metadata["employment_type"],
                        work_model=metadata["work_model"],
                        department=metadata["department"],
                        salary=metadata.get("salary"),
                        posted_at=metadata["posted_at"],
                        scraped_at=now,
                        apply_url=apply_url,
                        source_url=apply_url,
                        query_used=params.job_title,
                        ats_source=self.site_name,
                    )
                )
        except Exception as e:
            logger.warning(f"[{self.site_name}] Parsing error: {e}")

        return listings


class MyJobMagScraper(BaseScraper):
    site_name: str = "myjobmag"
    base_url: str = "https://www.myjobmag.com"

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        query_param = urllib.parse.quote_plus(params.job_title)
        url = f"{self.base_url}/search/jobs?q={query_param}"
        if params.location:
            url += f"&location={urllib.parse.quote_plus(params.location)}"

        try:
            html = await self.fetch_html(client, url)
            if not html:
                return listings
            soup = BeautifulSoup(html, "lxml")
            items = soup.select("li.job-list-li")
            if not items:
                items = soup.select("li.job-info, li.job-item")
            now = datetime.now(timezone.utc)
            seen_ids: set[str] = set()

            for item in items:
                title_elem = item.select_one("h2 a, h3 a, a[href*='/job/']")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")
                if not href or not title:
                    continue
                apply_url = urllib.parse.urljoin(self.base_url, href)
                listing_id = _make_scraped_id(apply_url)
                if listing_id in seen_ids:
                    continue
                seen_ids.add(listing_id)

                company = "Unknown Company"
                logo_img = item.select_one("li.job-logo img, img[alt]")
                if logo_img and logo_img.get("alt"):
                    raw_alt = logo_img["alt"].strip()
                    company = re.sub(r"\s+logo$", "", raw_alt, flags=re.IGNORECASE).strip()
                if not company or company == "Unknown Company":
                    co_link = item.select_one("a[href*='/jobs-at/']")
                    if co_link:
                        company = co_link.get_text(strip=True)
                if not company or company == "Unknown Company":
                    match = re.search(r"\s+(?:at|@)\s+([^|·-]+)$", title, re.IGNORECASE)
                    if match:
                        company = match.group(1).strip()

                loc_elem = item.select_one("li.job-details span[id*='location'], span.location, li[id*='location']")
                loc = loc_elem.get_text(strip=True) if loc_elem else params.location
                metadata = _extract_card_metadata(item)
                listings.append(
                    JobListing(
                        id=listing_id,
                        provider=self.site_name,
                        data_source="scrape",
                        title=title,
                        company=company,
                        company_slug=None,
                        location=loc,
                        is_remote=metadata["is_remote"],
                        employment_type=metadata["employment_type"],
                        work_model=metadata["work_model"],
                        department=metadata["department"],
                        salary=metadata.get("salary"),
                        posted_at=metadata["posted_at"],
                        scraped_at=now,
                        apply_url=apply_url,
                        source_url=apply_url,
                        query_used=params.job_title,
                        ats_source=self.site_name,
                    )
                )
        except BotBlockError as e:
            logger.warning(f"[{self.site_name}] Bot block detected: {e}")
        except Exception as e:
            logger.warning(f"[{self.site_name}] Scraper error: {e}")

        return listings


class NgCareersScraper(BaseScraper):
    site_name: str = "ngcareers"
    base_url: str = "https://ngcareers.com"

    async def fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        headers = self.get_headers()
        timeout = httpx.Timeout(settings.scraper_request_timeout_seconds)
        try:
            response = await client.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if response.status_code == 429:
                raise RateLimitError(self.site_name)
            if "jobberman.com" in str(response.url) or (response.url.host and "ngcareers" not in response.url.host):
                logger.info(f"[{self.site_name}] Site permanently redirected to {response.url.host}; domain is retired.")
                return ""
            response.raise_for_status()
            html = response.text
            _check_bot_block(html, self.site_name)
            return html
        except Exception as e:
            logger.warning(f"[{self.site_name}] Fetch error: {e}")
            return ""

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        query_param = urllib.parse.quote_plus(params.job_title)
        url = f"{self.base_url}/jobs/search?keywords={query_param}"

        try:
            html = await self.fetch_html(client, url)
            if not html:
                return listings
            soup = BeautifulSoup(html, "lxml")
            items = soup.select(".job-item, article, div.job-box, div[class*='job-listing']")
            now = datetime.now(timezone.utc)

            for item in items:
                title_elem = item.select_one("a[href*='/job/'], h2 a, h3 a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")
                if not href or not title:
                    continue
                apply_url = urllib.parse.urljoin(self.base_url, href)

                company_elem = item.select_one(".company, .employer, span[class*='company']")
                company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"

                loc_elem = item.select_one(".location, span[class*='location']")
                loc = loc_elem.get_text(strip=True) if loc_elem else params.location
                metadata = _extract_card_metadata(item)

                listing_id = _make_scraped_id(apply_url)
                listings.append(
                    JobListing(
                        id=listing_id,
                        provider=self.site_name,
                        data_source="scrape",
                        title=title,
                        company=company,
                        company_slug=None,
                        location=loc,
                        is_remote=metadata["is_remote"],
                        employment_type=metadata["employment_type"],
                        work_model=metadata["work_model"],
                        department=metadata["department"],
                        salary=metadata.get("salary"),
                        posted_at=metadata["posted_at"],
                        scraped_at=now,
                        apply_url=apply_url,
                        source_url=apply_url,
                        query_used=params.job_title,
                        ats_source=self.site_name,
                    )
                )
        except BotBlockError as e:
            logger.warning(f"[{self.site_name}] Bot block detected: {e}")
        except Exception as e:
            logger.warning(f"[{self.site_name}] Scraper error: {e}")

        return listings


_HNJ_QUERY_STOPWORDS = frozenset({
    "a", "an", "and", "at", "by", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with", "job", "jobs", "role", "roles"
})

_HNJ_TECH_KEYWORDS = frozenset({
    "software", "developer", "engineer", "engineering", "frontend", "front-end", "backend", "back-end",
    "fullstack", "full-stack", "data", "scientist", "analyst", "analytics", "devops", "sre", "cloud",
    "security", "cybersecurity", "cyber", "network", "system", "systems", "it", "ict", "qa", "test",
    "testing", "mobile", "android", "ios", "web", "ui", "ux", "product", "designer", "design", "ai",
    "ml", "machine", "python", "java", "javascript", "typescript", "react", "node", "dotnet", ".net",
    "c#", "php", "golang", "rust", "sql", "database", "administrator", "support", "helpdesk", "switching",
    "technical", "technology", "automation", "architect", "scrum", "agile",
})


def _normalize_hnj_url(base_url: str, href: str) -> str:
    """Fix doubled scheme typos (e.g. https://https://...) and resolve relative URLs."""
    cleaned = re.sub(r"^https?://https?://", "https://", (href or "").strip(), flags=re.IGNORECASE)
    return urllib.parse.urljoin(base_url, cleaned)


def _slugify_hnj_token(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:48] or "role"


def _is_hnj_promotional_ad(raw_title: str, body_text: str) -> bool:
    """Detect non-job training/bootcamp promotional posts on HotNigerianJobs."""
    t_low = (raw_title or "").lower().strip()
    b_low = (body_text or "").lower().strip()
    if re.match(r"^apply\s+before\b", t_low) and " at " not in t_low and "recruitment" not in t_low:
        return True
    if not b_low:
        return False
    has_job_signal = (
        " at " in t_low
        or "recruitment" in t_low
        or "recruiting" in b_low
        or "invites applications" in b_low
        or "invites suitable" in b_low
        or "job title:" in b_low
        or "position is located" in b_low
        or "fill the position" in b_low
    )
    return not has_job_signal


def _split_hnj_roundup_roles(roles_str: str) -> list[str]:
    """Split a HotNigerianJobs roundup role list into individual position titles."""
    cleaned = re.sub(r"\s*Apply Now\.?\s*$", "", roles_str or "", flags=re.IGNORECASE).strip(" .:")
    if not cleaned:
        return []
    if ";" in cleaned:
        raw_parts = [re.sub(r"^and\s+", "", p.strip(), flags=re.IGNORECASE) for p in cleaned.split(";")]
        return [p.strip(" .") for p in raw_parts if p.strip(" .")]
    comma_parts = [p.strip() for p in cleaned.split(",") if p.strip()]
    if not comma_parts:
        return []
    if len(comma_parts) == 1:
        sub = re.split(r"\s+and\s+(?![^(]*\))", comma_parts[0], flags=re.IGNORECASE)
        return [s.strip(" .") for s in sub if s.strip(" .")]
    result: list[str] = []
    for part in comma_parts[:-1]:
        cleaned_part = part.strip(" .")
        if cleaned_part:
            result.append(cleaned_part)
    last = comma_parts[-1].strip()
    if re.match(r"^and\s+", last, flags=re.IGNORECASE):
        last_clean = re.sub(r"^and\s+", "", last, flags=re.IGNORECASE).strip(" .")
        if last_clean:
            result.append(last_clean)
    else:
        sub = re.split(r"\s+and\s+(?![^(]*\))", last, flags=re.IGNORECASE)
        result.extend(s.strip(" .") for s in sub if s.strip(" ."))
    return result


def _extract_hnj_company_and_title(raw_title: str, body_text: str) -> tuple[str, str, str | None]:
    """Extract (clean_title, company, workplace_hint) from HotNigerianJobs heading and body."""
    title_clean = re.sub(r"[\ufffd]+", " ", (raw_title or "").strip())
    title_clean = re.sub(r"\s+", " ", title_clean).strip()
    body_clean = re.sub(r"[\ufffd]+", " ", (body_text or "").strip())
    body_clean = re.sub(r"\s+", " ", body_clean).strip()
    workplace_hint: str | None = None

    # 1. Single-role pattern: "<Role> at <Company> [- Hybrid | - 4 Openings]"
    if re.search(r"\s+at\s+", title_clean, flags=re.IGNORECASE):
        parts = re.split(r"\s+at\s+", title_clean, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            role_part = parts[0].strip()
            comp_part = parts[1].strip()
            for candidate_str in (comp_part, role_part):
                hint_match = re.search(
                    r"\s*[-–—]\s*(remote|hybrid|on-?site|in-?person)\b",
                    candidate_str,
                    flags=re.IGNORECASE,
                )
                if hint_match and not workplace_hint:
                    workplace_hint = hint_match.group(1)
            comp_part = re.sub(
                r"\s*[-–—]\s*(?:remote|hybrid|on-?site|in-?person|full-?time|part-?time|contract|\d+\s+(?:openings?|positions?))\b.*$",
                "",
                comp_part,
                flags=re.IGNORECASE,
            ).strip(" -–—.")
            if comp_part:
                return role_part, comp_part, workplace_hint

    # 2. Roundup heading pattern: "<Company> [Graduate & Exp.] [Remote] Job Recruitment [(N Positions)]"
    if re.search(r"\bjob\s+recruitment\b", title_clean, flags=re.IGNORECASE):
        if re.search(r"\bremote\s+job\s+recruitment\b", title_clean, flags=re.IGNORECASE):
            workplace_hint = "remote"
        comp = re.sub(
            r"\s+(?:graduate\s*(?:&|and)\s*exp(?:erienced)?\.?\s+)?(?:massive\b.*?\b)?(?:nationwide\s+)?(?:remote\s+)?job\s+recruitment.*$",
            "",
            title_clean,
            flags=re.IGNORECASE,
        ).strip(" -–—.")
        if comp:
            return title_clean, comp, workplace_hint

    # 3. Body prose pattern: "<Company> is [currently] recruiting..." or "<Company> invites..."
    body_comp_match = re.match(
        r"^(?P<comp>[A-Z0-9][^.:;]{1,90}?)\s+(?:is\s+(?:currently\s+)?recruiting|invites\s+(?:applications|suitable\s+candidates))\b",
        body_clean,
    )
    if body_comp_match:
        comp = body_comp_match.group("comp").strip()
        comp = re.sub(r"\s*[-–—]\s*our\s+client$", "", comp, flags=re.IGNORECASE).strip()
        comp = re.sub(r"^the\s+", "", comp, flags=re.IGNORECASE).strip() if comp.lower().startswith("the ") else comp
        if comp and comp.lower() not in ("we", "our client", "a reputable company"):
            return title_clean, comp, workplace_hint

    return title_clean, "Unknown", workplace_hint


def _extract_hnj_location(body_text: str, labeled_location: str | None) -> str | None:
    """Extract explicit location from HotNigerianJobs text, or None if not stated (ADR 0001)."""
    if labeled_location:
        cleaned = re.sub(r"[\ufffd]+", "", labeled_location).strip(" .,-")
        if cleaned:
            return cleaned

    body_clean = re.sub(r"[\ufffd]+", " ", (body_text or "").strip())
    body_clean = re.sub(r"\s+", " ", body_clean)

    # Roundup location: "to fill the following [Graduate & Experienced] positions in <Location>:"
    roundup_loc = re.search(
        r"to\s+fill\s+the\s+following\s+(?:remote\s+)?(?:[\w&/\-]+\s+){0,4}?positions?\s+in\s+(?P<loc>[^:]+?):",
        body_clean,
        flags=re.IGNORECASE,
    )
    if roundup_loc:
        loc = roundup_loc.group("loc").strip(" .,")
        if loc:
            return loc

    # Single-job location: "The position is located in <Location>." or "This is a Remote Job in <Location>."
    single_loc = re.search(
        r"\b(?:(?:the\s+)?position\s+is\s+located|position\s+located|we\s+are\s+located|this\s+is\s+a\s+(?:remote|hybrid|on-?site)\s+(?:job|position|role)(?:\s+located)?)\s+in\s+(?P<loc>[^.:;]+?)(?:\.|;|$)",
        body_clean,
        flags=re.IGNORECASE,
    )
    if single_loc:
        loc = single_loc.group("loc").strip(" .,")
        if loc:
            return loc

    return None


class HotNigerianJobsScraper(BaseScraper):
    site_name: str = "hotnigerianJobs"
    base_url: str = "https://www.hotnigerianjobs.com"

    async def fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        headers = self.get_headers()
        timeout = httpx.Timeout(settings.scraper_request_timeout_seconds)
        try:
            response = await client.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if response.status_code == 429:
                raise RateLimitError(self.site_name)
            response.raise_for_status()
            html = response.text
            _check_bot_block(html, self.site_name)
            return html
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning(f"[{self.site_name}] Upstream/Network error for {url}: {exc}")
            return ""

    @staticmethod
    def _query_tokens(job_title: str) -> list[str]:
        raw_tokens = re.findall(r"[a-z0-9+#.]+", (job_title or "").lower())
        return [t for t in raw_tokens if len(t) >= 2 and t not in _HNJ_QUERY_STOPWORDS]

    @classmethod
    def _matches_query(cls, tokens: list[str], title: str, extra_text: str = "") -> bool:
        if not tokens:
            return True
        haystack = f"{title} {extra_text}".lower()
        return any(
            re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", haystack)
            for tok in tokens
        )

    def _build_listing(
        self,
        *,
        listing_id: str,
        title: str,
        company: str,
        location: str | None,
        title_work_model_suffix: str | None,
        body_text: str,
        metadata: dict,
        apply_url: str,
        source_url: str,
        query_used: str,
        scraped_at: datetime,
    ) -> JobListing:
        clean_role = re.sub(r"[\ufffd]+", " ", title).strip()
        clean_role = re.sub(r"\s+", " ", clean_role)

        # Preserve any title suffix (e.g. "- Hybrid" from "Graphics Designer at Cavista - Hybrid")
        # at Tier 5 (title), while keeping workplace_type strictly for structured labels (Tier 1)
        # and body_text at Tier 6 (description) per ADR 0002.
        title_for_wm = (
            f"{clean_role} - {title_work_model_suffix}"
            if title_work_model_suffix and title_work_model_suffix.lower() not in clean_role.lower()
            else clean_role
        )
        wm_res = resolve_work_model(
            workplace_type=metadata.get("work_model"),
            location=location,
            title=title_for_wm,
            description=body_text or None,
            description_ok=bool(body_text),
            trusted_description=body_text or None,
        )
        work_model = wm_res.value
        is_remote = (
            True
            if work_model == "remote"
            else (False if work_model in ("in_person", "hybrid") else metadata.get("is_remote"))
        )
        emp_type = metadata.get("employment_type") or normalize_job_type_from_text(body_text, title=clean_role)
        company_slug = _slugify_hnj_token(company) if company and company != "Unknown" else None

        return JobListing(
            id=listing_id,
            provider=self.site_name,
            data_source="scrape",
            title=clean_role,
            company=company or "Unknown",
            company_slug=company_slug,
            location=location,
            is_remote=is_remote,
            employment_type=emp_type,
            work_model=work_model,
            work_model_source=wm_res.source,
            work_model_evidence=wm_res.evidence,
            department=metadata.get("department"),
            salary=metadata.get("salary"),
            posted_at=metadata.get("posted_at"),
            scraped_at=scraped_at,
            apply_url=apply_url,
            source_url=source_url,
            query_used=query_used,
            ats_source=self.site_name,
        )

    def parse_html(
        self,
        html: str,
        params: SearchParams,
        *,
        seen_ids: set[str] | None = None,
    ) -> list[JobListing]:
        if not html:
            return []
        if seen_ids is None:
            seen_ids = set()

        soup = BeautifulSoup(html, "lxml")
        # Select only top-level .mycase containers (never div[class*='job'] which matches child .jobheader)
        raw_items = soup.select(".mycase") or soup.select("article, .post")
        now = datetime.now(timezone.utc)
        tokens = self._query_tokens(params.job_title)

        # Filter to actual job cards with a heading
        job_cards = []
        for item in raw_items:
            heading = item.select_one("h1, h2, h3")
            if heading and heading.get_text(strip=True):
                job_cards.append(item)

        is_multi_card_feed = len(job_cards) > 1
        listings: list[JobListing] = []

        for item in job_cards:
            heading = item.select_one("h1, h2, h3")
            if not heading:
                continue
            link_elem = (
                heading.select_one("a[href]")
                or item.select_one("h1 a, h2 a, h3 a, a[rel='bookmark'], a[href*='hotnigerianjobs.com/hotjobs/']")
            )
            raw_title = (link_elem or heading).get_text(" ", strip=True)
            href = link_elem.get("href", "") if link_elem else ""
            if not raw_title or not href:
                continue

            card_url = _normalize_hnj_url(self.base_url, href)
            body_node = item.select_one(".mycase4")
            body_text = body_node.get_text(" ", strip=True) if body_node else item.get_text(" ", strip=True)

            if _is_hnj_promotional_ad(raw_title, body_text):
                continue

            # Extract card metadata without letting shared roundup descriptions set card-wide work_model
            metadata = _extract_card_metadata(item)
            metadata["work_model"] = extract_labeled_fields(body_text).get("work_model")
            clean_title, company, title_wm_suffix = _extract_hnj_company_and_title(raw_title, body_text)
            card_location = _extract_hnj_location(body_text, metadata.get("location"))

            # Case 1: Detail page roundup with numbered sub-positions ("1.) Role Title")
            numbered_roles: list[dict[str, str | None]] = []
            if body_node:
                current_role: dict[str, str | None] | None = None
                for p_tag in body_node.select("p"):
                    p_text = re.sub(r"[\ufffd]+", " ", p_tag.get_text(" ", strip=True)).strip()
                    num_match = re.match(r"^\d+\s*[.)]+\s*(.+)$", p_text)
                    if num_match:
                        if current_role and current_role.get("title"):
                            numbered_roles.append(current_role)
                        current_role = {
                            "title": num_match.group(1).strip(" .)-"),
                            "location": None,
                            "href": None,
                        }
                        continue
                    if current_role is not None:
                        loc_match = re.match(r"^Location\s*:\s*(.+)$", p_text, flags=re.IGNORECASE)
                        if loc_match and not current_role.get("location"):
                            current_role["location"] = loc_match.group(1).strip(" .,")
                        a_tag = p_tag.select_one("a[href]")
                        if a_tag and a_tag.get("href") and not current_role.get("href"):
                            current_role["href"] = a_tag.get("href")
                if current_role and current_role.get("title"):
                    numbered_roles.append(current_role)

            if numbered_roles:
                card_candidates: list[JobListing] = []
                for role_info in numbered_roles:
                    r_title = role_info["title"] or ""
                    r_href = role_info.get("href")
                    r_url = _normalize_hnj_url(self.base_url, r_href) if r_href else f"{card_url}#{_slugify_hnj_token(r_title)}"
                    r_id = _make_scraped_id(r_url)
                    if r_id in seen_ids:
                        continue
                    r_loc = role_info.get("location") or card_location
                    card_candidates.append(
                        self._build_listing(
                            listing_id=r_id,
                            title=r_title,
                            company=company,
                            location=r_loc,
                            title_work_model_suffix=title_wm_suffix,
                            body_text="",
                            metadata=metadata,
                            apply_url=r_url,
                            source_url=card_url,
                            query_used=params.job_title,
                            scraped_at=now,
                        )
                    )
                matched = [c for c in card_candidates if self._matches_query(tokens, c.title)]
                chosen = matched if (is_multi_card_feed or matched) else card_candidates
                for c in chosen:
                    if c.id not in seen_ids:
                        seen_ids.add(c.id)
                        listings.append(c)
                continue

            # Case 2: Homepage roundup summary card ("to fill the following [remote] positions [in <Loc>]: Role 1, Role 2...")
            roundup_match = re.search(
                r"(?:to\s+fill\s+the\s+following\s+(?P<remote>remote\s+)?(?:[\w&/\-]+\s+){0,4}?positions?(?:\s+in\s+(?P<loc>[^:]+?)|\s+for\s+[^:]+?)?|apply\s+for\s+the\s+following\s+programmes?)\s*:\s*(?P<roles>.+?)(?:\.\s*Apply Now|\s+Apply Now|$)",
                re.sub(r"[\ufffd]+", " ", body_text),
                flags=re.IGNORECASE,
            )
            if roundup_match:
                roles_list = _split_hnj_roundup_roles(roundup_match.group("roles"))
                if roles_list:
                    r_suffix = "Remote" if roundup_match.groupdict().get("remote") else title_wm_suffix
                    r_loc = (roundup_match.groupdict().get("loc") or "").strip(" .,") or card_location
                    card_candidates = []
                    for r_title in roles_list:
                        role_url = f"{card_url}#{_slugify_hnj_token(r_title)}" if len(roles_list) > 1 else card_url
                        r_id = _make_scraped_id(role_url)
                        if r_id in seen_ids:
                            continue
                        card_candidates.append(
                            self._build_listing(
                                listing_id=r_id,
                                title=r_title,
                                company=company,
                                location=r_loc,
                                title_work_model_suffix=r_suffix,
                                body_text="",
                                metadata=metadata,
                                apply_url=role_url,
                                source_url=card_url,
                                query_used=params.job_title,
                                scraped_at=now,
                            )
                        )
                    matched = [c for c in card_candidates if self._matches_query(tokens, c.title)]
                    chosen = matched if (is_multi_card_feed or matched) else card_candidates
                    for c in chosen:
                        if c.id not in seen_ids:
                            seen_ids.add(c.id)
                            listings.append(c)
                    continue

            # Case 3: Single-position card or single-position detail page
            if is_multi_card_feed and not self._matches_query(tokens, clean_title, body_text):
                continue

            listing_id = _make_scraped_id(card_url)
            if listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)
            listings.append(
                self._build_listing(
                    listing_id=listing_id,
                    title=clean_title,
                    company=company,
                    location=card_location,
                    title_work_model_suffix=title_wm_suffix,
                    body_text=body_text,
                    metadata=metadata,
                    apply_url=card_url,
                    source_url=card_url,
                    query_used=params.job_title,
                    scraped_at=now,
                )
            )

        return listings

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings: list[JobListing] = []
        seen_ids: set[str] = set()
        query_param = urllib.parse.quote_plus(params.job_title)
        primary_url = f"{self.base_url}/?s={query_param}"

        try:
            html = await self.fetch_html(client, primary_url)
            if not html:
                return listings
            listings.extend(self.parse_html(html, params, seen_ids=seen_ids))

            # HotNigerianJobs ignores /?s= and returns the homepage roundup feed.
            # When live homepage is detected, also fetch the unbundled ICT/Software field page (/field/273/)
            # and/or Remote field page (/field/269/) when relevant.
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            page_title = (title_match.group(1) if title_match else "").lower()
            if "search for jobs & find your dream job" in page_title:
                tokens = self._query_tokens(params.job_title)
                extra_urls: list[str] = []
                if not tokens or any(t in _HNJ_TECH_KEYWORDS for t in tokens):
                    extra_urls.append(f"{self.base_url}/field/273/")
                if params.remote is True:
                    extra_urls.append(f"{self.base_url}/field/269/")
                for extra_url in extra_urls:
                    extra_html = await self.fetch_html(client, extra_url)
                    if extra_html:
                        listings.extend(self.parse_html(extra_html, params, seen_ids=seen_ids))
        except BotBlockError as e:
            logger.warning(f"[{self.site_name}] Bot block detected for {primary_url}: {e}")
        except Exception as e:
            logger.warning(f"[{self.site_name}] Scraper error for {primary_url}: {e}")

        return listings


NIGERIAN_SCRAPERS: list[BaseScraper] = [
    JobbermanScraper(),
    MyJobMagScraper(),
    NgCareersScraper(),
    HotNigerianJobsScraper(),
]
