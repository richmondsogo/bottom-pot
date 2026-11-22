"""Passing and failing unit tests for every rule in scripts/check_repo_hygiene.py."""

from __future__ import annotations

from pathlib import Path

from scripts.check_repo_hygiene import (
    IMAGE_SIZE_BUDGET_BYTES,
    MAX_SOURCE_LINES,
    check_asset_size_budgets,
    check_docs_links,
    check_docs_reachability,
    check_forbidden_tracked_files,
    check_no_commit_shas_in_docs,
    check_offline_test_network_discipline,
    check_safety_broad_excepts,
    check_source_module_line_limits,
    check_top_level_allowlist,
    scan_repository,
)


def test_real_repository_passes_all_hygiene_checks():
    assert scan_repository() == []


def test_rule_1_top_level_allowlist_pass_and_fail(tmp_path: Path):
    assert (
        check_top_level_allowlist(
            tmp_path,
            [".agents/skills/x.md", ".gitignore", "README.md", "src/core/settings.py", "docs/README.md"],
        )
        == []
    )
    findings = check_top_level_allowlist(tmp_path, ["README.md", "stray_dump.txt"])
    assert len(findings) == 1
    assert "L-08" in findings[0]
    assert "stray_dump.txt" in findings[0]


def test_rule_2_asset_size_budgets_pass_and_fail(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    small_img = tmp_path / "docs" / "ok.png"
    small_img.write_bytes(b"0" * 1024)
    assert check_asset_size_budgets(tmp_path, ["docs/ok.png"]) == []

    big_img = tmp_path / "docs" / "huge.png"
    big_img.write_bytes(b"0" * (IMAGE_SIZE_BUDGET_BYTES + 1))
    findings = check_asset_size_budgets(tmp_path, ["docs/huge.png"])
    assert len(findings) == 1
    assert "L-08" in findings[0]

    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    big_fix = tmp_path / "tests" / "fixtures" / "new_huge.json"
    big_fix.write_bytes(b"0" * (IMAGE_SIZE_BUDGET_BYTES + 1))
    fix_findings = check_asset_size_budgets(tmp_path, ["tests/fixtures/new_huge.json"])
    assert len(fix_findings) == 1
    assert "L-08" in fix_findings[0]


def test_rule_3_no_commit_shas_in_docs_pass_and_fail(tmp_path: Path):
    (tmp_path / "docs" / "steps").mkdir(parents=True)
    active = tmp_path / "docs" / "guide.md"
    active.write_text("# Guide\nProvenance lives in PR #57.\n", encoding="utf-8")
    historical = tmp_path / "docs" / "steps" / "01-old.md"
    historical.write_text("Merge Commit SHA: " + ("a" * 40) + "\n", encoding="utf-8")
    assert check_no_commit_shas_in_docs(tmp_path, ["docs/guide.md", "docs/steps/01-old.md"]) == []

    bad = tmp_path / "docs" / "bad.md"
    bad.write_text("Commit SHA: deadbeef12\n", encoding="utf-8")
    findings = check_no_commit_shas_in_docs(tmp_path, ["docs/bad.md"])
    assert len(findings) == 1
    assert "L-04" in findings[0]


def test_rule_4_forbidden_tracked_files_pass_and_fail():
    assert check_forbidden_tracked_files(["src/core/settings.py", "docs/LESSONS.md"]) == []
    findings = check_forbidden_tracked_files([
        "src/__pycache__/config.cpython-312.pyc",
        "scratch/notes.txt",
        "data/cache.sqlite.bak-test",
        "merge.orig",
        "run.log",
    ])
    assert len(findings) == 5
    assert all(("L-02" in f or "L-08" in f) for f in findings)


def test_rule_5_source_module_line_limits_pass_and_fail(tmp_path: Path):
    (tmp_path / "src" / "core").mkdir(parents=True)
    ok_mod = tmp_path / "src" / "core" / "ok.py"
    ok_mod.write_text("x = 1\n" * MAX_SOURCE_LINES, encoding="utf-8")
    assert check_source_module_line_limits(tmp_path, ["src/core/ok.py"]) == []

    too_long = tmp_path / "src" / "core" / "bloated.py"
    too_long.write_text("x = 1\n" * (MAX_SOURCE_LINES + 1), encoding="utf-8")
    findings = check_source_module_line_limits(tmp_path, ["src/core/bloated.py"])
    assert len(findings) == 1
    assert "L-03" in findings[0]


def test_rule_6_safety_broad_excepts_pass_and_fail(tmp_path: Path):
    (tmp_path / "src" / "safety").mkdir(parents=True)
    ok_file = tmp_path / "src" / "safety" / "guard.py"
    ok_file.write_text(
        "def f():\n"
        "    try:\n"
        "        return 1\n"
        "    except ValueError:\n"
        "        return 0\n"
        "    except Exception:  # broad-except-ok: boundary guard\n"
        "        return 0\n",
        encoding="utf-8",
    )
    assert check_safety_broad_excepts(tmp_path, ["src/safety/guard.py"]) == []

    bad_file = tmp_path / "src" / "safety" / "leaky.py"
    bad_file.write_text(
        "def f():\n"
        "    try:\n"
        "        return 1\n"
        "    except Exception:\n"
        "        return 0\n",
        encoding="utf-8",
    )
    findings = check_safety_broad_excepts(tmp_path, ["src/safety/leaky.py"])
    assert len(findings) == 1
    assert "L-02" in findings[0]


def test_rule_7_offline_test_network_discipline_pass_and_fail(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    ok_test = tmp_path / "tests" / "test_ok.py"
    ok_test.write_text(
        "import pytest\n"
        "def test_offline_unit():\n"
        "    assert 1 + 1 == 2\n"
        "@pytest.mark.live\n"
        "def test_live_check():\n"
        "    import urllib.request\n"
        "    urllib.request.urlopen('https://example.com')\n",
        encoding="utf-8",
    )
    assert check_offline_test_network_discipline(tmp_path, ["tests/test_ok.py"]) == []

    bad_test = tmp_path / "tests" / "test_bad.py"
    bad_test.write_text(
        "import urllib.request\n"
        "def test_hidden_network():\n"
        "    urllib.request.urlopen('https://example.com')\n",
        encoding="utf-8",
    )
    findings = check_offline_test_network_discipline(tmp_path, ["tests/test_bad.py"])
    assert len(findings) == 1
    assert "L-01" in findings[0]


def test_rule_8_docs_links_pass_and_fail(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "target.md").write_text("# Target\n", encoding="utf-8")
    ok_doc = tmp_path / "docs" / "index.md"
    ok_doc.write_text("See [target](target.md) and [ext](https://example.com).\n", encoding="utf-8")
    assert check_docs_links(tmp_path, ["docs/index.md", "docs/target.md"]) == []

    bad_doc = tmp_path / "docs" / "broken.md"
    bad_doc.write_text("See [missing](missing.md).\n", encoding="utf-8")
    findings = check_docs_links(tmp_path, ["docs/broken.md"])
    assert len(findings) == 1
    assert "L-08" in findings[0]


def test_rule_9_docs_reachability_pass_and_fail(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("- [Guide](guide.md)\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    assert check_docs_reachability(tmp_path, ["docs/README.md", "docs/guide.md"]) == []

    (tmp_path / "docs" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
    findings = check_docs_reachability(
        tmp_path,
        ["docs/README.md", "docs/guide.md", "docs/orphan.md"],
    )
    assert len(findings) == 1
    assert "L-08" in findings[0]
    assert "docs/orphan.md" in findings[0]
