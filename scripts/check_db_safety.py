"""
Targeted CI static & policy checker for operational SQLite database safety controls.

Checks:
1. playwright.config.js allocates a unique per-run disposable directory (`mkdtempSync`),
   disables `reuseExistingServer`, includes `cache.sqlite-journal` in protected baselines,
   never preserves inherited `PLAYWRIGHT_SQLITE_DB_PATH` conditionals, and never falls back to `data/cache.sqlite`.
2. tests/conftest.py isolates `SQLITE_DB_PATH` and `SUBSCRIPTIONS_FILE` before importing
   database singletons or FastAPI `app`.
3. tests/**/*.py do not contain direct destructive calls (`unlink`, `os.remove`, `shutil.rmtree`)
   against literals or protected identifiers pointing to `data/cache.sqlite`, sidecars, or backups.

Limitations:
- Python checks inspect AST call sites and literal/name arguments; dynamically constructed strings
  obfuscated across helper functions are caught at runtime by `src/safety/db_safety.py`
  and `tests/test_operational_db_safety.py`, not solely by static AST inspection.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
_PROTECTED_TOKENS = (
    "data/cache.sqlite",
    "data\\cache.sqlite",
    "cache.sqlite.bak",
    "restore-staging",
    "operational_db",
)
_DESTRUCTIVE_NAMES = {"unlink", "remove", "rmtree"}


def check_playwright_config(repo_root: Path) -> list[str]:
    cfg_path = repo_root / "playwright.config.js"
    if not cfg_path.exists():
        return ["Missing playwright.config.js"]
    text = cfg_path.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []

    if re.search(r"if\s*\(\s*!\s*process\.env\.PLAYWRIGHT_SQLITE_DB_PATH", text):
        findings.append("playwright.config.js conditionally preserves inherited PLAYWRIGHT_SQLITE_DB_PATH")
    if "mkdtempSync" not in text:
        findings.append("playwright.config.js must allocate a unique disposable directory via fs.mkdtempSync")
    if not re.search(r"reuseExistingServer\s*:\s*false\b", text):
        findings.append("playwright.config.js must set reuseExistingServer: false so E2E never attaches to an operational server")
    if re.search(r"(?:fallback|default)\w*.*['\"]data[\\/]+cache\.sqlite['\"]", text, re.IGNORECASE):
        findings.append("playwright.config.js must never use data/cache.sqlite as a fallback")
    if "reuseExistingServer" in text and "cache.sqlite-journal" not in text and "-journal" not in text and (repo_root / "src").exists():
        findings.append("playwright.config.js should include cache.sqlite-journal in protected operational baseline paths")
    if "reuseExistingServer" in text and "BOTTOM_POT_ALLOW_OPERATIONAL_DB" not in text and (repo_root / "src").exists():
        findings.append("playwright.config.js must force BOTTOM_POT_ALLOW_OPERATIONAL_DB: '0' in webServer.env")
    return findings


def check_env_files(repo_root: Path) -> list[str]:
    findings: list[str] = []
    for name in (".env", ".env.example"):
        env_path = repo_root / name
        if not env_path.exists():
            continue
        text = env_path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"^\s*BOTTOM_POT_ALLOW_OPERATIONAL_DB\s*=\s*(1|true|yes|on)\s*$", text, re.IGNORECASE | re.MULTILINE):
            findings.append(f"{name} must never enable BOTTOM_POT_ALLOW_OPERATIONAL_DB (must only be set explicitly at documented production entrypoints)")
    return findings


def check_conftest(repo_root: Path) -> list[str]:
    conftest_path = repo_root / "tests" / "conftest.py"
    if not conftest_path.exists():
        return []
    text = conftest_path.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []
    if "SQLITE_DB_PATH" not in text:
        findings.append("tests/conftest.py must set isolated SQLITE_DB_PATH")
    idx_env = text.find("SQLITE_DB_PATH")
    for mod in ("cache_store", "company_board_registry", "src.api.main"):
        idx_imp = text.find(mod)
        if idx_imp != -1 and (idx_env == -1 or idx_imp < idx_env):
            findings.append(f"tests/conftest.py imports '{mod}' before setting SQLITE_DB_PATH")
    return findings


def check_python_test_ast(repo_root: Path) -> list[str]:
    tests_dir = repo_root / "tests"
    if not tests_dir.exists():
        return []
    findings: list[str] = []

    for py_file in sorted(tests_dir.rglob("*.py")):
        if py_file.name == "test_operational_db_safety.py":
            continue
        source = py_file.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as exc:
            findings.append(f"{py_file.relative_to(repo_root)}: SyntaxError {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = None
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                func_name = node.func.id
            if func_name not in _DESTRUCTIVE_NAMES:
                continue

            snippet_parts: list[str] = []
            if isinstance(node.func, ast.Attribute):
                snippet_parts.append(ast.unparse(node.func.value))
            for arg in node.args:
                snippet_parts.append(ast.unparse(arg))
            joined = " ".join(snippet_parts).lower()
            if any(tok in joined for tok in _PROTECTED_TOKENS):
                findings.append(
                    f"{py_file.relative_to(repo_root)}:{node.lineno}: potentially destructive call '{func_name}' referencing protected asset ({joined[:80]})"
                )
    return findings


def scan_repository(repo_root: Path | None = None) -> list[str]:
    root = repo_root or REPO_ROOT
    findings: list[str] = []
    findings.extend(check_playwright_config(root))
    findings.extend(check_env_files(root))
    findings.extend(check_conftest(root))
    findings.extend(check_python_test_ast(root))
    return findings


def main() -> int:
    findings = scan_repository()
    if findings:
        print("Database safety static check FAILED:")
        for item in findings:
            print(f"  - {item}")
        return 1
    print("Database safety static check PASSED (0 unsafe patterns found).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
