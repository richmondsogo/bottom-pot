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
from src.project_files.ats_url_parser import is_valid_board_slug, parse_ats_url
from src.project_files.canonical_job_adapter import CanonicalJobAdapter
from src.project_files.company_board_registry import company_board_registry
from src.project_files.exceptions import BotBlockError, RateLimitError
from src.project_files.http_resilience import HostRateLimitedError, resilience_manager
from src.project_files.field_normalizer import (
    extract_labeled_fields,
    normalize_fields,
    normalize_job_type_from_text,
    parse_datetime,
    resolve_work_model,
    to_markdown,
)
from src.project_files.job_extraction_service import JobExtractionService, RawJobPosting
from src.project_files.models import JobListing, SearchParams
from src.project_files.extraction_outcome import (
    ExtractionOutcome,
    ExtractionResult,
    map_status_or_exception_to_outcome,
    sanitize_error_text,
)

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


def _find_contextual_apply_link(soup: BeautifulSoup, site_domain: str) -> str | None:
    """
    Find authentic external apply links from dedicated application buttons,
    application sections, or explicit call-to-action elements.
    Ignores headers, footers, navigation, social sharing, and recommended job widgets.
    """
    candidates = soup.select(
        "a[data-cy*='apply'], a.apply-btn, a.apply-button, a[class*='apply'], "
        "[class*='apply'] a[href], [id*='apply'] a[href], .job__details a[href], "
        ".job-details a[href], .job-key-info a[href], a.mag-apply-btn, a.btn-apply, "
        ".apply-container a[href], .apply-section a[href]"
    )

    ignored_hosts = ("facebook.com", "twitter.com", "linkedin.com", "whatsapp.com", "t.me", "instagram.com", "youtube.com")

    for a in candidates:
        href = a.get("href", "").strip()
        if not href.startswith("http") or site_domain.lower() in href.lower():
            continue
        if any(h in href.lower() for h in ignored_hosts):
            continue
        text = a.get_text(" ", strip=True).lower()
        cls_str = " ".join(a.get("class") or []).lower()
        if (
            "apply" in text
            or "apply" in cls_str
            or "apply" in a.get("id", "").lower()
            or a.get("data-cy")
            or "application" in text
        ):
            return href

    main_container = soup.select_one("article, main, .job-details, .job__details, #job-details, .job-info-details")
    if main_container:
        for a in main_container.select("a[href]"):
            href = a.get("href", "").strip()
            if not href.startswith("http") or site_domain.lower() in href.lower():
                continue
            if any(h in href.lower() for h in ignored_hosts):
                continue
            text = a.get_text(" ", strip=True).lower()
            if re.search(r"\b(?:apply|apply now|application link|apply on)\b", text):
                return href

    return None


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

    # Extract explicit labeled salary if present (never scan unlabelled card snippets)
    sal_match = re.search(r"\bSalary\s*:\s*([^\n\r<.]+)", text, re.IGNORECASE)
    salary_str = sal_match.group(1).strip() if sal_match else None

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
        if json_ld.get("employmentType") and not labeled.get("employment_type"):
            labeled["employment_type"] = json_ld["employmentType"]
        if json_ld.get("jobLocationType") and not labeled.get("work_model"):
            labeled["work_model"] = json_ld["jobLocationType"]
        if json_ld.get("datePosted") and not date_value:
            date_value = json_ld["datePosted"]
        if json_ld.get("department") and not labeled.get("department"):
            labeled["department"] = json_ld["department"] if isinstance(json_ld["department"], str) else json_ld["department"].get("name")

    work_model_cand = labeled.get("work_model")
    if not work_model_cand:
        for elem in card.select("span, div, p"):
            b = elem.get_text(strip=True)
            if 0 < len(b) < 60 and re.search(r"\b(?:remote|hybrid|on-?site|work from home|wfh)\b", b, re.IGNORECASE):
                work_model_cand = b
                break

    return {
        "location": labeled.get("location"),
        "employment_type": labeled.get("employment_type"),
        "work_model": work_model_cand,
        "department": labeled.get("department"),
        "posted_at": parse_datetime(date_value),
        "salary": salary_str,
        "json_ld": json_ld,
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
        host = resilience_manager.extract_host(url)
        try:
            async with resilience_manager.throttle(url):
                response = await client.get(url, headers=headers, timeout=timeout, follow_redirects=True)
                if response.status_code == 429:
                    retry_after = response.headers.get("retry-after")
                    resilience_manager.record_rate_limit(host, retry_after)
                    raise RateLimitError(self.site_name)
                elif response.status_code < 500:
                    resilience_manager.record_success(host)
                elif response.status_code >= 500:
                    resilience_manager.record_failure(host)
                response.raise_for_status()
                html = response.text
                _check_bot_block(html, self.site_name)
                return html
        except HostRateLimitedError:
            raise RateLimitError(self.site_name)

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings, _ = await self.search_result(client, params)
        return listings

    async def search_result(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> tuple[list[JobListing], ExtractionResult]:
        raise NotImplementedError


class JobbermanScraper(BaseScraper):
    site_name: str = "jobberman"
    base_url: str = "https://www.jobberman.com"

    @staticmethod
    def _extract_card_summary(card: BeautifulSoup, title: str, company: str) -> str | None:
        summary_elem = card.select_one(
            "p.md\\:pl-5, p[class*='md:pl-5'], p.job-summary, div.job-summary"
        )
        if summary_elem:
            text = summary_elem.get_text(" ", strip=True)
            if len(text) >= 25:
                return to_markdown(text) or text

        for p_tag in card.select("p"):
            txt = p_tag.get_text(" ", strip=True)
            if (
                len(txt) >= 35
                and txt != title
                and txt != company
                and not re.match(r"^\d+\s+(?:hour|day|week|month)s?\s+ago$", txt, flags=re.IGNORECASE)
            ):
                return to_markdown(txt) or txt
        return None

    @staticmethod
    def extract_detail_markdown(html: str) -> str | None:
        """Extract clean Markdown description from a Jobberman listing detail page (`article.job__details`)."""
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")
        article = soup.select_one("article.job__details, div.job__details")
        if not article:
            return None

        sections: list[str] = []
        for h3 in article.find_all(["h2", "h3", "h4"]):
            heading_text = h3.get_text(" ", strip=True)
            h_low = heading_text.lower()
            if any(
                skip in h_low
                for skip in ("share link", "important safety tips", "report job", "similar jobs")
            ):
                continue

            if "job summary" in h_low or "job description" in h_low or "requirements" in h_low:
                sibling_parts: list[str] = []
                for sib in h3.find_next_siblings():
                    if sib.name in ("h2", "h3", "h4"):
                        break
                    sib_md = to_markdown(str(sib))
                    if sib_md:
                        sibling_parts.append(sib_md)
                if sibling_parts:
                    title_clean = "Job Summary" if "summary" in h_low else "Job Description & Requirements"
                    sections.append(f"### {title_clean}\n\n" + "\n\n".join(sibling_parts))

        if sections:
            return "\n\n".join(sections).strip()

        prose = article.select_one("div.prose")
        if prose:
            return to_markdown(str(prose))
        return None

    async def _enrich_detail(
        self,
        client: httpx.AsyncClient,
        listing: JobListing,
        raw: RawJobPosting,
        sem: asyncio.Semaphore,
    ) -> None:
        if not listing.apply_url:
            return
        async with sem:
            try:
                detail_html = await self.fetch_html(client, listing.apply_url)
                if detail_html:
                    soup = BeautifulSoup(detail_html, "lxml")
                    apply_link = _find_contextual_apply_link(soup, "jobberman.com")
                    if apply_link:
                        parsed = parse_ats_url(apply_link)
                        if parsed and parsed.company_slug and is_valid_board_slug(parsed.ats, parsed.company_slug):
                            listing.apply_url = apply_link
                            company_board_registry.register_candidate(
                                ats_provider=parsed.ats,
                                board_token=parsed.company_slug,
                                company_name=listing.company if listing.company != "Unknown Company" else None,
                                source_url=apply_link,
                            )
                        elif apply_link.startswith("http"):
                            listing.apply_url = apply_link

                detail_md = self.extract_detail_markdown(detail_html)
                if detail_md:
                    raw.raw_description = detail_md
                    raw.description_is_authentic = True
                    canonical = JobExtractionService.extract(raw)
                    enriched = CanonicalJobAdapter.to_listing(canonical)
                    listing.description = enriched.description
                    listing.description_ok = enriched.description_ok
                    listing.work_model = enriched.work_model
                    listing.work_model_source = enriched.work_model_source
                    listing.work_model_evidence = enriched.work_model_evidence
                    listing.is_remote = enriched.is_remote
                    if enriched.salary:
                        listing.salary = enriched.salary
                    if enriched.employment_type:
                        listing.employment_type = enriched.employment_type
            except Exception as e:
                logger.debug(f"[{self.site_name}] Detail enrichment skipped for {listing.apply_url}: {e}")

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings, _ = await self.search_result(client, params)
        return listings

    async def search_result(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> tuple[list[JobListing], ExtractionResult]:
        listings: list[JobListing] = []
        raw_postings: list[RawJobPosting] = []
        query_param = urllib.parse.quote_plus(params.job_title)
        url = f"{self.base_url}/jobs?q={query_param}"
        if params.location:
            url += f"&l={urllib.parse.quote_plus(params.location)}"

        html = ""
        try:
            html = await self.fetch_html(client, url)
        except RateLimitError as exc:
            logger.warning(f"[{self.site_name}] HTTP 429 encountered: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP 429 rate limit exceeded: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.RATE_LIMITED,
                status_code=429,
                error_summary=safe_err,
                attempts=1,
            )
        except BotBlockError as exc:
            logger.warning(f"[{self.site_name}] Bot block detected: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Bot block detected: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PERMANENT_ERROR,
                error_summary=safe_err,
                attempts=1,
            )
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(status_code=exc.response.status_code)
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP error {exc.response.status_code}: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=1,
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[{self.site_name}] Scraping error: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                error_summary=safe_err,
                attempts=1,
            )

        if not html:
            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )

        try:
            soup = BeautifulSoup(html, "lxml")
            cards = soup.select("div[data-cy='listing-cards-components']") or soup.select(
                "article, div.mx-5, div.flex-grow"
            )
            now = datetime.now(timezone.utc)
            seen_ids: set[str] = set()

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
                listing_id = _make_scraped_id(apply_url)
                if listing_id in seen_ids:
                    continue
                seen_ids.add(listing_id)

                company_elem = card.select_one(
                    "a[href*='/employer/'], a[href*='/employers/'], p.text-blue-700, p[class*='text-blue'], span[class*='company']"
                )
                company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
                if company in ("Engineering & Technology", "Software & Data", "IT & Telecoms"):
                    alt_elem = card.select_one("a[href*='/employer/'], a[href*='/employers/'], p.text-blue-700")
                    if alt_elem and alt_elem != company_elem:
                        company = alt_elem.get_text(strip=True)

                loc_elem = card.select_one(
                    "span[class*='location'], span[class*='badge'], span.bg-brand-secondary-100, span.text-gray-500"
                )
                loc = loc_elem.get_text(strip=True) if loc_elem else params.location
                card_summary = self._extract_card_summary(card, title, company)

                # Extract raw candidate fields from card badges/spans
                badges = [s.get_text(" ", strip=True) for s in card.select("span")]
                raw_salary: str | None = None
                raw_work_model: str | None = None
                raw_emp: str | None = None

                for b in badges:
                    if not raw_salary and re.search(r"(?:NGN|₦|[$£€]|N\s*\d)", b, re.IGNORECASE):
                        raw_salary = b
                    elif not raw_work_model and re.search(r"\b(?:remote|hybrid|on-?site|work from home|wfh)\b", b, re.IGNORECASE):
                        raw_work_model = b
                    elif not raw_emp and re.search(r"\b(?:full[- ]time|part[- ]time|contract|internship|temporary)\b", b, re.IGNORECASE):
                        raw_emp = b

                card_text = card.get_text(" ", strip=True)
                labeled = extract_labeled_fields(card_text)
                if not raw_salary:
                    sal_m = re.search(r"\bSalary\s*:\s*([^\n\r<.]+)", card_text, re.IGNORECASE)
                    if sal_m:
                        raw_salary = sal_m.group(1).strip()

                date_node = card.select_one("time[datetime], time, [data-posted], [data-date-posted]")
                date_val: str | None = None
                if date_node:
                    date_val = date_node.get("datetime") or date_node.get("data-posted") or date_node.get_text(" ", strip=True)

                json_ld = None
                for script in card.select('script[type="application/ld+json"]'):
                    try:
                        p_data = json.loads(script.string or script.get_text())
                        vals = p_data if isinstance(p_data, list) else [p_data]
                        json_ld = next((it for it in vals if isinstance(it, dict) and it.get("@type") == "JobPosting"), None)
                        if json_ld:
                            break
                    except Exception:
                        pass

                raw = RawJobPosting(
                    provider=self.site_name,
                    source_url=apply_url,
                    apply_url=apply_url,
                    provider_job_id=listing_id,
                    raw_title=title,
                    raw_company=company,
                    raw_location=loc,
                    raw_workplace_type=raw_work_model or labeled.get("work_model"),
                    raw_employment_type=raw_emp or labeled.get("employment_type"),
                    raw_department=labeled.get("department"),
                    raw_date=date_val,
                    raw_fields={
                        "bare_n_is_ngn": True,
                        "salary": raw_salary,
                        "json_ld": json_ld,
                    },
                    raw_description=card_summary,
                    description_is_authentic=False,
                    query_used=params.job_title,
                    scraped_at=now,
                )
                canonical = JobExtractionService.extract(raw)
                listing = CanonicalJobAdapter.to_listing(canonical)
                listing.id = listing_id
                listing.provider = self.site_name
                listing.data_source = "scrape"
                listings.append(listing)
                raw_postings.append(raw)

            if listings:
                sem = asyncio.Semaphore(5)
                enrich_targets = list(zip(listings, raw_postings))[: min(len(listings), params.max_results, 10)]
                await asyncio.gather(*(self._enrich_detail(client, item[0], item[1], sem) for item in enrich_targets))
            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )
        except Exception as e:
            logger.warning(f"[{self.site_name}] Parsing error: {e}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Parsing error: {e}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PARSE_ERROR,
                status_code=200,
                error_summary=safe_err,
                attempts=1,
            )


class MyJobMagScraper(BaseScraper):
    site_name: str = "myjobmag"
    base_url: str = "https://www.myjobmag.com"

    async def _enrich_detail(
        self,
        client: httpx.AsyncClient,
        listing: JobListing,
        raw: RawJobPosting,
        sem: asyncio.Semaphore,
    ) -> None:
        if not listing.apply_url:
            return
        async with sem:
            try:
                detail_html = await self.fetch_html(client, listing.apply_url)
                if not detail_html:
                    return
                soup = BeautifulSoup(detail_html, "lxml")

                # Scan for authentic contextual external apply links / ATS links
                apply_link = _find_contextual_apply_link(soup, "myjobmag.com")
                if apply_link:
                    parsed = parse_ats_url(apply_link)
                    if parsed and parsed.company_slug and is_valid_board_slug(parsed.ats, parsed.company_slug):
                        listing.apply_url = apply_link
                        company_board_registry.register_candidate(
                            ats_provider=parsed.ats,
                            board_token=parsed.company_slug,
                            company_name=listing.company if listing.company != "Unknown Company" else None,
                            source_url=apply_link,
                        )
                    elif apply_link.startswith("http"):
                        listing.apply_url = apply_link

                desc_container = soup.select_one(
                    "div.job-details, div.read-more-content, div.item-desc, .job-description, div.job-info-details"
                )
                if desc_container:
                    desc_md = to_markdown(str(desc_container))
                    if desc_md and len(desc_md) > len(listing.description or ""):
                        raw.raw_description = desc_md
                        raw.description_is_authentic = True
                        canonical = JobExtractionService.extract(raw)
                        enriched = CanonicalJobAdapter.to_listing(canonical)
                        listing.description = enriched.description
                        listing.description_ok = enriched.description_ok
                        if enriched.work_model:
                            listing.work_model = enriched.work_model
                            listing.work_model_source = enriched.work_model_source
                            listing.work_model_evidence = enriched.work_model_evidence
                            listing.is_remote = enriched.is_remote
                        if enriched.salary:
                            listing.salary = enriched.salary
                        if enriched.employment_type:
                            listing.employment_type = enriched.employment_type
            except Exception as e:
                logger.debug(f"[{self.site_name}] Detail enrichment skipped for {listing.apply_url}: {e}")

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings, _ = await self.search_result(client, params)
        return listings

    async def search_result(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> tuple[list[JobListing], ExtractionResult]:
        listings: list[JobListing] = []
        query_param = urllib.parse.quote_plus(params.job_title)
        url = f"{self.base_url}/search/jobs?q={query_param}"
        if params.location:
            url += f"&location={urllib.parse.quote_plus(params.location)}"

        html = ""
        try:
            html = await self.fetch_html(client, url)
        except RateLimitError as exc:
            logger.warning(f"[{self.site_name}] HTTP 429 encountered: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP 429 rate limit exceeded: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.RATE_LIMITED,
                status_code=429,
                error_summary=safe_err,
                attempts=1,
            )
        except BotBlockError as exc:
            logger.warning(f"[{self.site_name}] Bot block detected: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Bot block detected: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PERMANENT_ERROR,
                error_summary=safe_err,
                attempts=1,
            )
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(status_code=exc.response.status_code)
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP error {exc.response.status_code}: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=1,
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[{self.site_name}] Scraping error: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                error_summary=safe_err,
                attempts=1,
            )

        if not html:
            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )

        try:
            soup = BeautifulSoup(html, "lxml")
            items = soup.select("li.job-list-li")
            if not items:
                items = soup.select("li.job-info, li.job-item")
            now = datetime.now(timezone.utc)
            seen_ids: set[str] = set()
            raw_postings: list[RawJobPosting] = []

            for item in items:
                title_elem = item.select_one("h2 a, h3 a, a[href*='/job/']")
                if not title_elem:
                    continue

                raw_title_text = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")
                if not href or not raw_title_text:
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

                # Clean title: strip verified " at <Company>" suffix without truncating valid titles (e.g. "Live at Home Carer")
                if company and company != "Unknown Company":
                    pattern = rf"\s+(?:at|@)\s+{re.escape(company)}\s*$"
                    if re.search(pattern, raw_title_text, re.IGNORECASE):
                        cleaned_title = re.sub(pattern, "", raw_title_text, flags=re.IGNORECASE).strip()
                        title = cleaned_title if cleaned_title else raw_title_text
                    else:
                        title = raw_title_text
                else:
                    match = re.search(r"^(.*?)\s+(?:at|@)\s+([A-Z][A-Za-z0-9&.,' -]{1,50})$", raw_title_text)
                    non_company_words = {"home", "sea", "large", "work", "site", "risk", "scale", "peace", "rest"}
                    if match and match.group(2).strip().lower() not in non_company_words:
                        company = match.group(2).strip()
                        title = match.group(1).strip()
                    else:
                        title = raw_title_text

                loc_elem = item.select_one("li.job-details span[id*='location'], span.location, li[id*='location']")
                loc = loc_elem.get_text(strip=True) if loc_elem else params.location
                desc_elem = item.select_one("li.job-desc, div.job-desc, p.job-desc")
                desc_md = to_markdown(str(desc_elem)) if desc_elem else None

                # Extract raw candidate fields from item
                badges = [s.get_text(" ", strip=True) for s in item.select("li.job-details span, span")]
                raw_salary: str | None = None
                raw_work_model: str | None = None
                raw_emp: str | None = None

                for b in badges:
                    if not raw_salary and re.search(r"(?:NGN|₦|[$£€]|N\s*\d)", b, re.IGNORECASE):
                        raw_salary = b
                    elif not raw_work_model and re.search(r"\b(?:remote|hybrid|on-?site|work from home|wfh)\b", b, re.IGNORECASE):
                        raw_work_model = b
                    elif not raw_emp and re.search(r"\b(?:full[- ]time|part[- ]time|contract|internship|temporary)\b", b, re.IGNORECASE):
                        raw_emp = b

                if not raw_salary:
                    sal_m = re.search(r"\bSalary\s*:\s*([^\n\r<.]+)", item.get_text(" ", strip=True), re.IGNORECASE)
                    if sal_m:
                        raw_salary = sal_m.group(1).strip()

                date_node = item.select_one("time[datetime], time, [data-posted], [data-date-posted], li#job-date, [id*='date']")
                date_val: str | None = None
                if date_node:
                    date_val = date_node.get("datetime") or date_node.get("data-posted") or date_node.get_text(" ", strip=True)
                if not date_val:
                    date_match = re.search(r"(?:posted|published)\s*(?:on)?\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", item.get_text(" ", strip=True), re.IGNORECASE)
                    date_val = date_match.group(1) if date_match else None

                # Handle partial dates like '13 October'
                if date_val and re.match(r"^\d{1,2}\s+[a-zA-Z]+$", date_val.strip()):
                    current_year = datetime.now(timezone.utc).year
                    date_val = f"{date_val.strip()} {current_year}"

                json_ld = None
                for script in item.select('script[type="application/ld+json"]'):
                    try:
                        p_data = json.loads(script.string or script.get_text())
                        vals = p_data if isinstance(p_data, list) else [p_data]
                        json_ld = next((it for it in vals if isinstance(it, dict) and it.get("@type") == "JobPosting"), None)
                        if json_ld:
                            break
                    except Exception:
                        pass

                raw = RawJobPosting(
                    provider=self.site_name,
                    source_url=apply_url,
                    apply_url=apply_url,
                    provider_job_id=listing_id,
                    raw_title=title,
                    raw_company=company,
                    raw_location=loc,
                    raw_workplace_type=raw_work_model,
                    raw_employment_type=raw_emp,
                    raw_date=date_val,
                    raw_fields={
                        "bare_n_is_ngn": True,
                        "salary": raw_salary,
                        "json_ld": json_ld,
                    },
                    raw_description=desc_md,
                    description_is_authentic=False,
                    query_used=params.job_title,
                    scraped_at=now,
                )
                canonical = JobExtractionService.extract(raw)
                listing = CanonicalJobAdapter.to_listing(canonical)
                listing.id = listing_id
                listing.provider = self.site_name
                listing.data_source = "scrape"
                listings.append(listing)
                raw_postings.append(raw)

            if listings:
                sem = asyncio.Semaphore(3)
                enrich_targets = list(zip(listings, raw_postings))[: min(len(listings), params.max_results, 10)]
                await asyncio.gather(*(self._enrich_detail(client, item[0], item[1], sem) for item in enrich_targets))

            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )
        except Exception as e:
            logger.warning(f"[{self.site_name}] Parsing error: {e}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Parsing error: {e}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PARSE_ERROR,
                status_code=200,
                error_summary=safe_err,
                attempts=1,
            )


class NgCareersScraper(BaseScraper):
    site_name: str = "ngcareers"
    base_url: str = "https://ngcareers.com"

    async def fetch_html(self, client: httpx.AsyncClient, url: str) -> str:
        headers = self.get_headers()
        timeout = httpx.Timeout(settings.scraper_request_timeout_seconds)
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

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings, _ = await self.search_result(client, params)
        return listings

    async def search_result(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> tuple[list[JobListing], ExtractionResult]:
        listings: list[JobListing] = []
        query_param = urllib.parse.quote_plus(params.job_title)
        url = f"{self.base_url}/jobs/search?keywords={query_param}"

        html = ""
        try:
            html = await self.fetch_html(client, url)
        except RateLimitError as exc:
            logger.warning(f"[{self.site_name}] HTTP 429 encountered: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP 429 rate limit exceeded: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.RATE_LIMITED,
                status_code=429,
                error_summary=safe_err,
                attempts=1,
            )
        except BotBlockError as exc:
            logger.warning(f"[{self.site_name}] Bot block detected: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Bot block detected: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PERMANENT_ERROR,
                error_summary=safe_err,
                attempts=1,
            )
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(status_code=exc.response.status_code)
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP error {exc.response.status_code}: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=1,
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[{self.site_name}] Scraping error: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                error_summary=safe_err,
                attempts=1,
            )

        if not html:
            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )

        try:
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
                listing_id = _make_scraped_id(apply_url)

                company_elem = item.select_one(".company, .employer, span[class*='company']")
                company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"

                loc_elem = item.select_one(".location, span[class*='location']")
                loc = loc_elem.get_text(strip=True) if loc_elem else params.location

                # Extract candidate raw fields from item
                raw_salary: str | None = None
                raw_work_model: str | None = None
                raw_emp: str | None = None

                badges = [s.get_text(" ", strip=True) for s in item.select(".salary, .badge, span")]
                for b in badges:
                    if not raw_salary and re.search(r"(?:NGN|₦|[$£€]|N\s*\d)", b, re.IGNORECASE):
                        raw_salary = b
                    elif not raw_work_model and re.search(r"\b(?:remote|hybrid|on-?site|work from home|wfh)\b", b, re.IGNORECASE):
                        raw_work_model = b
                    elif not raw_emp and re.search(r"\b(?:full[- ]time|part[- ]time|contract|internship|temporary)\b", b, re.IGNORECASE):
                        raw_emp = b

                if not raw_salary:
                    sal_m = re.search(r"\bSalary\s*:\s*([^\n\r<.]+)", item.get_text(" ", strip=True), re.IGNORECASE)
                    if sal_m:
                        raw_salary = sal_m.group(1).strip()

                date_node = item.select_one("time[datetime], time, [data-posted], [data-date-posted], span.date, .date")
                date_val: str | None = None
                if date_node:
                    date_val = date_node.get("datetime") or date_node.get("data-posted") or date_node.get_text(" ", strip=True)
                if not date_val:
                    date_match = re.search(r"(?:posted|published)\s*(?:on)?\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})", item.get_text(" ", strip=True), re.IGNORECASE)
                    date_val = date_match.group(1) if date_match else None

                desc_elem = item.select_one(".job-desc, .description, p")
                desc_md = to_markdown(str(desc_elem)) if desc_elem else None

                json_ld = None
                for script in item.select('script[type="application/ld+json"]'):
                    try:
                        p_data = json.loads(script.string or script.get_text())
                        vals = p_data if isinstance(p_data, list) else [p_data]
                        json_ld = next((it for it in vals if isinstance(it, dict) and it.get("@type") == "JobPosting"), None)
                        if json_ld:
                            break
                    except Exception:
                        pass

                raw = RawJobPosting(
                    provider=self.site_name,
                    source_url=apply_url,
                    apply_url=apply_url,
                    provider_job_id=listing_id,
                    raw_title=title,
                    raw_company=company,
                    raw_location=loc,
                    raw_workplace_type=raw_work_model,
                    raw_employment_type=raw_emp,
                    raw_date=date_val,
                    raw_fields={
                        "bare_n_is_ngn": True,
                        "salary": raw_salary,
                        "json_ld": json_ld,
                    },
                    raw_description=desc_md,
                    description_is_authentic=False,
                    query_used=params.job_title,
                    scraped_at=now,
                )
                canonical = JobExtractionService.extract(raw)
                listing = CanonicalJobAdapter.to_listing(canonical)
                listing.id = listing_id
                listing.provider = self.site_name
                listing.data_source = "scrape"
                listings.append(listing)
            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )
        except Exception as e:
            logger.warning(f"[{self.site_name}] Parsing error: {e}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Parsing error: {e}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PARSE_ERROR,
                status_code=200,
                error_summary=safe_err,
                attempts=1,
            )


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


_DISALLOWED_APPLY_DOMAINS = (
    "hotnigerianjobs.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "whatsapp.com",
    "t.me",
    "doubleclick.net",
    "googlesyndication.com",
    "googleadservices.com",
)

_AGGREGATOR_TRACKING_PARAMS = {"src", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def _decode_cf_email(cf_hex: str) -> str:
    """Decode Cloudflare XOR email-protection hex string."""
    try:
        k = int(cf_hex[:2], 16)
        return "".join(chr(int(cf_hex[i : i + 2], 16) ^ k) for i in range(2, len(cf_hex), 2))
    except Exception:
        return ""


def _clean_external_apply_url(url: str) -> str:
    """Strip aggregator tracking params and fix double scheme typos."""
    cleaned = re.sub(r"^https?://https?://", "https://", (url or "").strip(), flags=re.IGNORECASE)
    try:
        parts = urllib.parse.urlsplit(cleaned)
        if not parts.scheme or not parts.netloc:
            return cleaned
        query_pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        filtered_pairs = [
            (k, v)
            for k, v in query_pairs
            if k.lower() not in _AGGREGATOR_TRACKING_PARAMS and not k.lower().startswith("utm_")
        ]
        new_query = urllib.parse.urlencode(filtered_pairs)
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    except Exception:
        return cleaned


def _is_valid_external_apply_url(url: str) -> bool:
    """Check if URL is a valid external job application URL and not in the blocklist."""
    if not url:
        return False
    url_stripped = url.strip()
    if url_stripped.startswith("#") or url_stripped.lower().startswith("javascript:"):
        return False
    try:
        parts = urllib.parse.urlsplit(url_stripped)
    except Exception:
        return False
    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False
    host = (parts.hostname or "").lower()
    if not host:
        return False
    path = (parts.path or "").lower()
    if "/cdn-cgi/" in path or "/cdn-cgi/" in url_stripped.lower():
        return False
    for domain in _DISALLOWED_APPLY_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return False
    if (host == "linkedin.com" or host.endswith(".linkedin.com")) and "/share" in path:
        return False
    return True


def _extract_hnj_subject(text: str, default_title: str = "") -> str:
    """Extract explicit quoted subject line from application instructions or fall back to role_title."""
    cleaned = re.sub(r"[\ufffd]+", '"', text or "")
    cleaned = re.sub(r"[“”]", '"', cleaned)
    cleaned = re.sub(r"[‘’]", "'", cleaned)

    m1 = re.search(
        r'(?:using|with|subject\s+(?:of\s+(?:the\s+)?(?:e-?mail)\s+)?(?:should\s+be|is)|as\s+(?:the\s+)?subject)\s*[:\-]?\s*["\']([^"\r\n]{2,100})["\']',
        cleaned,
        re.IGNORECASE,
    )
    if m1:
        return m1.group(1).strip()

    m2 = re.search(
        r'["\']([^"\r\n]{2,100})["\']\s*(?:as\s+(?:the\s+)?(?:e-?mail\s+)?subject|as\s+subject\s+of\s+(?:the\s+)?(?:e-?mail))',
        cleaned,
        re.IGNORECASE,
    )
    if m2:
        return m2.group(1).strip()

    return default_title.strip()


def _extract_hnj_application_method(container: BeautifulSoup, role_title: str = "") -> str | None:
    """
    Extract direct apply URL or decoded mailto URI from a HotNigerianJobs card or container.
    Returns clean external URL, mailto URI with subject, or None.
    """
    if container is None:
        return None

    # Priority A: Check links with explicit apply-intent anchor text
    for a in container.find_all("a", href=True):
        href = a["href"].strip()
        link_text = a.get_text(" ", strip=True).lower()
        if _is_valid_external_apply_url(href):
            if any(kw in link_text for kw in ("click here to apply", "apply online", "apply here", "application link", "apply now")):
                return _clean_external_apply_url(href)

    # Priority B: Search inside application sections ("How to Apply" / "Method of Application")
    app_sections = []
    for elem in container.find_all(["p", "div", "h2", "h3", "h4", "strong"]):
        txt = elem.get_text(" ", strip=True).lower()
        if "how to apply" in txt or "method of application" in txt:
            parent = elem.parent if elem.name == "strong" else elem
            if parent not in app_sections:
                app_sections.append(parent)

    for sec in app_sections:
        for a in sec.find_all("a", href=True):
            href = a["href"].strip()
            if _is_valid_external_apply_url(href):
                return _clean_external_apply_url(href)

    # Priority C: Any valid external link in the container
    for a in container.find_all("a", href=True):
        href = a["href"].strip()
        if _is_valid_external_apply_url(href):
            return _clean_external_apply_url(href)

    # Priority D: Search for emails (Cloudflare-protected or plain text)
    search_nodes = app_sections if app_sections else [container]
    email: str | None = None
    section_text: str = ""

    for node in search_nodes:
        # Check Cloudflare span
        for span in node.select("span.__cf_email__"):
            cf_hex = span.get("data-cfemail", "")
            decoded = _decode_cf_email(cf_hex)
            if "@" in decoded and "." in decoded:
                email = decoded
                break
        if email:
            section_text = node.get_text(" ", strip=True)
            break

        # Check Cloudflare href
        for a in node.select("a[href*='email-protection#']"):
            href = a.get("href", "")
            m = re.search(r"email-protection#([0-9a-fA-F]+)", href)
            if m:
                decoded = _decode_cf_email(m.group(1))
                if "@" in decoded and "." in decoded:
                    email = decoded
                    break
        if email:
            section_text = node.get_text(" ", strip=True)
            break

        # Check plain-text email in node text
        node_text = node.get_text(" ", strip=True)
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", node_text)
        if email_match:
            email = email_match.group(0)
            section_text = node_text
            break

    # If not found in app_sections, search full container
    if not email and app_sections:
        for span in container.select("span.__cf_email__"):
            decoded = _decode_cf_email(span.get("data-cfemail", ""))
            if "@" in decoded and "." in decoded:
                email = decoded
                break
        if not email:
            for a in container.select("a[href*='email-protection#']"):
                m = re.search(r"email-protection#([0-9a-fA-F]+)", a.get("href", ""))
                if m:
                    decoded = _decode_cf_email(m.group(1))
                    if "@" in decoded and "." in decoded:
                        email = decoded
                        break
        if not email:
            container_text = container.get_text(" ", strip=True)
            email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", container_text)
            if email_match:
                email = email_match.group(0)
        section_text = container.get_text(" ", strip=True)

    if email:
        subject = _extract_hnj_subject(section_text, role_title)
        if subject:
            return f"mailto:{email}?subject={urllib.parse.quote(subject)}"
        return f"mailto:{email}"

    return None


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


def _extract_hnj_body_markdown(body_node: BeautifulSoup | None, fallback_text: str = "") -> str | None:
    """Convert HotNigerianJobs .mycase4 HTML into clean Markdown with AdSense stripped."""
    if body_node is not None:
        frag = BeautifulSoup(str(body_node), "lxml")
        for bad in frag.select("script, style, ins, .adsbygoogle, iframe"):
            bad.decompose()
        md = to_markdown(str(frag))
        if md:
            md = re.sub(r"\n*(?:\[Apply Now\]\([^)]+\)|Click Here and Apply Online|Apply Now\.?)\s*$", "", md, flags=re.IGNORECASE).strip()
            return md or None
    if fallback_text:
        md = to_markdown(fallback_text)
        if md:
            md = re.sub(r"\n*(?:\[Apply Now\]\([^)]+\)|Click Here and Apply Online|Apply Now\.?)\s*$", "", md, flags=re.IGNORECASE).strip()
            return md or None
    return None


_HNJ_ROLE_FEED_RULES: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({"software", "developer", "engineer", "engineering", "programmer"}), "/role/1108/"),
    (frozenset({"fullstack", "full-stack", "react", "vue", "angular", "node", "nodejs", "nextjs"}), "/role/427/"),
    (
        frozenset({
            "frontend", "front-end", "backend", "back-end", "python", "java",
            "golang", "dotnet", ".net", "c#", "rust", "typescript", "javascript",
        }),
        "/role/1121/",
    ),
    (frozenset({"web", "wordpress", "php", "laravel", "html", "css"}), "/role/445/"),
    (frozenset({"mobile", "android", "ios", "flutter", "kotlin", "swift"}), "/role/437/"),
    (frozenset({"data", "analyst", "analytics", "scientist", "bi", "sql", "machine", "ml", "ai"}), "/role/1010/"),
    (frozenset({"ui", "ux", "designer", "design", "figma", "graphic", "graphics", "creative"}), "/role/349/"),
    (
        frozenset({
            "devops", "cloud", "aws", "azure", "gcp", "sre", "sysadmin", "system",
            "systems", "administrator", "network", "security", "cyber", "cybersecurity",
            "it", "support", "helpdesk",
        }),
        "/role/441/",
    ),
    (frozenset({"database", "dba", "postgres", "mysql", "oracle"}), "/role/365/"),
)


class HotNigerianJobsScraper(BaseScraper):
    site_name: str = "hotnigerianJobs"
    base_url: str = "https://www.hotnigerianjobs.com"

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

    def _select_feed_urls(self, params: SearchParams) -> list[str]:
        """Select targeted HotNigerianJobs /role/<id>/ and /field/<id>/ feeds based on query tokens."""
        tokens = set(self._query_tokens(params.job_title))
        urls: list[str] = []

        def _add(path: str) -> None:
            full = f"{self.base_url}{path}"
            if full not in urls:
                urls.append(full)

        for rule_tokens, path in _HNJ_ROLE_FEED_RULES:
            if tokens & rule_tokens:
                _add(path)

        if not tokens or (tokens & _HNJ_TECH_KEYWORDS):
            _add("/field/273/")
        if tokens & {"data", "scientist", "analytics", "research", "ai", "ml"}:
            _add("/field/268/")
        if tokens & {"qa", "test", "testing", "quality"}:
            _add("/field/258/")
        if tokens & {"product", "project", "scrum", "agile", "operations"}:
            _add("/field/257/")
        if params.remote is True or "remote" in tokens:
            _add("/field/269/")

        return urls[:3]

    def _build_listing(
        self,
        *,
        listing_id: str,
        title: str,
        company: str,
        location: str | None,
        title_work_model_suffix: str | None,
        body_text: str,
        description: str | None = None,
        metadata: dict,
        apply_url: str,
        source_url: str,
        query_used: str,
        scraped_at: datetime,
        description_is_authentic: bool = False,
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
        company_clean = company or "Unknown"
        company_slug = _slugify_hnj_token(company_clean) if company_clean and company_clean != "Unknown" else None
        final_desc = description if description is not None else (_extract_hnj_body_markdown(None, body_text) if body_text else None)

        raw_fields = {
            "bare_n_is_ngn": True,
            "title_for_wm": title_for_wm,
        }
        if metadata.get("salary"):
            raw_fields["salary"] = metadata["salary"]
        if metadata.get("department"):
            raw_fields["department"] = metadata["department"]
        if metadata.get("employment_type"):
            raw_fields["employmentType"] = metadata["employment_type"]
        if metadata.get("work_model"):
            raw_fields["jobLocationType"] = metadata["work_model"]
        if metadata.get("json_ld"):
            raw_fields["json_ld"] = metadata["json_ld"]

        raw_date = str(metadata["posted_at"]) if metadata.get("posted_at") else None

        raw = RawJobPosting(
            provider=self.site_name,
            source_url=source_url,
            apply_url=apply_url,
            provider_job_id=listing_id,
            company_slug=company_slug,
            raw_title=clean_role,
            raw_company=company_clean,
            raw_location=location,
            raw_description=final_desc,
            raw_workplace_type=metadata.get("work_model"),
            raw_employment_type=metadata.get("employment_type"),
            raw_salary=metadata.get("salary"),
            raw_date=raw_date,
            raw_fields=raw_fields,
            description_is_authentic=description_is_authentic,
            scraped_at=scraped_at,
        )
        canonical = JobExtractionService.extract(raw)
        listing = CanonicalJobAdapter.to_listing(canonical)
        listing.id = listing_id
        listing.provider = self.site_name
        listing.data_source = "scrape"
        listing.source_url = source_url
        listing.apply_url = apply_url
        listing.query_used = query_used
        listing.ats_source = self.site_name
        listing.scraped_at = scraped_at
        if metadata.get("posted_at") and not listing.posted_at:
            listing.posted_at = metadata.get("posted_at")
        if metadata.get("department"):
            listing.department = metadata.get("department")
        return listing

    def enrich_listing_from_detail(self, listing: JobListing, detail_html: str) -> bool:
        """Enrich a HotNigerianJobs listing with direct apply URL/email and full Markdown description from its detail page."""
        if not detail_html:
            return False
        soup = BeautifulSoup(detail_html, "lxml")
        cards = [c for c in (soup.select(".mycase") or soup.select("article, .post")) if c.select_one("h1, h2, h3")]
        if len(cards) != 1:
            return False

        card = cards[0]
        body_node = card.select_one(".mycase4")
        if not body_node:
            return False

        # Check if the detail page is a multi-position numbered roundup ("1.) Role Title")
        is_roundup = any(re.match(r"^\d+\s*[.)]+\s*(.+)$", p.get_text(" ", strip=True)) for p in body_node.select("p"))

        if is_roundup:
            target_title = (listing.title or "").strip().lower()
            role_app_method: str | None = None
            shared_app_tags = []
            in_shared_app = False
            matching_role_tags = []
            current_role_matches = False

            for p_tag in body_node.select("p"):
                p_text = re.sub(r"[\ufffd]+", " ", p_tag.get_text(" ", strip=True)).strip()
                if re.match(r"^(?:How to Apply|Method of Application)\b", p_text, flags=re.IGNORECASE):
                    in_shared_app = True
                    shared_app_tags.append(p_tag)
                    current_role_matches = False
                    continue
                if in_shared_app:
                    shared_app_tags.append(p_tag)
                    continue
                num_match = re.match(r"^\d+\s*[.)]+\s*(.+)$", p_text)
                if num_match:
                    r_title = num_match.group(1).strip(" .)-").lower()
                    current_role_matches = (
                        r_title == target_title
                        or target_title in r_title
                        or r_title in target_title
                    )
                    if current_role_matches:
                        matching_role_tags.append(p_tag)
                    continue
                if current_role_matches:
                    matching_role_tags.append(p_tag)

            # 1. Look inside the matching sub-role block for external apply link or role-specific email
            if matching_role_tags:
                role_container = BeautifulSoup("".join(str(t) for t in matching_role_tags), "lxml")
                role_app_method = _extract_hnj_application_method(role_container, role_title=listing.title)

            # 2. If not found in sub-role block, fall back to shared application footer
            if not role_app_method and shared_app_tags:
                shared_container = BeautifulSoup("".join(str(t) for t in shared_app_tags), "lxml")
                role_app_method = _extract_hnj_application_method(shared_container, role_title=listing.title)

            if role_app_method:
                listing.apply_url = role_app_method
                if role_app_method.startswith("http"):
                    parsed = parse_ats_url(role_app_method)
                    if parsed and parsed.company_slug and is_valid_board_slug(parsed.ats, parsed.company_slug):
                        company_board_registry.register_candidate(
                            ats_provider=parsed.ats,
                            board_token=parsed.company_slug,
                            company_name=listing.company if listing.company != "Unknown Company" else None,
                            source_url=role_app_method,
                        )

            # Register any other candidate boards scoped strictly to matching sub-role or shared tags
            scoped_tags = list(matching_role_tags) + list(shared_app_tags)
            for tag in scoped_tags:
                for a in tag.select("a[href]"):
                    href = a.get("href", "").strip()
                    if href.startswith("http") and "hotnigerianjobs.com" not in href.lower():
                        p = parse_ats_url(href)
                        if p and p.company_slug and is_valid_board_slug(p.ats, p.company_slug):
                            company_board_registry.register_candidate(
                                ats_provider=p.ats,
                                board_token=p.company_slug,
                                company_name=listing.company if listing.company != "Unknown Company" else None,
                                source_url=href,
                            )

            # Enrich authentic description scoped strictly to this sub-role
            if matching_role_tags:
                role_soup = BeautifulSoup("".join(str(t) for t in matching_role_tags), "lxml")
                sub_desc_md = to_markdown(str(role_soup))
                if sub_desc_md and len(sub_desc_md) > len(listing.description or ""):
                    raw_sub = RawJobPosting(
                        provider=self.site_name,
                        source_url=listing.source_url or listing.apply_url,
                        apply_url=listing.apply_url,
                        raw_title=listing.title,
                        raw_company=listing.company,
                        raw_location=listing.location,
                        raw_description=sub_desc_md,
                        description_is_authentic=True,
                        scraped_at=listing.scraped_at,
                    )
                    canonical = JobExtractionService.extract(raw_sub)
                    enriched = CanonicalJobAdapter.to_listing(canonical)
                    listing.description = enriched.description
                    listing.description_ok = enriched.description_ok
                    if enriched.work_model:
                        listing.work_model = enriched.work_model
                        listing.work_model_source = enriched.work_model_source
                        listing.work_model_evidence = enriched.work_model_evidence
                        listing.is_remote = enriched.is_remote

            return bool(role_app_method or (matching_role_tags and len(listing.description or "") > 100))

        # Single-role detail page: extract application method from card
        apply_method = _extract_hnj_application_method(card, role_title=listing.title)
        if apply_method:
            listing.apply_url = apply_method
            if apply_method.startswith("http"):
                parsed = parse_ats_url(apply_method)
                if parsed and parsed.company_slug and is_valid_board_slug(parsed.ats, parsed.company_slug):
                    company_board_registry.register_candidate(
                        ats_provider=parsed.ats,
                        board_token=parsed.company_slug,
                        company_name=listing.company if listing.company != "Unknown Company" else None,
                        source_url=apply_method,
                    )

        # Scan body for any ATS application links
        for a in body_node.select("a[href]"):
            href = a.get("href", "").strip()
            if href.startswith("http") and "hotnigerianjobs.com" not in href.lower():
                p = parse_ats_url(href)
                if p and p.company_slug and is_valid_board_slug(p.ats, p.company_slug):
                    company_board_registry.register_candidate(
                        ats_provider=p.ats,
                        board_token=p.company_slug,
                        company_name=listing.company if listing.company != "Unknown Company" else None,
                        source_url=href,
                    )

        detail_md = _extract_hnj_body_markdown(body_node)
        if not detail_md:
            return bool(apply_method)

        body_text = body_node.get_text(" ", strip=True)
        detail_meta = _extract_card_metadata(card)
        labeled = extract_labeled_fields(body_text)
        loc = listing.location or _extract_hnj_location(body_text, detail_meta.get("location"))

        raw_fields = {
            "bare_n_is_ngn": True,
        }
        if detail_meta.get("salary"):
            raw_fields["salary"] = detail_meta["salary"]
        if detail_meta.get("department"):
            raw_fields["department"] = detail_meta["department"]
        if detail_meta.get("employment_type"):
            raw_fields["employmentType"] = detail_meta["employment_type"]
        if labeled.get("work_model"):
            raw_fields["jobLocationType"] = labeled["work_model"]
        if detail_meta.get("json_ld"):
            raw_fields["json_ld"] = detail_meta["json_ld"]

        raw = RawJobPosting(
            provider=self.site_name,
            source_url=listing.source_url or listing.apply_url,
            apply_url=listing.apply_url,
            raw_title=listing.title,
            raw_company=listing.company,
            raw_location=loc,
            raw_description=detail_md,
            raw_workplace_type=labeled.get("work_model"),
            raw_employment_type=detail_meta.get("employment_type"),
            raw_salary=detail_meta.get("salary"),
            raw_fields=raw_fields,
            description_is_authentic=True,
            scraped_at=listing.scraped_at,
        )
        canonical = JobExtractionService.extract(raw)
        enriched = CanonicalJobAdapter.to_listing(canonical)
        if not listing.description or len(enriched.description or "") > len(listing.description):
            listing.description = enriched.description
            listing.description_ok = enriched.description_ok
        if enriched.work_model:
            listing.work_model = enriched.work_model
            listing.work_model_source = enriched.work_model_source
            listing.work_model_evidence = enriched.work_model_evidence
            listing.is_remote = enriched.is_remote
        if enriched.salary:
            listing.salary = enriched.salary
        if enriched.location and not listing.location:
            listing.location = enriched.location
        if enriched.employment_type and not listing.employment_type:
            listing.employment_type = enriched.employment_type
        return True

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
            shared_app_tags = []
            in_shared_app = False
            if body_node:
                current_role: dict[str, str | None] | None = None
                for p_tag in body_node.select("p"):
                    p_text = re.sub(r"[\ufffd]+", " ", p_tag.get_text(" ", strip=True)).strip()
                    if re.match(r"^(?:How to Apply|Method of Application)\b", p_text, flags=re.IGNORECASE):
                        if current_role and current_role.get("title"):
                            numbered_roles.append(current_role)
                            current_role = None
                        in_shared_app = True
                        shared_app_tags.append(p_tag)
                        continue
                    if in_shared_app:
                        shared_app_tags.append(p_tag)
                        continue
                    num_match = re.match(r"^\d+\s*[.)]+\s*(.+)$", p_text)
                    if num_match:
                        if current_role and current_role.get("title"):
                            numbered_roles.append(current_role)
                        current_role = {
                            "title": num_match.group(1).strip(" .)-"),
                            "location": None,
                            "salary": None,
                            "href": None,
                            "desc_lines": "",
                        }
                        continue
                    if current_role is not None:
                        loc_match = re.match(r"^Location\s*:\s*(.+)$", p_text, flags=re.IGNORECASE)
                        if loc_match and not current_role.get("location"):
                            current_role["location"] = loc_match.group(1).strip(" .,")
                            continue
                        sal_match = re.match(r"^Salary\s*:\s*(.+)$", p_text, flags=re.IGNORECASE)
                        if sal_match and not current_role.get("salary"):
                            current_role["salary"] = sal_match.group(1).strip(" .,")
                            continue
                        a_tag = p_tag.select_one("a[href]")
                        if a_tag and a_tag.get("href") and not current_role.get("href"):
                            current_role["href"] = a_tag.get("href")
                            continue
                        if not re.match(r"^(?:Deadline|Application Closing Date|Click Here)\b", p_text, flags=re.IGNORECASE):
                            prev_desc = current_role.get("desc_lines") or ""
                            current_role["desc_lines"] = f"{prev_desc}\n\n{p_text}".strip()
                if current_role and current_role.get("title"):
                    numbered_roles.append(current_role)

            if numbered_roles:
                card_candidates: list[JobListing] = []
                shared_container = BeautifulSoup("".join(str(t) for t in shared_app_tags), "lxml") if shared_app_tags else None
                for role_info in numbered_roles:
                    r_title = role_info["title"] or ""
                    r_href = role_info.get("href")
                    # Check 1: role block external apply URL
                    if r_href and _is_valid_external_apply_url(r_href):
                        r_url = _clean_external_apply_url(r_href)
                    else:
                        # Check 2: shared application method at bottom of post
                        shared_apply = _extract_hnj_application_method(shared_container, role_title=r_title) if shared_container else None
                        if shared_apply:
                            r_url = shared_apply
                        elif r_href:
                            r_url = _normalize_hnj_url(self.base_url, r_href)
                        else:
                            r_url = f"{card_url}#{_slugify_hnj_token(r_title)}"
                    r_id = _make_scraped_id(r_url)
                    if r_id in seen_ids:
                        continue
                    r_loc = role_info.get("location") or card_location
                    role_meta = dict(metadata)
                    if role_info.get("salary"):
                        role_meta["salary"] = role_info["salary"]
                    role_desc = to_markdown(role_info.get("desc_lines") or "")
                    card_candidates.append(
                        self._build_listing(
                            listing_id=r_id,
                            title=r_title,
                            company=company,
                            location=r_loc,
                            title_work_model_suffix=title_wm_suffix,
                            body_text=role_info.get("desc_lines") or "",
                            description=role_desc,
                            metadata=role_meta,
                            apply_url=r_url,
                            source_url=card_url,
                            query_used=params.job_title,
                            scraped_at=now,
                            description_is_authentic=True,
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
                        roundup_summary_desc = (
                            f"**{company}** is recruiting for the position of **{r_title}**"
                            + (f" ({r_loc})." if r_loc else ".")
                        )
                        card_candidates.append(
                            self._build_listing(
                                listing_id=r_id,
                                title=r_title,
                                company=company,
                                location=r_loc,
                                title_work_model_suffix=r_suffix,
                                body_text="",
                                description=roundup_summary_desc,
                                metadata=metadata,
                                apply_url=role_url,
                                source_url=card_url,
                                query_used=params.job_title,
                                scraped_at=now,
                                description_is_authentic=False,
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
            body_md = _extract_hnj_body_markdown(body_node, body_text)
            extracted_apply = _extract_hnj_application_method(body_node or item, role_title=clean_title)
            apply_url = extracted_apply if extracted_apply else card_url
            listings.append(
                self._build_listing(
                    listing_id=listing_id,
                    title=clean_title,
                    company=company,
                    location=card_location,
                    title_work_model_suffix=title_wm_suffix,
                    body_text=body_text,
                    description=body_md,
                    metadata=metadata,
                    apply_url=apply_url,
                    source_url=card_url,
                    query_used=params.job_title,
                    scraped_at=now,
                    description_is_authentic=(not is_multi_card_feed and body_node is not None),
                )
            )

        return listings

    async def _resolve_roundup_placeholders(
        self,
        client: httpx.AsyncClient,
        listings: list[JobListing],
        params: SearchParams,
        seen_ids: set[str],
    ) -> list[JobListing]:
        """Upgrade homepage roundup #slug placeholder items by fetching their roundup detail page."""
        roundup_urls: list[str] = []
        for item in listings:
            if "#" in item.apply_url and item.source_url and item.source_url not in roundup_urls:
                roundup_urls.append(item.source_url)

        if not roundup_urls:
            return listings

        target_roundup_urls = roundup_urls[:4]
        roundup_pages = await asyncio.gather(
            *(self.fetch_html(client, r_url) for r_url in target_roundup_urls),
            return_exceptions=True,
        )
        resolved_by_source: dict[str, list[JobListing]] = {}
        for r_url, r_html in zip(target_roundup_urls, roundup_pages):
            if not isinstance(r_html, str) or not r_html:
                continue
            parsed_roles = self.parse_html(r_html, params, seen_ids=set())
            # Only replace if the detail page actually yielded unbundled sub-roles with dedicated links or metadata
            if parsed_roles and any("#" not in pr.apply_url or pr.salary for pr in parsed_roles):
                resolved_by_source[r_url] = parsed_roles

        if not resolved_by_source:
            return listings

        upgraded: list[JobListing] = []
        emitted_sources: set[str] = set()
        for item in listings:
            if "#" in item.apply_url and item.source_url in resolved_by_source:
                if item.source_url not in emitted_sources:
                    emitted_sources.add(item.source_url)
                    for pr in resolved_by_source[item.source_url]:
                        if pr.id not in seen_ids:
                            seen_ids.add(pr.id)
                            upgraded.append(pr)
                continue
            upgraded.append(item)
        return upgraded

    async def _enrich_detail_item(
        self,
        client: httpx.AsyncClient,
        listing: JobListing,
        sem: asyncio.Semaphore,
    ) -> None:
        is_hnj_apply_url = "hotnigerianjobs.com" in (listing.apply_url or "")
        needs_desc = not listing.description or len(listing.description) < 350
        if not is_hnj_apply_url and not needs_desc:
            return

        target_url = listing.apply_url.split("#")[0] if is_hnj_apply_url else (listing.source_url or "")
        if not target_url or "hotnigerianjobs.com" not in target_url:
            return

        async with sem:
            try:
                detail_html = await self.fetch_html(client, target_url)
                if detail_html:
                    self.enrich_listing_from_detail(listing, detail_html)
            except Exception as exc:
                logger.debug(f"[{self.site_name}] Detail enrichment skipped for {target_url}: {exc}")

    async def search(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> list[JobListing]:
        listings, _ = await self.search_result(client, params)
        return listings

    async def search_result(
        self,
        client: httpx.AsyncClient,
        params: SearchParams,
    ) -> tuple[list[JobListing], ExtractionResult]:
        listings: list[JobListing] = []
        seen_ids: set[str] = set()
        query_param = urllib.parse.quote_plus(params.job_title)
        primary_url = f"{self.base_url}/?s={query_param}"

        html = ""
        try:
            html = await self.fetch_html(client, primary_url)
        except RateLimitError as exc:
            logger.warning(f"[{self.site_name}] HTTP 429 encountered: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP 429 rate limit exceeded: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.RATE_LIMITED,
                status_code=429,
                error_summary=safe_err,
                attempts=1,
            )
        except BotBlockError as exc:
            logger.warning(f"[{self.site_name}] Bot block detected for {primary_url}: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Bot block detected: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PERMANENT_ERROR,
                error_summary=safe_err,
                attempts=1,
            )
        except httpx.HTTPStatusError as exc:
            outcome = map_status_or_exception_to_outcome(status_code=exc.response.status_code)
            safe_err = sanitize_error_text(f"[{self.site_name}] HTTP error {exc.response.status_code}: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                status_code=exc.response.status_code,
                error_summary=safe_err,
                attempts=1,
            )
        except Exception as exc:
            outcome = map_status_or_exception_to_outcome(exception=exc)
            safe_err = sanitize_error_text(f"[{self.site_name}] Scraper error for {primary_url}: {exc}")
            return [], ExtractionResult(
                outcome=outcome,
                error_summary=safe_err,
                attempts=1,
            )

        if not html:
            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )

        try:
            listings.extend(self.parse_html(html, params, seen_ids=seen_ids))

            # HotNigerianJobs ignores /?s= and returns the homepage roundup feed.
            # When live homepage is detected, also fetch the targeted /role/<id>/ and /field/<id>/ feeds.
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
            page_title = (title_match.group(1) if title_match else "").lower()
            if "search for jobs & find your dream job" in page_title:
                extra_urls = self._select_feed_urls(params)
                extra_pages = await asyncio.gather(
                    *(self.fetch_html(client, extra_url) for extra_url in extra_urls),
                    return_exceptions=True,
                )
                for extra_html in extra_pages:
                    if isinstance(extra_html, str) and extra_html:
                        listings.extend(self.parse_html(extra_html, params, seen_ids=seen_ids))

            if listings:
                listings = await self._resolve_roundup_placeholders(client, listings, params, seen_ids)
                sem = asyncio.Semaphore(5)
                enrich_targets = listings[: min(len(listings), params.max_results, 10)]
                await asyncio.gather(*(self._enrich_detail_item(client, item, sem) for item in enrich_targets))
            return listings, ExtractionResult(
                outcome=ExtractionOutcome.SUCCESS,
                status_code=200,
                attempts=1,
            )
        except Exception as exc:
            logger.warning(f"[{self.site_name}] Parsing error for {primary_url}: {exc}")
            safe_err = sanitize_error_text(f"[{self.site_name}] Parsing error: {exc}")
            return [], ExtractionResult(
                outcome=ExtractionOutcome.PARSE_ERROR,
                status_code=200,
                error_summary=safe_err,
                attempts=1,
            )


NIGERIAN_SCRAPERS: list[BaseScraper] = [
    JobbermanScraper(),
    MyJobMagScraper(),
    HotNigerianJobsScraper(),
]
