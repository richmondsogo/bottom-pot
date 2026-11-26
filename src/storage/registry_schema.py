"""PostgreSQL DDL and shared batch-upsert helpers for CompanyBoardRegistry."""

from __future__ import annotations

import json
import re
from typing import Any

from src.core.models import JobListing
from src.extraction.field_normalizer import humanize_slug

_MONITORED_JOB_COLS = (
    "job_id, board_id, ats_provider, company_slug, company_name, "
    "title, location, work_model, employment_type, salary, "
    "description, requirements, posted_at, first_discovered_at, "
    "last_checked_at, source_url, apply_url, confidence_score, "
    "source_evidence, status, content_fingerprint, canonical_json, "
    "detail_status, detail_last_hydrated_at, detail_retry_count, "
    "detail_next_retry_at, detail_last_error, widget_location_signature, "
    "listing_item_hash, missing_confirmation_count, missing_first_seen_at"
)

_COMMON_UPSERT_SET = (
    "board_id = COALESCE(excluded.board_id, monitored_jobs.board_id), "
    "ats_provider = excluded.ats_provider, "
    "company_slug = excluded.company_slug, "
    "company_name = excluded.company_name, "
    "title = excluded.title, "
    "location = excluded.location, "
    "work_model = excluded.work_model, "
    "employment_type = excluded.employment_type, "
    "salary = excluded.salary, "
    "description = excluded.description, "
    "requirements = excluded.requirements, "
    "posted_at = COALESCE(excluded.posted_at, monitored_jobs.posted_at), "
    "last_checked_at = excluded.last_checked_at, "
    "source_url = excluded.source_url, "
    "apply_url = excluded.apply_url, "
    "confidence_score = excluded.confidence_score, "
    "source_evidence = excluded.source_evidence, "
    "status = 'active', "
    "content_fingerprint = COALESCE(excluded.content_fingerprint, monitored_jobs.content_fingerprint), "
    "canonical_json = excluded.canonical_json, "
    "missing_confirmation_count = 0, "
    "missing_first_seen_at = NULL"
)

_DETAIL_UPSERT_SET = (
    f"{_COMMON_UPSERT_SET}, "
    "detail_status = excluded.detail_status, "
    "detail_last_hydrated_at = COALESCE(excluded.detail_last_hydrated_at, monitored_jobs.detail_last_hydrated_at), "
    "detail_retry_count = excluded.detail_retry_count, "
    "detail_next_retry_at = excluded.detail_next_retry_at, "
    "detail_last_error = excluded.detail_last_error, "
    "widget_location_signature = COALESCE(excluded.widget_location_signature, monitored_jobs.widget_location_signature), "
    "listing_item_hash = COALESCE(excluded.listing_item_hash, monitored_jobs.listing_item_hash)"
)


def ensure_postgres_registry_schema(conn: Any, monitorable_providers: frozenset[str]) -> None:
    """Create CompanyBoardRegistry tables and GIN full-text index in PostgreSQL."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS company_boards (
            id SERIAL PRIMARY KEY,
            company_name TEXT NOT NULL,
            company_slug TEXT NOT NULL,
            ats_provider TEXT NOT NULL,
            board_token TEXT NOT NULL,
            board_url TEXT NOT NULL,
            discovery_source TEXT NOT NULL,
            source_posting_url TEXT,
            first_discovered_at DOUBLE PRECISION NOT NULL,
            last_discovered_at DOUBLE PRECISION NOT NULL,
            verification_status TEXT NOT NULL DEFAULT 'candidate',
            monitoring_capability TEXT NOT NULL DEFAULT 'unsupported',
            last_successful_check DOUBLE PRECISION,
            next_scheduled_check DOUBLE PRECISION,
            failure_count INTEGER NOT NULL DEFAULT 0,
            polling_priority INTEGER NOT NULL DEFAULT 1,
            etag TEXT,
            last_modified TEXT,
            content_fingerprint TEXT,
            active_job_count INTEGER DEFAULT 0,
            company_logo_url TEXT,
            company_logo_source TEXT,
            company_logo_verified INTEGER NOT NULL DEFAULT 0,
            company_logo_updated_at DOUBLE PRECISION,
            company_logo_checked_at DOUBLE PRECISION,
            UNIQUE(ats_provider, board_token)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_boards_provider_token ON company_boards(ats_provider, board_token)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_boards_monitor ON company_boards(verification_status, monitoring_capability, next_scheduled_check)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_boards_company_slug ON company_boards(company_slug)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS monitored_jobs (
            job_id TEXT PRIMARY KEY,
            board_id INTEGER REFERENCES company_boards(id),
            ats_provider TEXT NOT NULL,
            company_slug TEXT NOT NULL,
            company_name TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            work_model TEXT,
            employment_type TEXT,
            salary TEXT,
            description TEXT,
            requirements TEXT,
            posted_at TEXT,
            first_discovered_at DOUBLE PRECISION NOT NULL,
            last_checked_at DOUBLE PRECISION NOT NULL,
            source_url TEXT NOT NULL,
            apply_url TEXT,
            confidence_score DOUBLE PRECISION,
            source_evidence TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            content_fingerprint TEXT,
            canonical_json TEXT,
            detail_status TEXT NOT NULL DEFAULT 'hydrated',
            detail_last_hydrated_at DOUBLE PRECISION,
            detail_retry_count INTEGER NOT NULL DEFAULT 0,
            detail_next_retry_at DOUBLE PRECISION,
            detail_last_error TEXT,
            widget_location_signature TEXT,
            listing_item_hash TEXT,
            missing_confirmation_count INTEGER NOT NULL DEFAULT 0,
            missing_first_seen_at DOUBLE PRECISION,
            search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector(
                    'simple',
                    coalesce(title, '') || ' ' ||
                    coalesce(company_name, '') || ' ' ||
                    coalesce(location, '') || ' ' ||
                    coalesce(description, '') || ' ' ||
                    coalesce(requirements, '')
                )
            ) STORED
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_board ON monitored_jobs(board_id, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_provider ON monitored_jobs(ats_provider, status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_status ON monitored_jobs(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_dates ON monitored_jobs(status, first_discovered_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_monitored_jobs_search_vec ON monitored_jobs USING GIN (search_vector)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS monitor_leases (
            lease_name TEXT PRIMARY KEY,
            holder_id TEXT NOT NULL,
            acquired_at DOUBLE PRECISION NOT NULL,
            expires_at DOUBLE PRECISION NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS registry_meta (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO registry_meta (key, value) VALUES ('store_version', 1) ON CONFLICT (key) DO NOTHING"
    )
    if monitorable_providers:
        placeholders = ",".join("?" for _ in monitorable_providers)
        conn.execute(
            f"""
            UPDATE company_boards
            SET monitoring_capability = 'supported',
                next_scheduled_check = COALESCE(next_scheduled_check, 0.0)
            WHERE ats_provider IN ({placeholders})
              AND monitoring_capability IN ('unsupported', 'provisional')
            """,
            tuple(sorted(monitorable_providers)),
        )
    conn.commit()


def extract_monitored_job_fields(job: JobListing) -> dict[str, Any]:
    """Extract normalized column values for ``monitored_jobs`` upserts."""
    job_id = job.id.strip()
    provider = (job.ats_source or job.provider or "unknown").strip().lower()
    company_slug = job.company_slug or (job.id.split(":")[1] if ":" in job.id else "")
    company_name = job.company or humanize_slug(company_slug)
    title = job.title.strip()
    location = job.location.strip() if job.location else None

    salary_str: str | None = None
    if job.salary:
        if hasattr(job.salary, "model_dump_json"):
            salary_str = job.salary.model_dump_json()
        else:
            salary_str = str(job.salary)

    reqs_str: str | None = None
    if job.requirements:
        reqs_str = (
            json.dumps(job.requirements)
            if isinstance(job.requirements, list)
            else str(job.requirements)
        )

    posted_at_iso = job.posted_at.isoformat() if job.posted_at else None
    source_url = job.source_url or job.apply_url or ""
    apply_url = job.apply_url or job.source_url or ""
    confidence = float(job.extraction_confidence) if job.extraction_confidence is not None else None
    evidence_str: str | None = None
    if job.field_evidence:
        if isinstance(job.field_evidence, list):
            evidence_list = [
                (v.model_dump() if hasattr(v, "model_dump") else v)
                for v in job.field_evidence
            ]
            evidence_str = json.dumps(evidence_list)
        elif isinstance(job.field_evidence, dict):
            evidence_dict = {
                k: (v.model_dump() if hasattr(v, "model_dump") else v)
                for k, v in job.field_evidence.items()
            }
            evidence_str = json.dumps(evidence_dict)
        else:
            evidence_str = str(job.field_evidence)

    return {
        "job_id": job_id,
        "provider": provider,
        "company_slug": company_slug,
        "company_name": company_name,
        "title": title,
        "location": location,
        "work_model": job.work_model,
        "emp_type": job.employment_type,
        "salary_str": salary_str,
        "desc": job.description,
        "reqs_str": reqs_str,
        "posted_at_iso": posted_at_iso,
        "source_url": source_url,
        "apply_url": apply_url,
        "confidence": confidence,
        "evidence_str": evidence_str,
        "canonical_json": job.model_dump_json(),
    }


def execute_monitored_jobs_batch_upsert(
    conn: Any,
    deduped_jobs: dict[str, JobListing],
    *,
    board_id: int | None,
    content_fingerprint: str | None,
    refreshed_job_ids: set[str] | None,
    detail_states: dict[str, Any] | None,
    now: float,
) -> int:
    """Execute one transactional batch upsert against SQLite or PostgreSQL and bump ``store_version``."""
    job_ids = list(deduped_jobs.keys())
    existing_rows: dict[str, tuple[float, float]] = {}
    for start in range(0, len(job_ids), 200):
        chunk = job_ids[start : start + 200]
        placeholders = ",".join("?" for _ in chunk)
        for row in conn.execute(
            f"SELECT job_id, first_discovered_at, last_checked_at FROM monitored_jobs WHERE job_id IN ({placeholders})",
            tuple(chunk),
        ).fetchall():
            existing_rows[str(row[0])] = (
                float(row[1]) if row[1] is not None else now,
                float(row[2]) if row[2] is not None else 0.0,
            )

    rows_with_detail: list[tuple[Any, ...]] = []
    rows_without_detail: list[tuple[Any, ...]] = []

    for job_id, job in deduped_jobs.items():
        f = extract_monitored_job_fields(job)
        preserve = refreshed_job_ids is not None and job_id not in refreshed_job_ids
        existing = existing_rows.get(job_id)
        if existing is not None:
            first_ts = existing[0]
            checked_ts = existing[1] if preserve else now
        else:
            first_ts = now
            checked_ts = 0.0 if preserve else now

        ds = detail_states.get(job_id) if detail_states is not None else None
        base_tuple = (
            f["job_id"],
            board_id,
            f["provider"],
            f["company_slug"],
            f["company_name"],
            f["title"],
            f["location"],
            f["work_model"],
            f["emp_type"],
            f["salary_str"],
            f["desc"],
            f["reqs_str"],
            f["posted_at_iso"],
            first_ts,
            checked_ts,
            f["source_url"],
            f["apply_url"],
            f["confidence"],
            f["evidence_str"],
            "active",
            content_fingerprint,
            f["canonical_json"],
        )
        if ds is not None:
            rows_with_detail.append(
                base_tuple
                + (
                    ds.detail_status,
                    ds.detail_last_hydrated_at,
                    int(ds.detail_retry_count),
                    ds.detail_next_retry_at,
                    ds.detail_last_error,
                    ds.widget_location_signature,
                    ds.listing_item_hash,
                    0,
                    None,
                )
            )
        else:
            rows_without_detail.append(
                base_tuple + ("hydrated", now, 0, None, None, None, None, 0, None)
            )

    is_pg = getattr(conn, "is_postgres", False)
    for batch_rows, update_clause in (
        (rows_with_detail, _DETAIL_UPSERT_SET),
        (rows_without_detail, _COMMON_UPSERT_SET),
    ):
        if not batch_rows:
            continue
        if is_pg:
            conn.execute_values(
                f"INSERT INTO monitored_jobs ({_MONITORED_JOB_COLS}) VALUES %s ON CONFLICT(job_id) DO UPDATE SET {update_clause}",
                batch_rows,
            )
        else:
            q_marks = ", ".join("?" for _ in range(31))
            conn.executemany(
                f"INSERT INTO monitored_jobs ({_MONITORED_JOB_COLS}) VALUES ({q_marks}) ON CONFLICT(job_id) DO UPDATE SET {update_clause}",
                batch_rows,
            )

    conn.execute("UPDATE registry_meta SET value = value + 1 WHERE key = 'store_version'")
    conn.commit()
    return len(deduped_jobs)


def _esc_fts_token(tok: str) -> str:
    return tok.replace('"', "").replace("*", "")


def _esc_pg_token(tok: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "", tok)


def _token_sql_variants(tok: str) -> list[str]:
    """Return surface variants for stemmed tokens (e.g. 'security' -> ['security', 'securities'])."""
    variants = [tok]
    if len(tok) > 3 and tok.endswith("y") and tok[-2] not in "aeiou":
        variants.append(tok[:-1] + "ies")
    return variants


def build_monitored_search_plan(
    query: str,
    query_units: list[tuple[str, tuple[str, ...]]],
    *,
    relevance_active: bool,
    like_op: str,
) -> dict[str, Any]:
    """Build SQL ordering, FTS5/GIN queries, LIKE fallback clauses, and title-compound clauses."""
    clean_words = (
        []
        if relevance_active
        else [
            w for w in re.sub(r"[^\w\s-]", " ", query).split()
            if len(w) > 1 and not w.isdigit()
        ]
    )

    title_order_sql = "m.first_discovered_at DESC"
    title_order_params: list[Any] = []
    if relevance_active and query_units:
        score_terms: list[str] = []
        idx_u = 0
        while idx_u < len(query_units):
            collapsed, parts = query_units[idx_u]
            unit_pats: list[str] = []
            for base_tok in [collapsed] + [p for p in parts if len(p) > 1]:
                for var in _token_sql_variants(base_tok):
                    if var not in unit_pats:
                        unit_pats.append(var)
            if idx_u + 1 < len(query_units) and len(parts) == 1 and len(query_units[idx_u + 1][1]) == 1:
                joined = f"{collapsed}{query_units[idx_u + 1][0]}"
                for var in _token_sql_variants(joined):
                    if var not in unit_pats:
                        unit_pats.append(var)
            conds = []
            for pat_tok in unit_pats:
                conds.append(
                    f"REPLACE(REPLACE(m.title, '-', ''), ' ', '') {like_op} ? "
                    f"OR REPLACE(REPLACE(m.company_name, '-', ''), ' ', '') {like_op} ?"
                )
                pat = f"%{pat_tok}%"
                title_order_params.extend([pat, pat])
            score_terms.append(f"(CASE WHEN ({' OR '.join(conds)}) THEN 1 ELSE 0 END)")
            idx_u += 1
        if score_terms:
            title_order_sql = f"({' + '.join(score_terms)}) DESC, m.first_discovered_at DESC"

    def _pg_or_variants(tok: str) -> str:
        vars_pg = [_esc_pg_token(v) for v in _token_sql_variants(tok) if _esc_pg_token(v)]
        if not vars_pg:
            return ""
        if len(vars_pg) == 1:
            return f"{vars_pg[0]}:*"
        return "(" + " | ".join(f"{v}:*" for v in vars_pg) + ")"

    def _fts_or_variants(tok: str) -> str:
        vars_fts = [_esc_fts_token(v) for v in _token_sql_variants(tok) if _esc_fts_token(v)]
        if not vars_fts:
            return ""
        if len(vars_fts) == 1:
            return f'"{vars_fts[0]}"*'
        return "(" + " OR ".join(f'"{v}"*' for v in vars_fts) + ")"

    pg_tsquery = ""
    fts_query_str = ""
    if relevance_active and query_units:
        pg_clauses: list[str] = []
        fts_clauses: list[str] = []
        idx_u = 0
        while idx_u < len(query_units):
            collapsed, parts = query_units[idx_u]
            c_pg, c_fts = _pg_or_variants(collapsed), _fts_or_variants(collapsed)
            if len(parts) > 1:
                p_pg = [_pg_or_variants(p) for p in parts if _pg_or_variants(p)]
                p_fts = [_fts_or_variants(p) for p in parts if _fts_or_variants(p)]
                if c_pg and len(p_pg) > 1:
                    pg_clauses.append(f"({c_pg} | ({' & '.join(p_pg)}))")
                elif c_pg:
                    pg_clauses.append(c_pg)
                if c_fts and len(p_fts) > 1:
                    fts_clauses.append(f"({c_fts} OR ({' AND '.join(p_fts)}))")
                elif c_fts:
                    fts_clauses.append(c_fts)
                idx_u += 1
            elif idx_u + 1 < len(query_units) and len(query_units[idx_u + 1][1]) == 1:
                nxt = query_units[idx_u + 1][0]
                n_pg, n_fts = _pg_or_variants(nxt), _fts_or_variants(nxt)
                j_pg, j_fts = _pg_or_variants(f"{collapsed}{nxt}"), _fts_or_variants(f"{collapsed}{nxt}")
                if c_pg and n_pg and j_pg:
                    pg_clauses.append(f"(({c_pg} & {n_pg}) | {j_pg})")
                elif c_pg:
                    pg_clauses.append(c_pg)
                if c_fts and n_fts and j_fts:
                    fts_clauses.append(f"(({c_fts} AND {n_fts}) OR {j_fts})")
                elif c_fts:
                    fts_clauses.append(c_fts)
                idx_u += 2 if (c_pg and n_pg and j_pg) or (c_fts and n_fts and j_fts) else 1
            else:
                if c_pg:
                    pg_clauses.append(c_pg)
                if c_fts:
                    fts_clauses.append(c_fts)
                idx_u += 1
        pg_tsquery = " & ".join(pg_clauses)
        fts_query_str = " AND ".join(fts_clauses)
    elif clean_words:
        pg_tokens = [tok for w in clean_words if (tok := _esc_pg_token(w))]
        pg_tsquery = " & ".join(f"{tok}:*" for tok in pg_tokens)
        fts_query_str = " AND ".join(f'"{_esc_fts_token(w)}"*' for w in clean_words)

    def _word_like(word: str) -> tuple[str, list[str]]:
        exprs: list[str] = []
        w_params: list[str] = []
        for var in _token_sql_variants(word):
            pat = f"%{var}%"
            exprs.append(f"(m.title {like_op} ? OR m.company_name {like_op} ? OR m.description {like_op} ?)")
            w_params.extend([pat, pat, pat])
        if len(exprs) == 1:
            return exprs[0], w_params
        return "(" + " OR ".join(exprs) + ")", w_params

    like_clauses: list[str] = []
    like_params: list[str] = []
    compound_clauses: list[str] = []
    compound_params: list[str] = []
    if relevance_active:
        idx_u = 0
        while idx_u < len(query_units):
            collapsed, parts = query_units[idx_u]
            comp_exprs: list[str] = []
            for var in _token_sql_variants(collapsed):
                c_pat = f"%{var}%"
                comp_exprs.append(
                    f"REPLACE(REPLACE(m.title, '-', ''), ' ', '') {like_op} ? "
                    f"OR REPLACE(REPLACE(m.company_name, '-', ''), ' ', '') {like_op} ?"
                )
                compound_params.extend([c_pat, c_pat])
            compound_clauses.append("(" + " OR ".join(comp_exprs) + ")")
            if len(parts) > 1:
                c_expr, c_p = _word_like(collapsed)
                p_exprs, p_params = [], []
                for part in parts:
                    pe, pp = _word_like(part)
                    p_exprs.append(pe)
                    p_params.extend(pp)
                like_clauses.append(f"({c_expr} OR ({' AND '.join(p_exprs)}))")
                like_params.extend(c_p + p_params)
                idx_u += 1
            elif idx_u + 1 < len(query_units) and len(query_units[idx_u + 1][1]) == 1:
                e1, p1 = _word_like(collapsed)
                e2, p2 = _word_like(query_units[idx_u + 1][0])
                ej, pj = _word_like(f"{collapsed}{query_units[idx_u + 1][0]}")
                like_clauses.append(f"(({e1} AND {e2}) OR {ej})")
                like_params.extend(p1 + p2 + pj)
                idx_u += 2
            else:
                e1, p1 = _word_like(collapsed)
                like_clauses.append(e1)
                like_params.extend(p1)
                idx_u += 1
    else:
        for w in clean_words:
            e1, p1 = _word_like(w)
            like_clauses.append(e1)
            like_params.extend(p1)

    return {
        "has_terms": bool(query_units) if relevance_active else bool(clean_words),
        "title_order_sql": title_order_sql,
        "title_order_params": title_order_params,
        "pg_tsquery": pg_tsquery,
        "fts_query_str": fts_query_str,
        "like_clauses": like_clauses,
        "like_params": like_params,
        "compound_clauses": compound_clauses,
        "compound_params": compound_params,
    }
