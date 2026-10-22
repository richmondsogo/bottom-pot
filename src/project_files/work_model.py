from __future__ import annotations

from dataclasses import dataclass
import html
import re
from typing import Any
from loguru import logger

@dataclass(frozen=True)
class WorkModelResult:
    value: str | None = None     # "remote" | "hybrid" | "in_person" | None
    source: str | None = None    # api_enum | jsonld | li_tag | location | title | description
    evidence: str | None = None

_ENUM = {
    "hybrid": "hybrid",
    "onsite": "in_person",
    "on site": "in_person",
    "in office": "in_person",
    "in person": "in_person",
    "inoffice": "in_person",
    "inperson": "in_person",
    "office": "in_person",
    "office based": "in_person",
    "office-based": "in_person",
    "vor ort": "in_person",
    "presencial": "in_person",
    "fully remote": "remote",
    "telecommute": "remote",
    "work from home": "remote",
    "wfh": "remote",
    "home office": "remote",
    "distributed": "remote",
    "anywhere": "remote",
    "worldwide": "remote",
    "virtual": "remote",
}

def _map_enum(v: Any) -> str | None:
    if v is None or isinstance(v, bool):
        return None
    k = re.sub(r"[\s_\-]+", " ", str(v).strip().lower())
    if not k:
        return None
    if k.startswith("remote"):
        return "remote"
    if k.startswith("hybrid"):
        return "hybrid"
    return _ENUM.get(k)   # NOT "flexible"

_NEG = re.compile(r"\b(?:not|no|non|never|without|isn'?t|aren'?t)\b[^.\n]{0,25}$", re.I)

_REMOTE = re.compile(
    r"\b(?:fully|100\s*%|completely|entirely)\s+remote\b|\bremote[- ]first\b"
    r"|\bremote\s+(?:position|role|job|opportunity|work|team|only|friendly|available)\b"
    r"|\bwork\s+from\s+(?:home|anywhere)\b|\bwork-from-home\b|\bwfh\b|\bwfh-first\b"
    r"|\btelecommut\w*"
    r"|\bdistributed\s+(?:team|workforce|company|culture)\b"
    r"|\bhome\s+office\b|\btélétravail\b|\bvirtual\s+(?:role|position|job)\b",
    re.I,
)
_HYBRID = re.compile(
    r"\bhybrid\b|\bhybridi[sz]ed\b"
    r"|\bpartially\s+remote\b|\bsome\s+remote\b"
    r"|\bflexible\s+(?:remote|hybrid|work\s*model)\b"
    r"|\bremote\s*[-/]\s*on\s*-?\s*site\b"
    r"|\b(?:mix|mixture|combination|split)\s+(?:of|between)\s+(?:remote|home|office)\b"
    r"|\b(?:remote|home)\s+(?:and|&|or)\s+(?:on\s*-?\s*site|office|in\s*-?\s*person)\b"
    r"|\b(?:on\s*-?\s*site|office|in\s*-?\s*person)\s+(?:and|&|or)\s+(?:remote|home)\b"
    r"|\bpartially\s+on\s*-?\s*site\b"
    r"|\b(?:[1-5]|one|two|three|four|five)\s+days?\s+(?:(?:a|per|each)\s+week\s+)?(?:in|at|on)\s*-?\s*(?:the\s+)?(?:office|site)\b"
    r"|\b(?:in|at)\s+(?:the\s+)?office\s+\d+\s+days\b"
    r"|\b(?:onsite|on-site|on site|office|in-office)\s+or\s+remote\b"
    r"|\bremote\s+or\s+(?:onsite|on-site|on site|office|in-office|office[- ]based)\b",
    re.I,
)
_ONSITE = re.compile(
    r"\bfully\s+on\s*-?\s*site\b|\b(?:on\s*-?\s*site|onsite)\s+(?:role|position|only|required|presence)\b"
    r"|\bmust\s+work\s+from\s+(?:the\s+)?office\b"
    r"|\bmust\s+be\s+(?:on\s*-?\s*site|in\s+the\s+office)\b"
    r"|\bin\s*-?\s*office\s+(?:role|position|presence)\b"
    r"|\bthis\s+is\s+an?\s+on\s*-?\s*site\b"
    r"|\bin\s*-?\s*person\s+collaboration\b|\boffice\s*-?\s*based\b"
    r"|\barbeit\s+vor\s+ort\b|\bpresencial\b|\bface\s+to\s+face\b",
    re.I,
)
_CTX = re.compile(
    r"\b(?:work|working|role|position|office|on-?site|remote|days|schedule"
    r"|location|arrangement|model|setup)\b",
    re.I,
)   # "hybrid" needs work context if bare word

_LOC_HYBRID = re.compile(r"\b(?:hybrid|partially\s+remote)\b", re.I)
_LOC_REMOTE = re.compile(r"\b(?:remote|telecommut\w*|work\s+from\s+home|wfh|anywhere|worldwide|virtual)\b", re.I)
_LOC_ONSITE = re.compile(r"\b(?:on\s*-?\s*site|onsite|in\s*-?\s*person|in\s*-?\s*office|office[- ]based)\b", re.I)

_TITLE_TAG = re.compile(
    r"[(\[]\s*(?:(?:fully|100\s*%)\s+)?(remote|hybrid|on-?site|virtual)[^)\]]*[)\]]"
    r"|[-–—|,]\s*(remote|hybrid|on-?site|virtual|flexible)\s*$"
    r"|^\s*(remote|virtual)\b",
    re.I,
)

_LI_TAG_RE = re.compile(r"(?<![\w#])#LI-(Remote|Hybrid|Onsite|On-site)\b", re.IGNORECASE)
_LI_ALL_STRIP_RE = re.compile(r"[ \t]*(?<![\w#])#LI-[A-Za-z0-9_-]+\b", re.IGNORECASE)

def strip_li_tags(text: str | None) -> str | None:
    """Remove any LinkedIn recruiter tags (#LI-*) from description text."""
    if not text:
        return text
    cleaned = _LI_ALL_STRIP_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip() or None

def _scan(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for model, rx in (("hybrid", _HYBRID), ("remote", _REMOTE), ("in_person", _ONSITE)):
        for m in rx.finditer(text):
            if _NEG.search(text[max(0, m.start() - 25):m.start()]):
                continue
            matched_word = m.group(0).lower()
            if model == "hybrid" and matched_word in ("hybrid", "hybridised", "hybridized"):
                surrounding = text[max(0, m.start() - 40):m.end() + 40].replace(m.group(0), " ")
                if not _CTX.search(surrounding):
                    continue
            found[model] = text[max(0, m.start() - 40):m.end() + 40].strip()
            break
    if "hybrid" in found:
        if "remote" in found:
            has_fully_remote = bool(re.search(r"\b(?:fully|100\s*%|completely|entirely)\s+remote\b", text, re.I))
            has_office_days = bool(re.search(r"\b(?:[1-5]|one|two|three|four|five)\s+days?\b", text, re.I))
            if has_fully_remote and has_office_days:
                return found
        if "in_person" in found:
            has_fully_onsite = bool(re.search(r"\b(?:fully\s+on\s*-?\s*site|100%\s+on\s*-?\s*site)\b", text, re.I))
            if has_fully_onsite:
                return found
        return {"hybrid": found["hybrid"]}
    return found

def resolve_work_model(
    *,
    workplace_type: Any = None,
    is_remote: bool | None = None,
    jsonld_location_type: str | None = None,
    location: str | None = None,
    title: str | None = None,
    description: str | None = None,
    description_ok: bool = False,
    trusted_description: str | None = None,
) -> WorkModelResult:
    # 1. API Enum
    api_result: WorkModelResult | None = None
    if workplace_type and not isinstance(workplace_type, bool):
        if v := _map_enum(workplace_type):
            api_result = WorkModelResult(v, "api_enum", str(workplace_type))
        elif len(str(workplace_type)) < 100:
            scanned = _scan(str(workplace_type))
            if "hybrid" in scanned:
                api_result = WorkModelResult("hybrid", "api_enum", str(workplace_type).strip())
            else:
                res_dict = {}
                for m_name, rx in (("remote", _LOC_REMOTE), ("in_person", _LOC_ONSITE)):
                    if m := rx.search(str(workplace_type)):
                        res_dict[m_name] = m.group(0)
                if len(res_dict) == 1:
                    k = next(iter(res_dict.keys()))
                    api_result = WorkModelResult(k, "api_enum", str(workplace_type).strip())

    # 2. JSON-LD
    jsonld_result: WorkModelResult | None = None
    if (jsonld_location_type or "").upper() == "TELECOMMUTE":
        jsonld_result = WorkModelResult("remote", "jsonld", "jobLocationType=TELECOMMUTE")

    # Scan li_tag from trusted_description if provided
    li_model: str | None = None
    li_evidence: str | None = None
    if trusted_description:
        raw_trusted = html.unescape(str(trusted_description))
        matches = list(_LI_TAG_RE.finditer(raw_trusted))
        if matches:
            tags: set[tuple[str, str]] = set()
            for m in matches:
                tag_word = m.group(1).lower().replace("-", "")
                tag_model = "in_person" if tag_word == "onsite" else tag_word
                tags.add((tag_model, m.group(0)))
            distinct_models = {t[0] for t in tags}
            if len(distinct_models) == 1:
                li_model, li_evidence = next(iter(tags))
            else:
                # Multiple different #LI- tags -> None
                li_model = None

    # Handle api_enum / jsonld precedence over li_tag
    if api_result:
        if li_model and li_model != api_result.value:
            logger.info(
                f"[work_model] Disagreement: api_enum='{api_result.value}' vs li_tag='{li_model}'"
            )
        return api_result

    if jsonld_result:
        if li_model and li_model != jsonld_result.value:
            logger.info(
                f"[work_model] Disagreement: jsonld='{jsonld_result.value}' vs li_tag='{li_model}'"
            )
        return jsonld_result

    # 3. li_tag (ladder: api_enum > jsonld > li_tag > location > title > description scan)
    # Check if li_tag disagrees with description scan if description scan is active
    desc_scan_result: dict[str, str] = {}
    if description and description_ok:
        desc_scan_result = _scan(description)

    if li_model in ("remote", "hybrid"):
        if len(desc_scan_result) == 1:
            desc_model = next(iter(desc_scan_result.keys()))
            if desc_model != li_model:
                # Disagreement with single description-scan result -> None
                logger.info(
                    f"[work_model] Disagreement between li_tag='{li_model}' and description='{desc_model}' -> None"
                )
                return WorkModelResult()
        return WorkModelResult(li_model, "li_tag", li_evidence)

    # 4. Location
    if location:
        loc_res: dict[str, str] = {}
        for m_name, rx in (("hybrid", _LOC_HYBRID), ("remote", _LOC_REMOTE), ("in_person", _LOC_ONSITE)):
            if m := rx.search(location):
                loc_res[m_name] = m.group(0)
        if len(loc_res) == 1:
            m_name, ev = next(iter(loc_res.items()))
            return WorkModelResult(m_name, "location", location)

    # 5. Title
    if title:
        if m := _TITLE_TAG.search(title):
            matched_text = m.group(0).strip()
            kw = (m.group(1) or m.group(2) or m.group(3)).lower().replace("-", "")
            mapped = "in_person" if kw in ("onsite", "on_site") else ("hybrid" if kw in ("hybrid", "flexible") else "remote")
            return WorkModelResult(mapped, "title", matched_text)

    # 6. Description scan (only when description_ok is True)
    if description and description_ok:
        if not desc_scan_result:
            desc_scan_result = _scan(description)
        if len(desc_scan_result) == 1:  # conflicting signals -> unknown
            (model, ev), = desc_scan_result.items()
            return WorkModelResult(model, "description", ev)

    # 7. Weak #LI-Onsite fallback: only if nothing else was available AND it is the only signal
    if li_model == "in_person":
        return WorkModelResult("in_person", "li_tag", "li_tag_onsite")

    # 8. Unknown
    return WorkModelResult()
