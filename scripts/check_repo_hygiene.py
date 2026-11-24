"""
Repository hygiene & institutional memory static checks for Bottom Pot.

Enforces the automated rules defined in AGENTS.md and docs/LESSONS.md:
1. Top-level allow-list (L-08)
2. Asset and fixture size budgets (L-08)
3. No commit SHAs in committed documentation outside history/steps (L-04)
4. No forbidden tracked artifacts (__pycache__, scratch/, *.bak*, *.orig, *.log) (L-02, L-08)
5. Source module line-count limit (<= 1,500 lines, ratcheted legacy list) (L-03, L-08)
6. No new unjustified broad except handlers in safety/storage/monitoring (L-02)
7. No direct real-network calls in offline tests not marked @pytest.mark.live (L-01)
8. No broken markdown links in active documentation (L-04, L-08)
9. Every active doc under docs/ must be reachable from docs/README.md (L-08)
"""

from __future__ import annotations

import ast
import re
import subprocess
from collections import deque
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]

ALLOWED_TOP_LEVEL_ENTRIES: frozenset[str] = frozenset({
    ".agents",
    ".codex",
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".github",
    ".gitignore",
    "AGENTS.md",
    "BUILD_PROTOCOL.md",
    "CONTEXT.md",
    "CONTRIBUTING.md",
    "DESIGN.md",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_DATA.md",
    "docs",
    "frontend",
    "main.py",
    "package-lock.json",
    "package.json",
    "playwright.config.js",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
    "scripts",
    "skills-lock.json",
    "src",
    "tests",
})

IMAGE_EXTS: frozenset[str] = frozenset({
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
})
IMAGE_SIZE_BUDGET_BYTES = 500 * 1024
FIXTURE_SIZE_BUDGET_BYTES = 500 * 1024

# Phase 8 THIRD_PARTY_DATA.md documents all existing >500 KB fixtures; no implicit exceptions remain.
GRANDFATHERED_PRE_PHASE8_FIXTURES: frozenset[str] = frozenset()

MAX_SOURCE_LINES = 1500
# Legacy pre-Phase-3/4 monoliths capped at their baseline line counts (ratcheted down in Phases 3-4).
GRANDFATHERED_LARGE_MODULES: dict[str, int] = {
    "src/ats/ats_api_client.py": 3819,
    "src/storage/company_board_registry.py": 1770,
    "src/extraction/eligibility_extractor.py": 1529,
    "src/discovery/nigerian_scrapers.py": 2198,
}

SAFETY_PACKAGE_PREFIXES: tuple[str, ...] = (
    "src/safety/",
    "src/storage/",
    "src/monitoring/",
)
LEGACY_SAFETY_MODULES: frozenset[str] = frozenset()
# Baseline unjustified broad-except counts cleared to zero in Phase 4.6.
GRANDFATHERED_BROAD_EXCEPT_COUNTS: dict[str, int] = {}

HISTORICAL_DOC_PREFIXES: tuple[str, ...] = (
    "docs/steps/",
    "docs/history/",
    "docs/superpowers/",
)

_FULL_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
_EXPLICIT_SHA_RE = re.compile(
    r"(?:commit|merge|first|last|base|head)\s+sha\s*[:#`]*\s*[0-9a-f]{7,40}\b",
    re.IGNORECASE,
)
_FENCED_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def get_tracked_files(repo_root: Path) -> list[str]:
    """Return tracked repo-relative POSIX paths from git ls-files."""
    raw = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=str(repo_root),
    )
    return sorted(p.decode("utf-8").replace("\\", "/") for p in raw.split(b"\x00") if p)


def _norm_paths(tracked_files: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw in tracked_files:
        if not raw:
            continue
        p = raw.replace("\\", "/")
        while p.startswith("./"):
            p = p[2:]
        normalized.append(p)
    return sorted(normalized)


def _strip_fenced_blocks_preserving_lines(text: str) -> str:
    return _FENCED_BLOCK_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _is_active_markdown_doc(rel_path: str) -> bool:
    if not rel_path.endswith(".md"):
        return False
    if "/" not in rel_path:
        return True
    if not rel_path.startswith("docs/"):
        return False
    return not rel_path.startswith(HISTORICAL_DOC_PREFIXES)


def check_top_level_allowlist(
    _repo_root: Path,
    tracked_files: Iterable[str],
    *,
    allowlist: frozenset[str] = ALLOWED_TOP_LEVEL_ENTRIES,
) -> list[str]:
    """Fail if any tracked top-level path sits outside the allow-list (protects L-08)."""
    findings: list[str] = []
    seen_disallowed: set[str] = set()
    for rel in _norm_paths(tracked_files):
        top = rel.split("/", 1)[0]
        if top not in allowlist and top not in seen_disallowed:
            seen_disallowed.add(top)
            findings.append(
                f"[L-08] Unexpected top-level tracked entry '{top}' outside allow-list ({rel})."
            )
    return findings


def check_asset_size_budgets(repo_root: Path, tracked_files: Iterable[str]) -> list[str]:
    """Fail on oversized tracked images or undocumented fixtures > 500 KB (protects L-08)."""
    findings: list[str] = []
    third_party_doc = repo_root / "THIRD_PARTY_DATA.md"
    third_party_text = (
        third_party_doc.read_text(encoding="utf-8", errors="replace")
        if third_party_doc.exists()
        else ""
    )

    for rel in _norm_paths(tracked_files):
        full = repo_root / rel
        if not full.is_file():
            continue
        size = full.stat().st_size
        suffix = full.suffix.lower()

        if suffix in IMAGE_EXTS and size > IMAGE_SIZE_BUDGET_BYTES:
            if not (third_party_text and rel in third_party_text):
                findings.append(
                    f"[L-08] Tracked image '{rel}' is {size} bytes (> {IMAGE_SIZE_BUDGET_BYTES} byte budget) without THIRD_PARTY_DATA.md entry."
                )

        if rel.startswith("tests/fixtures/") and size > FIXTURE_SIZE_BUDGET_BYTES:
            documented = bool(third_party_text and rel in third_party_text)
            grandfathered = not third_party_text and rel in GRANDFATHERED_PRE_PHASE8_FIXTURES
            if not documented and not grandfathered:
                findings.append(
                    f"[L-08] Tracked fixture '{rel}' is {size} bytes (> {FIXTURE_SIZE_BUDGET_BYTES} byte budget) without THIRD_PARTY_DATA.md entry."
                )
    return findings


def check_no_commit_shas_in_docs(repo_root: Path, tracked_files: Iterable[str]) -> list[str]:
    """Fail if active markdown docs contain commit SHAs (protects L-04)."""
    findings: list[str] = []
    for rel in _norm_paths(tracked_files):
        if not _is_active_markdown_doc(rel):
            continue
        full = repo_root / rel
        if not full.is_file():
            continue
        cleaned = _strip_fenced_blocks_preserving_lines(
            full.read_text(encoding="utf-8", errors="replace")
        )
        for lineno, line in enumerate(cleaned.splitlines(), 1):
            if _FULL_SHA_RE.search(line) or _EXPLICIT_SHA_RE.search(line):
                findings.append(
                    f"[L-04] {rel}:{lineno}: commit SHA reference found in active doc (git/PR description owns provenance)."
                )
    return findings


def check_forbidden_tracked_files(tracked_files: Iterable[str]) -> list[str]:
    """Fail if cache, scratch, backup, or log artifacts are tracked (protects L-02, L-08)."""
    findings: list[str] = []
    for rel in _norm_paths(tracked_files):
        parts = rel.split("/")
        name = parts[-1]
        if "__pycache__" in parts or "scratch" in parts:
            findings.append(f"[L-08] Forbidden tracked path '{rel}' (__pycache__ or scratch/).")
        elif name.endswith(".bak") or ".bak-" in name:
            findings.append(f"[L-02] Forbidden tracked backup file '{rel}'.")
        elif name.endswith(".orig") or name.endswith(".log"):
            findings.append(f"[L-08] Forbidden tracked artifact '{rel}' (.orig or .log).")
    return findings


def check_source_module_line_limits(repo_root: Path, tracked_files: Iterable[str]) -> list[str]:
    """Fail if a Python source module under src/ exceeds 1,500 lines (protects L-03, L-08)."""
    findings: list[str] = []
    for rel in _norm_paths(tracked_files):
        if not (rel.startswith("src/") and rel.endswith(".py")):
            continue
        full = repo_root / rel
        if not full.is_file():
            continue
        line_count = len(full.read_text(encoding="utf-8", errors="replace").splitlines())
        cap = GRANDFATHERED_LARGE_MODULES.get(rel, MAX_SOURCE_LINES)
        if line_count > cap:
            findings.append(
                f"[L-03] Source module '{rel}' has {line_count} lines (limit {cap})."
            )
    return findings


def _is_broad_exception_expr(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"Exception", "BaseException"}
    if isinstance(node, ast.Tuple):
        return any(_is_broad_exception_expr(elt) for elt in node.elts)
    return False


def check_safety_broad_excepts(repo_root: Path, tracked_files: Iterable[str]) -> list[str]:
    """Fail on new unjustified broad except handlers in safety/storage/monitoring (protects L-02)."""
    findings: list[str] = []
    for rel in _norm_paths(tracked_files):
        is_target = rel.endswith(".py") and (
            rel.startswith(SAFETY_PACKAGE_PREFIXES) or rel in LEGACY_SAFETY_MODULES
        )
        if not is_target:
            continue
        full = repo_root / rel
        if not full.is_file():
            continue
        source = full.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            findings.append(f"[L-02] {rel}: SyntaxError while scanning exceptions ({exc}).")
            continue

        unjustified: list[int] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None or _is_broad_exception_expr(node.type):
                header = lines[node.lineno - 1] if 0 < node.lineno <= len(lines) else ""
                if "# broad-except-ok:" not in header:
                    unjustified.append(node.lineno)

        allowed_legacy = GRANDFATHERED_BROAD_EXCEPT_COUNTS.get(rel, 0)
        if len(unjustified) > allowed_legacy:
            findings.append(
                f"[L-02] '{rel}' has {len(unjustified)} unjustified broad except handler(s) "
                f"(allowed baseline {allowed_legacy}) at lines {unjustified}; "
                "narrow the exception or add '# broad-except-ok: <reason>'."
            )
    return findings


def _has_live_marker(decorators: list[ast.expr]) -> bool:
    for dec in decorators:
        unparsed = ast.unparse(dec)
        if unparsed == "pytest.mark.live" or unparsed.endswith(".mark.live"):
            return True
    return False


def _is_module_marked_live(tree: ast.Module) -> bool:
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "pytestmark":
                    if "mark.live" in ast.unparse(stmt.value):
                        return True
    return False


_FORBIDDEN_NETWORK_CALLS: frozenset[str] = frozenset({
    "urllib.request.urlopen",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.head",
    "requests.patch",
    "requests.request",
    "http.client.HTTPConnection",
    "http.client.HTTPSConnection",
    "socket.create_connection",
    "socket.getaddrinfo",
})


def _attr_dotted_name(expr: ast.expr) -> str | None:
    parts: list[str] = []
    cur: ast.expr = expr
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _iter_direct_calls_in_body(nodes: list[ast.stmt]) -> Iterable[ast.Call]:
    """Walk statements without descending into nested helper function definitions."""
    stack: list[ast.AST] = list(nodes)
    while stack:
        cur = stack.pop()
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(cur, ast.Call):
            yield cur
        stack.extend(ast.iter_child_nodes(cur))


def check_offline_test_network_discipline(repo_root: Path, tracked_files: Iterable[str]) -> list[str]:
    """Fail if an offline test function directly calls real-network APIs without @pytest.mark.live (protects L-01)."""
    findings: list[str] = []
    for rel in _norm_paths(tracked_files):
        if not (rel.startswith("tests/") and rel.endswith(".py")):
            continue
        full = repo_root / rel
        if not full.is_file():
            continue
        source = full.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            findings.append(f"[L-01] {rel}: SyntaxError while scanning offline tests ({exc}).")
            continue

        if _is_module_marked_live(tree):
            continue

        test_nodes: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, bool]] = []
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name.startswith("test_"):
                test_nodes.append((stmt, _has_live_marker(stmt.decorator_list)))
            elif isinstance(stmt, ast.ClassDef):
                cls_live = _has_live_marker(stmt.decorator_list)
                for member in stmt.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and member.name.startswith("test_"):
                        test_nodes.append((member, cls_live or _has_live_marker(member.decorator_list)))

        for fn, is_live in test_nodes:
            if is_live:
                continue
            for call in _iter_direct_calls_in_body(fn.body):
                dotted = _attr_dotted_name(call.func)
                if dotted in _FORBIDDEN_NETWORK_CALLS:
                    findings.append(
                        f"[L-01] {rel}:{call.lineno}: '{fn.name}' calls '{dotted}' without @pytest.mark.live."
                    )
    return findings


def _extract_local_markdown_links(markdown_text: str) -> list[str]:
    stripped = _strip_fenced_blocks_preserving_lines(markdown_text)
    stripped = _INLINE_CODE_RE.sub("", stripped)
    targets: list[str] = []
    for match in _MD_LINK_RE.finditer(stripped):
        raw = match.group(1).strip()
        if not raw or raw.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = raw.split("#", 1)[0].split("?", 1)[0].strip()
        if target:
            targets.append(target)
    return targets


def check_docs_links(repo_root: Path, tracked_files: Iterable[str]) -> list[str]:
    """Fail if any local markdown link in active docs resolves to a missing file (protects L-04, L-08)."""
    findings: list[str] = []
    for rel in _norm_paths(tracked_files):
        if not _is_active_markdown_doc(rel):
            continue
        full = repo_root / rel
        if not full.is_file():
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        for target in _extract_local_markdown_links(text):
            resolved = (full.parent / target).resolve()
            if not resolved.exists():
                findings.append(
                    f"[L-08] Broken markdown link in '{rel}': '{target}' does not exist."
                )
    return findings


def check_docs_reachability(repo_root: Path, tracked_files: Iterable[str]) -> list[str]:
    """Fail if any active markdown doc under docs/ is unreachable from docs/README.md (protects L-08)."""
    index_rel = "docs/README.md"
    index_path = (repo_root / index_rel).resolve()
    if not index_path.is_file():
        return [f"[L-08] Missing documentation index '{index_rel}'."]

    tracked_set = set(_norm_paths(tracked_files))
    reachable: set[str] = set()
    queue: deque[Path] = deque([index_path])
    visited: set[Path] = set()
    root_resolved = repo_root.resolve()

    while queue:
        cur = queue.popleft()
        if cur in visited or not cur.is_file():
            continue
        visited.add(cur)
        try:
            cur_rel = cur.relative_to(root_resolved).as_posix()
        except ValueError:
            continue
        reachable.add(cur_rel)
        text = cur.read_text(encoding="utf-8", errors="replace")
        for target in _extract_local_markdown_links(text):
            resolved = (cur.parent / target).resolve()
            if resolved.is_dir():
                candidate = (resolved / "README.md").resolve()
                if candidate.is_file():
                    resolved = candidate
            try:
                res_rel = resolved.relative_to(root_resolved).as_posix()
            except ValueError:
                continue
            if res_rel.startswith("docs/") and res_rel.endswith(".md") and not res_rel.startswith(HISTORICAL_DOC_PREFIXES):
                queue.append(resolved)

    findings: list[str] = []
    for rel in sorted(tracked_set):
        if not rel.startswith("docs/") or not rel.endswith(".md"):
            continue
        if rel == index_rel or rel.startswith(HISTORICAL_DOC_PREFIXES):
            continue
        if rel not in reachable:
            findings.append(
                f"[L-08] Active doc '{rel}' is unreachable from docs/README.md."
            )
    return findings


def scan_repository(
    repo_root: Path | None = None,
    tracked_files: Iterable[str] | None = None,
) -> list[str]:
    """Run all repository hygiene checks and return failure messages."""
    root = (repo_root or REPO_ROOT).resolve()
    files = list(tracked_files) if tracked_files is not None else get_tracked_files(root)
    findings: list[str] = []
    findings.extend(check_top_level_allowlist(root, files))
    findings.extend(check_asset_size_budgets(root, files))
    findings.extend(check_no_commit_shas_in_docs(root, files))
    findings.extend(check_forbidden_tracked_files(files))
    findings.extend(check_source_module_line_limits(root, files))
    findings.extend(check_safety_broad_excepts(root, files))
    findings.extend(check_offline_test_network_discipline(root, files))
    findings.extend(check_docs_links(root, files))
    findings.extend(check_docs_reachability(root, files))
    return findings


def main() -> int:
    findings = scan_repository()
    if findings:
        print("Repository hygiene check FAILED:")
        for item in findings:
            print(f"  - {item}")
        return 1
    print("Repository hygiene check PASSED (all 9 institutional-memory rules green).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
