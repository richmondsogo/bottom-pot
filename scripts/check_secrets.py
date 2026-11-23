"""
Lightweight secret and credential scanner for git-tracked repository files.

Flags committed private keys, secret API keys (including sk_* secret tokens and
non-placeholder pk_* publishable tokens), cloud access keys, and non-placeholder
credential assignments without touching gitignored local files like .env or
frontend/.env.local.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

_PLACEHOLDER_MARKERS: tuple[str, ...] = (
    "your_",
    "example",
    "sample",
    "placeholder",
    "dummy",
    "fake",
    "mock",
    "test",
    "redacted",
    "forbidden",
    "invalid",
    "xxx",
    "change_me",
    "replace_",
    "empty",
    "<",
)

_SECRET_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Private key block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    (
        "Secret key token (sk_*)",
        re.compile(r"\bsk_(?:live_|test_)?[A-Za-z0-9_\-]{12,}\b"),
    ),
    (
        "Publishable key token (pk_*)",
        re.compile(r"\bpk_[A-Za-z0-9_\-]{12,}\b"),
    ),
    (
        "GitHub personal access token",
        re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    ),
    (
        "AWS access key ID",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "OpenAI/Anthropic-style bearer token",
        re.compile(r"\b(?:sk-proj-|sk-ant-)[A-Za-z0-9_\-]{16,}\b"),
    ),
)

_ENV_CRED_ASSIGN_RE = re.compile(
    r"^\s*(?:SERPER_API_KEY|ADMIN_PASSWORD|ADMIN_SESSION_SECRET|API_SECRET_KEY)\s*=\s*(['\"]?)([^\s'\"#]+)\1"
)


def get_tracked_files(repo_root: Path) -> list[str]:
    """Return tracked repo-relative POSIX paths from git ls-files."""
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=str(repo_root))
    return sorted(p.decode("utf-8").replace("\\", "/") for p in raw.split(b"\x00") if p)


def _is_placeholder_token(token: str) -> bool:
    lowered = token.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


_PUBLIC_S3_SIGV4_CREDENTIAL_RE = re.compile(
    r"X-Amz-Credential=AKIA[0-9A-Z]{16}%2F\d{8}%2F[a-z0-9-]+%2Fs3%2Faws4_request"
)


def scan_text_for_secrets(rel_path: str, text: str) -> list[str]:
    """Return secret findings for one file's text."""
    findings: list[str] = []
    is_fixture = rel_path.startswith("tests/fixtures/")
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pattern in _SECRET_RULES:
            for match in pattern.finditer(line):
                token = match.group(0)
                if label in ("Secret key token (sk_*)", "Publishable key token (pk_*)") and _is_placeholder_token(token):
                    continue
                if label == "AWS access key ID" and is_fixture:
                    window = line[max(0, match.start() - 18) : match.end() + 80]
                    if _PUBLIC_S3_SIGV4_CREDENTIAL_RE.search(window):
                        continue
                findings.append(f"{rel_path}:{lineno}: {label} detected.")
        env_match = _ENV_CRED_ASSIGN_RE.match(line)
        if env_match:
            val = env_match.group(2)
            if not _is_placeholder_token(val) and len(val) >= 8:
                findings.append(f"{rel_path}:{lineno}: Non-placeholder credential assignment detected.")
    return findings


def scan_repository(
    repo_root: Path | None = None,
    tracked_files: Iterable[str] | None = None,
) -> list[str]:
    """Scan all tracked text files in *repo_root* for secrets."""
    root = (repo_root or REPO_ROOT).resolve()
    files = list(tracked_files) if tracked_files is not None else get_tracked_files(root)
    findings: list[str] = []
    for rel in files:
        norm = rel.replace("\\", "/")
        full = root / norm
        if not full.is_file():
            continue
        raw = full.read_bytes()
        if b"\x00" in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        findings.extend(scan_text_for_secrets(norm, text))
    return findings


def main() -> int:
    findings = scan_repository()
    if findings:
        print("Secret scan FAILED:")
        for item in findings:
            print(f"  - {item}")
        return 1
    print("Secret scan PASSED (0 tracked secret findings).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
