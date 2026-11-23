"""Passing and failing tests for scripts/check_secrets.py."""

from __future__ import annotations

from pathlib import Path

from scripts.check_secrets import scan_repository


def test_real_repository_passes_secret_scan():
    assert scan_repository() == []


def test_secret_scan_allows_placeholders_and_flags_real_looking_secrets(tmp_path: Path):
    (tmp_path / ".env.example").write_text(
        "SERPER_API_KEY=your_serper_api_key_here\n"
        "VITE_LOGO_DEV_TOKEN=pk_your_publishable_token_here\n",
        encoding="utf-8",
    )
    assert scan_repository(tmp_path, [".env.example"]) == []

    # Build synthetic secret patterns dynamically so the test file itself stays clean.
    fake_sk = "_".join(["sk", "aBcDeFgH12345678"])
    fake_pk = "_".join(["pk", "zYxWvUtS98765432"])
    fake_aws = "AKIA" + "Z9X8W7V6U5T4S3R2"
    fake_pem = "-----BEGIN " + "PRIVATE KEY-----"
    (tmp_path / "leak.txt").write_text(
        f"token={fake_sk}\npub={fake_pk}\naws={fake_aws}\n{fake_pem}\nSERPER_API_KEY=real_live_serper_key_99\n",
        encoding="utf-8",
    )
    findings = scan_repository(tmp_path, ["leak.txt"])
    assert len(findings) == 5
    assert any("sk_*" in f for f in findings)
    assert any("pk_*" in f for f in findings)
    assert any("AWS access key ID" in f for f in findings)
    assert any("Private key block" in f for f in findings)
    assert any("Non-placeholder credential assignment" in f for f in findings)
