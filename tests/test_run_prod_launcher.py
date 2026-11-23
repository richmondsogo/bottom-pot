"""
Real Windows PowerShell 5.1 regression tests for scripts/run_prod.ps1.

Uses a disposable mock `python.cmd` earlier on PATH that records the child environment
and exits with a configurable code — never launching Uvicorn or opening SQLite.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_PROD_SCRIPT = REPO_ROOT / "scripts" / "run_prod.ps1"


def _require_windows_powershell_51() -> str:
    if sys.platform != "win32":
        pytest.skip("Windows-only PowerShell 5.1 launcher regression test")
    ps_exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if not ps_exe:
        pytest.fail("powershell.exe is required on Windows to verify PowerShell 5.1 compatibility")
    return ps_exe


def _setup_mock_python(tmp_path: Path, *, child_exit_code: int) -> tuple[Path, Path, Path]:
    bin_dir = tmp_path / "mock_bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    record_file = tmp_path / "child_record.json"
    recorder_py = tmp_path / "record_child_env.py"
    recorder_py.write_text(
        "\n".join(
            [
                "import json, os, sys",
                f"out_path = r'{str(record_file)}'",
                "payload = {",
                "    'argv': sys.argv[1:],",
                "    'BOTTOM_POT_ALLOW_OPERATIONAL_DB': os.environ.get('BOTTOM_POT_ALLOW_OPERATIONAL_DB'),",
                "    'has_allow_var': 'BOTTOM_POT_ALLOW_OPERATIONAL_DB' in os.environ,",
                "}",
                "with open(out_path, 'w', encoding='utf-8') as fh:",
                "    json.dump(payload, fh)",
                f"sys.exit({child_exit_code})",
            ]
        ),
        encoding="utf-8",
    )
    (bin_dir / "python.cmd").write_text(
        f'@echo off\r\n"{sys.executable}" "{recorder_py}" %*\r\n',
        encoding="utf-8",
    )
    return bin_dir, record_file, recorder_py


def _invoke_ps51_session(
    ps_exe: str,
    bin_dir: Path,
    *,
    prior_allow_value: str | None,
    extra_env: dict[str, str] | None = None,
    script_args: str = "",
) -> dict:
    # Build an isolated parent PowerShell 5.1 process, verify $PSVersionTable.PSVersion.Major -eq 5,
    # invoke run_prod.ps1 in the SAME PowerShell session scope, and inspect parent env afterward.
    env = os.environ.copy()
    for key in (
        "PYTEST_CURRENT_TEST",
        "PLAYWRIGHT_TEST",
        "PLAYWRIGHT_SQLITE_DB_PATH",
        "PLAYWRIGHT_SUBSCRIPTIONS_FILE",
        "BOTTOM_POT_TEST_MODE",
        "BOTTOM_POT_ALLOW_OPERATIONAL_DB",
        "TESTING",
        "CI",
    ):
        env.pop(key, None)
    if prior_allow_value is not None:
        env["BOTTOM_POT_ALLOW_OPERATIONAL_DB"] = prior_allow_value
    if extra_env:
        env.update(extra_env)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    ps_script = f"""
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSEdition -ne 'Desktop') {{
    throw "Expected Windows PowerShell 5.1 Desktop, got $($PSVersionTable.PSVersion) ($($PSVersionTable.PSEdition))"
}}
& "{RUN_PROD_SCRIPT}" {script_args} 2>&1 | Out-Null
$launcherExit = $LASTEXITCODE
$hadVar = Test-Path Env:BOTTOM_POT_ALLOW_OPERATIONAL_DB
$parentVal = if ($hadVar) {{ $env:BOTTOM_POT_ALLOW_OPERATIONAL_DB }} else {{ $null }}
$out = @{{
    ps_version = $PSVersionTable.PSVersion.ToString()
    ps_edition = $PSVersionTable.PSEdition
    launcher_exit = $launcherExit
    parent_had_var = $hadVar
    parent_value = $parentVal
}}
$out | ConvertTo-Json -Compress
"""
    proc = subprocess.run(
        [ps_exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


@pytest.mark.parametrize(
    ("prior_value", "child_exit_code"),
    [
        (None, 0),
        ("0", 0),
        ("1", 0),
        (None, 42),
        ("0", 7),
        ("1", 3),
    ],
)
def test_run_prod_ps1_scopes_and_restores_operational_env_in_powershell_51(
    tmp_path: Path,
    prior_value: str | None,
    child_exit_code: int,
):
    ps_exe = _require_windows_powershell_51()
    bin_dir, record_file, _ = _setup_mock_python(tmp_path, child_exit_code=child_exit_code)

    session = _invoke_ps51_session(
        ps_exe,
        bin_dir,
        prior_allow_value=prior_value,
        script_args="-HostAddress 127.0.0.1 -Port 8123",
    )

    assert session["ps_version"].startswith("5.1")
    assert session["ps_edition"] == "Desktop"
    assert session["launcher_exit"] == child_exit_code

    # Parent session must match exact prior state (no leakage on success OR failure)
    if prior_value is None:
        assert session["parent_had_var"] is False
        assert session["parent_value"] is None
    else:
        assert session["parent_had_var"] is True
        assert session["parent_value"] == prior_value

    # Child python.cmd must have observed BOTTOM_POT_ALLOW_OPERATIONAL_DB=1 and exact uvicorn CLI args
    assert record_file.exists(), "Expected mock python.cmd child to have executed"
    child = json.loads(record_file.read_text(encoding="utf-8"))
    assert child["has_allow_var"] is True
    assert child["BOTTOM_POT_ALLOW_OPERATIONAL_DB"] == "1"
    assert child["argv"] == ["-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "8123"]


@pytest.mark.parametrize(
    ("marker_name", "marker_value"),
    [
        ("BOTTOM_POT_TEST_MODE", "1"),
        ("BOTTOM_POT_TEST_MODE", "0"),
        ("PYTEST_CURRENT_TEST", "tests/test_fake.py::test_x"),
        ("PYTEST_CURRENT_TEST", "0"),
        ("PLAYWRIGHT_TEST", "0"),
        ("PLAYWRIGHT_SQLITE_DB_PATH", "/tmp/pw.sqlite"),
        ("TESTING", "true"),
        ("CI", "1"),
    ],
)
def test_run_prod_ps1_rejects_test_markers_before_launching_child_and_leaves_parent_clean(
    tmp_path: Path,
    marker_name: str,
    marker_value: str,
):
    ps_exe = _require_windows_powershell_51()
    bin_dir, record_file, _ = _setup_mock_python(tmp_path, child_exit_code=0)

    session = _invoke_ps51_session(
        ps_exe,
        bin_dir,
        prior_allow_value=None,
        extra_env={marker_name: marker_value},
    )

    assert session["ps_version"].startswith("5.1")
    assert session["launcher_exit"] != 0
    assert session["parent_had_var"] is False
    assert session["parent_value"] is None
    assert not record_file.exists(), "run_prod.ps1 must reject test markers BEFORE spawning python"
