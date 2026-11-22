"""
Curated Catalog of Verified Direct Employer Boards (Steps 54–56).

Strictly bounded to Bottom Pot's existing 9 ``MONITORABLE_PROVIDERS`` and
explicitly seeded only via explicit helpers or CLI ``--seed-catalog`` — never
auto-seeded inside ``_ensure_db()``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from loguru import logger

from src.ats.ats_url_parser import is_valid_board_slug
from src.storage.company_board_registry import (
    MONITORABLE_PROVIDERS,
    CompanyBoard,
    CompanyBoardRegistry,
    build_canonical_board_url,
)

CATALOG_ACTIVATION_COMMAND = "python -m src.monitoring.board_monitor --seed-catalog --allow-operational-db"


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


@dataclass(frozen=True)
class CatalogActivationPreview:
    """Read-only status distinction between catalogued and operationally registered boards."""

    company_name: str
    ats_provider: str
    board_token: str
    board_url: str
    catalogued: bool = True
    permission_verified: bool = True
    technically_verified: bool = True
    operationally_registered: bool = False
    activation_command: str = CATALOG_ACTIVATION_COMMAND


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
    CuratedEmployerBoard(
        company_name="Metabase",
        ats_provider="lever",
        board_token="metabase",
        board_url="https://jobs.lever.co/metabase",
        discovery_source="opentoafrica_direct_ats_lead",
        notes="Global remote-first BI/analytics engineering employer discovered via OpenToAfrica with explicit Global Remote roles; ETag/304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Railway",
        ats_provider="ashby",
        board_token="railway",
        board_url="https://jobs.ashbyhq.com/railway",
        discovery_source="opentoafrica_direct_ats_lead",
        notes="Distributed cloud platform discovered via OpenToAfrica with explicit Global remote infrastructure and product engineering roles; ETag/304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Whippy",
        ats_provider="ashby",
        board_token="whippy",
        board_url="https://jobs.ashbyhq.com/whippy",
        discovery_source="opentoafrica_direct_ats_lead",
        notes="Ultra-fresh AI platform discovered via OpenToAfrica hiring Dublin Intern and New Graduate Forward Deployed Engineers plus worldwide remote roles.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="DuckDuckGo",
        ats_provider="ashby",
        board_token="duck-duck-go",
        board_url="https://jobs.ashbyhq.com/duck-duck-go",
        discovery_source="opentoafrica_direct_ats_lead",
        notes="Remote-first privacy engineering employer publishing explicit 25-30 country hiring lists (incl. ZA, IN, SG, GB, CA, US; excludes unlisted NG).",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Kraken",
        ats_provider="ashby",
        board_token="kraken.com",
        board_url="https://jobs.ashbyhq.com/kraken.com",
        discovery_source="global_remote_first_seed",
        notes="Fresh distributed engineering board listing structured multi-country remote eligibility across ZA, GB, CA, EU, LATAM, and UAE via secondaryLocations.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Kuda",
        ats_provider="workable",
        board_token="kuda",
        board_url="https://apply.workable.com/kuda",
        discovery_source="africa_fintech_seed",
        notes="African digital banking fintech diversifying Nigerian (Lagos, Abuja) and South African technical roles via Workable widget + v2 details.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Electrum",
        ats_provider="workable",
        board_token="electrum",
        board_url="https://apply.workable.com/electrum",
        discovery_source="africa_early_career_seed",
        notes="Cape Town payments-software employer hiring 2027 Software Developer Graduate Programme and Summer Internship roles (ZA local, NG excluded).",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Affirm",
        ats_provider="greenhouse",
        board_token="affirm",
        board_url="https://boards.greenhouse.io/affirm",
        discovery_source="global_early_career_seed",
        notes="Fresh financial-tech engineering board featuring Early Career Software Engineer I (Remote Canada/US, London) and Summer 2027 IT Intern roles; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Lyft",
        ats_provider="greenhouse",
        board_token="lyft",
        board_url="https://boards.greenhouse.io/lyft",
        discovery_source="global_early_career_seed",
        notes="Active Summer 2027 SWE, Data Engineering, and PhD ML internship pipeline across Canada (Toronto) and US (SF/NYC); ETag/304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Almedia",
        ats_provider="ashby",
        board_token="almedia",
        board_url="https://jobs.ashbyhq.com/almedia",
        discovery_source="eu_early_career_seed",
        notes="Berlin-based tech employer with fresh explicit Junior Software Engineer, Junior Data Scientist, and Junior TypeScript/Python/DevOps/AI openings; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="ElevenLabs",
        ats_provider="ashby",
        board_token="elevenlabs",
        board_url="https://jobs.ashbyhq.com/elevenlabs",
        discovery_source="global_remote_first_seed",
        notes="Fresh global remote-first AI audio & research engineering board with explicit global-execution roles alongside scoped US/EU/LATAM/APAC postings; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Circle",
        ats_provider="ashby",
        board_token="circle",
        board_url="https://jobs.ashbyhq.com/circle",
        discovery_source="opentoafrica_detail_lead",
        notes="Fully remote creator platform discovered via OpenToAfrica offering fresh Anywhere worldwide engineering alongside AMER/EMEA entry-level IT Coordinator; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Cohere",
        ats_provider="ashby",
        board_token="cohere",
        board_url="https://jobs.ashbyhq.com/cohere",
        discovery_source="global_early_career_seed",
        notes="Enterprise AI employer offering remote multi-country Machine Learning Intern/Co-op alongside UK/EU/CA/US research and ML systems roles; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Keyrock",
        ats_provider="ashby",
        board_token="keyrock",
        board_url="https://jobs.ashbyhq.com/keyrock",
        discovery_source="opentoafrica_detail_lead",
        notes="Digital-assets market-making firm discovered via OpenToAfrica hiring ultra-fresh London & Brussels Quant/DeFi internships and Cape Town/EU data roles; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Coinbase",
        ats_provider="greenhouse",
        board_token="coinbase",
        board_url="https://boards.greenhouse.io/coinbase",
        discovery_source="global_early_career_seed",
        notes="Multi-region remote and APAC/NA SWE/ML/Analytics internship board covering Singapore Hybrid SWE Intern alongside Remote USA/India/Canada/UK roles; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Sentry",
        ats_provider="ashby",
        board_token="sentry",
        board_url="https://jobs.ashbyhq.com/sentry",
        discovery_source="eu_early_career_seed",
        notes="Developer monitoring platform hiring Summer 2027 Software Engineer Intern and New Grad in Vienna alongside North American and European engineering roles; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Property Finder",
        ats_provider="teamtailor",
        board_token="propertyfinder",
        board_url="https://propertyfinder.teamtailor.com",
        discovery_source="africa_mena_early_career_seed",
        notes="MENA/Egypt technology employer expanding Cairo Fullstack/Data/IT roles and UAE Engineering Graduate Trainee pipeline via Teamtailor RSS; 304 supported.",
        polling_priority=1,
    ),
    CuratedEmployerBoard(
        company_name="Foodics",
        ats_provider="workable",
        board_token="foodics",
        board_url="https://apply.workable.com/foodics",
        discovery_source="africa_mena_early_career_seed",
        notes="MENA/Egypt cloud platform adding Cairo remote FDE and Amman remote Junior AI Forward Engineer via Workable widget + v2 details.",
        polling_priority=1,
    ),
)


def preview_catalog_activation(
    catalog: tuple[CuratedEmployerBoard, ...] = VERIFIED_EMPLOYER_BOARDS,
) -> list[dict[str, object]]:
    """
    Return a strictly read-only activation status preview for every catalogued board.

    Does NOT open or touch any SQLite file; distinguishes catalog verification
    from operator-authorized production DB registration.
    """
    preview: list[dict[str, object]] = []
    for entry in catalog:
        provider = entry.ats_provider.strip().lower()
        token = entry.board_token.strip().lower()
        canonical_url = build_canonical_board_url(provider, token) or entry.board_url
        item = CatalogActivationPreview(
            company_name=entry.company_name,
            ats_provider=provider,
            board_token=token,
            board_url=canonical_url,
            catalogued=True,
            permission_verified=provider in MONITORABLE_PROVIDERS,
            technically_verified=is_valid_board_slug(provider, token),
            operationally_registered=False,
        )
        preview.append(asdict(item))
    return preview


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
