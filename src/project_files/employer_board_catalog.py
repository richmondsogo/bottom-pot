"""
Curated Catalog of Verified Direct Employer Boards (Step 54).

Strictly bounded to Bottom Pot's existing 9 ``MONITORABLE_PROVIDERS`` and
explicitly seeded only via explicit helpers or CLI ``--seed-catalog`` — never
auto-seeded inside ``_ensure_db()``.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from src.project_files.ats_url_parser import is_valid_board_slug
from src.project_files.company_board_registry import (
    MONITORABLE_PROVIDERS,
    CompanyBoard,
    CompanyBoardRegistry,
    build_canonical_board_url,
)


@dataclass(frozen=True)
class CuratedEmployerBoard:
    """Verified direct employer board approved for independent monitoring."""

    company_name: str
    ats_provider: str
    board_token: str
    board_url: str
    discovery_source: str
    notes: str
    polling_priority: int = 1


VERIFIED_EMPLOYER_BOARDS: tuple[CuratedEmployerBoard, ...] = (
    CuratedEmployerBoard(
        company_name="Supabase",
        ats_provider="ashby",
        board_token="supabase",
        board_url="https://jobs.ashbyhq.com/supabase",
        discovery_source="opentoafrica_direct_ats_lead",
        notes="Global remote-first developer platform with explicit Worldwide and AMER/EMEA/APAC/country-scoped roles; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Qdrant",
        ats_provider="ashby",
        board_token="qdrant.tech",
        board_url="https://jobs.ashbyhq.com/qdrant.tech",
        discovery_source="opentoafrica_detail_lead",
        notes="Vector search & AI infrastructure company discovered via OpenToAfrica; fresh US and EMEA/EU remote technical roles; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="M-KOPA",
        ats_provider="ashby",
        board_token="m-kopa",
        board_url="https://jobs.ashbyhq.com/m-kopa",
        discovery_source="opentoafrica_detail_lead",
        notes="Clean-tech and fintech engineering across East/West Africa & UK/EU hubs (UTC-1 to UTC+3) discovered via OpenToAfrica.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Thndr",
        ats_provider="ashby",
        board_token="thndr",
        board_url="https://jobs.ashbyhq.com/thndr",
        discovery_source="opentoafrica_detail_lead",
        notes="Egypt/MENA & EU fintech engineering discovered via OpenToAfrica; demonstrates Egypt vs Nigeria eligibility separation.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="FairMoney",
        ats_provider="workable",
        board_token="fairmoney",
        board_url="https://apply.workable.com/fairmoney",
        discovery_source="opentoafrica_direct_ats_lead",
        notes="Nigerian/African fintech engineering; uses Workable widget + v2 detail hydration with canonical shortcode deduplication.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Paystack",
        ats_provider="teamtailor",
        board_token="paystack",
        board_url="https://paystack.teamtailor.com",
        discovery_source="africa_global_fintech_seed",
        notes="Pan-African payments infrastructure engineering across Lagos, Nairobi, Cape Town, and Accra hubs; RSS feed with ETag/304.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Wikimedia Foundation",
        ats_provider="greenhouse",
        board_token="wikimedia",
        board_url="https://boards.greenhouse.io/wikimedia",
        discovery_source="global_remote_first_seed",
        notes="Remote-first open infrastructure employer publishing explicit 18-country + US hiring scope (incl. GH, KE, ZA, MA, DE, GB, IN, SG).",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Grafana Labs",
        ats_provider="greenhouse",
        board_token="grafanalabs",
        board_url="https://boards.greenhouse.io/grafanalabs",
        discovery_source="global_remote_first_seed",
        notes="Remote-first observability platform with fresh country-scoped remote engineering roles across Americas and Europe; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Spotify",
        ats_provider="lever",
        board_token="spotify",
        board_url="https://jobs.lever.co/spotify",
        discovery_source="eu_global_tech_seed",
        notes="European and North American Lever technology benchmark across UK, Sweden, US, and Canada with 100% descriptions; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Miaplaza",
        ats_provider="recruitee",
        board_token="miaplaza",
        board_url="https://miaplaza.recruitee.com",
        discovery_source="us_eu_benchmark_seed",
        notes="Fresh Recruitee EdTech infrastructure board blending US and EMEA remote engineering roles.",
        polling_priority=1,
    ),
)


def seed_verified_employer_boards(
    registry: CompanyBoardRegistry,
    catalog: tuple[CuratedEmployerBoard, ...] = VERIFIED_EMPLOYER_BOARDS,
) -> list[CompanyBoard]:
    """
    Idempotently register all verified direct employer boards into ``registry``.

    Validates every entry against ``MONITORABLE_PROVIDERS`` and canonical slug
    rules without touching operational schema initialization.
    """
    registered: list[CompanyBoard] = []
    for entry in catalog:
        provider = entry.ats_provider.strip().lower()
        token = entry.board_token.strip().lower()
        if provider not in MONITORABLE_PROVIDERS:
            logger.warning(f"[catalog] Skipping unsupported provider {provider}:{token}")
            continue
        if not is_valid_board_slug(provider, token):
            logger.warning(f"[catalog] Skipping invalid slug {provider}:{token}")
            continue
        canonical_url = build_canonical_board_url(provider, token) or entry.board_url
        board = registry.register_candidate(
            company_name=entry.company_name,
            ats_provider=provider,
            board_token=token,
            board_url=canonical_url,
            discovery_source=entry.discovery_source,
        )
        if board is not None:
            registered.append(board)
    return registered
