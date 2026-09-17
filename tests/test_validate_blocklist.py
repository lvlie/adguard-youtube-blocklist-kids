"""Tests for scripts/validate_blocklist.py and for the shipped blocklist."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import validate_blocklist as vb  # noqa: E402

BLOCKLIST = REPO_ROOT / "youtube-kids.txt"

VALID_HEADER = """\
! Title: Example
! Description: Example list
! Homepage: https://example.org
! License: https://example.org/LICENSE
! Version: 1.0.0
! Last modified: 2026-09-17T00:00:00Z
! Client: Kids
"""


def write(tmp_path: Path, body: str, header: str = VALID_HEADER) -> Path:
    path = tmp_path / "list.txt"
    path.write_text(header + body, encoding="utf-8")
    return path


def errors(tmp_path: Path, body: str, header: str = VALID_HEADER) -> list[str]:
    return vb.validate(write(tmp_path, body, header)).errors


# --- the list that ships in this repository ---------------------------------


def test_shipped_blocklist_is_valid() -> None:
    result = vb.validate(BLOCKLIST)
    assert result.errors == []


def test_shipped_blocklist_targets_only_the_kids_client() -> None:
    result = vb.validate(BLOCKLIST)
    assert result.rules, "expected at least one rule"
    assert {rule.client for rule in result.rules} == {"Kids"}


@pytest.mark.parametrize(
    "domain",
    ["youtube.com", "youtu.be", "youtubekids.com", "youtubei.googleapis.com", "ytimg.com"],
)
def test_shipped_blocklist_covers_core_domains(domain: str) -> None:
    result = vb.validate(BLOCKLIST)
    assert domain in {rule.domain for rule in result.rules if not rule.exception}


def test_shipped_blocklist_has_no_allowlist_rules() -> None:
    # This list blocks YouTube Kids too; an exception rule would be a regression.
    result = vb.validate(BLOCKLIST)
    assert [rule.text for rule in result.rules if rule.exception] == []


# --- rule parsing ------------------------------------------------------------


def test_accepts_a_well_formed_rule(tmp_path: Path) -> None:
    assert errors(tmp_path, "||example.org^$client='Kids',important\n") == []


def test_accepts_an_exception_rule(tmp_path: Path) -> None:
    body = "||example.org^$client='Kids',important\n@@||ok.example.org^$client='Kids',important\n"
    assert errors(tmp_path, body) == []


def test_rejects_a_rule_without_a_client(tmp_path: Path) -> None:
    found = errors(tmp_path, "||example.org^\n")
    assert any("not a client-scoped rule" in error for error in found)


def test_rejects_a_rule_for_another_client(tmp_path: Path) -> None:
    found = errors(tmp_path, "||example.org^$client='Guests',important\n")
    assert any("targets client 'Guests'" in error for error in found)


def test_rejects_a_rule_without_important(tmp_path: Path) -> None:
    found = errors(tmp_path, "||example.org^$client='Kids'\n")
    assert any("missing the 'important' modifier" in error for error in found)


def test_rejects_a_plain_hosts_entry(tmp_path: Path) -> None:
    found = errors(tmp_path, "0.0.0.0 youtube.com\n")
    assert any("not a client-scoped rule" in error for error in found)


@pytest.mark.parametrize("domain", ["Example.org", "example", "-example.org", "example.org.", "example.1"])
def test_rejects_invalid_domains(tmp_path: Path, domain: str) -> None:
    found = errors(tmp_path, f"||{domain}^$client='Kids',important\n")
    assert found, f"expected {domain!r} to be rejected"


def test_rejects_duplicate_rules(tmp_path: Path) -> None:
    body = "||example.org^$client='Kids',important\n||example.org^$client='Kids',important\n"
    found = errors(tmp_path, body)
    assert any("duplicate rule" in error for error in found)


def test_rejects_a_redundant_subdomain(tmp_path: Path) -> None:
    body = "||example.org^$client='Kids',important\n||www.example.org^$client='Kids',important\n"
    found = errors(tmp_path, body)
    assert any("redundant" in error for error in found)


def test_allows_a_subdomain_without_its_parent(tmp_path: Path) -> None:
    assert errors(tmp_path, "||youtubei.googleapis.com^$client='Kids',important\n") == []


def test_rejects_an_empty_rule_set(tmp_path: Path) -> None:
    found = errors(tmp_path, "")
    assert any("no rules" in error for error in found)


# --- headers -----------------------------------------------------------------


def test_rejects_a_missing_header(tmp_path: Path) -> None:
    header = VALID_HEADER.replace("! Client: Kids\n", "")
    found = errors(tmp_path, "||example.org^$client='Kids',important\n", header)
    assert any("missing '! Client:' header" in error for error in found)


def test_rejects_a_bad_version(tmp_path: Path) -> None:
    header = VALID_HEADER.replace("! Version: 1.0.0", "! Version: v1")
    found = errors(tmp_path, "||example.org^$client='Kids',important\n", header)
    assert any("Version" in error for error in found)


def test_rejects_a_bad_last_modified(tmp_path: Path) -> None:
    header = VALID_HEADER.replace("! Last modified: 2026-09-17T00:00:00Z", "! Last modified: yesterday")
    found = errors(tmp_path, "||example.org^$client='Kids',important\n", header)
    assert any("Last modified" in error for error in found)


# --- whitespace ---------------------------------------------------------------


def test_rejects_trailing_whitespace(tmp_path: Path) -> None:
    found = errors(tmp_path, "||example.org^$client='Kids',important  \n")
    assert any("trailing whitespace" in error for error in found)


def test_rejects_crlf(tmp_path: Path) -> None:
    path = tmp_path / "list.txt"
    path.write_bytes((VALID_HEADER + "||example.org^$client='Kids',important\n").replace("\n", "\r\n").encode())
    found = vb.validate(path).errors
    assert any("CRLF" in error for error in found)


def test_rejects_a_missing_final_newline(tmp_path: Path) -> None:
    found = errors(tmp_path, "||example.org^$client='Kids',important")
    assert any("newline" in error for error in found)


# --- cli ----------------------------------------------------------------------


def test_cli_returns_zero_for_the_shipped_list(capsys: pytest.CaptureFixture[str]) -> None:
    assert vb.main([str(BLOCKLIST)]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_returns_one_for_a_broken_list(tmp_path: Path) -> None:
    assert vb.main([str(write(tmp_path, "||example.org^\n"))]) == 1


def test_cli_reports_a_missing_file(tmp_path: Path) -> None:
    assert vb.main([str(tmp_path / "nope.txt")]) == 1
