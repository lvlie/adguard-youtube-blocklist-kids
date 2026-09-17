"""Tests for scripts/check_ha_package.py and for the shipped Home Assistant package."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

yaml = pytest.importorskip("yaml")
pytest.importorskip("jinja2")

import check_ha_package as chp  # noqa: E402

PACKAGE = REPO_ROOT / "homeassistant" / "packages" / "adguard_youtube_kids.yaml"
BLOCKLIST_URL = "https://raw.githubusercontent.com/lvlie/adguard-youtube-blocklist-kids/main/youtube-kids.txt"


@pytest.fixture(scope="module")
def package() -> dict:
    return yaml.load(PACKAGE.read_text(encoding="utf-8"), Loader=chp.HomeAssistantLoader)


# --- the package that ships in this repository -------------------------------


def test_shipped_package_passes_every_check() -> None:
    assert chp.check_package(PACKAGE) == []


def test_package_keeps_credentials_in_secrets(package: dict) -> None:
    rendered = PACKAGE.read_text(encoding="utf-8")
    assert "!secret adguard_username" in rendered
    assert "!secret adguard_password" in rendered
    assert package["rest_command"]["adguard_youtube_kids_filter_set"]["password"] == "<!secret>"


def test_package_url_matches_the_readme(package: dict) -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert BLOCKLIST_URL in readme
    assert BLOCKLIST_URL in PACKAGE.read_text(encoding="utf-8")


def test_secrets_example_covers_every_secret_the_package_uses() -> None:
    used = {
        line.split("!secret", 1)[1].strip()
        for line in PACKAGE.read_text(encoding="utf-8").splitlines()
        if "!secret" in line
    }
    example = yaml.safe_load((REPO_ROOT / "homeassistant" / "secrets.example.yaml").read_text(encoding="utf-8"))
    assert used <= set(example)


# --- the checks themselves ----------------------------------------------------


def write(tmp_path: Path, package: dict) -> Path:
    path = tmp_path / "package.yaml"
    path.write_text(yaml.safe_dump(package), encoding="utf-8")
    return path


def test_reports_a_missing_file(tmp_path: Path) -> None:
    assert chp.check_package(tmp_path / "nope.yaml") == [f"{tmp_path / 'nope.yaml'}: file not found"]


def test_reports_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "package.yaml"
    path.write_text("rest_command: [unclosed\n", encoding="utf-8")
    assert any("invalid YAML" in error for error in chp.check_package(path))


def test_reports_an_empty_package(tmp_path: Path) -> None:
    path = tmp_path / "package.yaml"
    path.write_text("[]\n", encoding="utf-8")
    assert any("mapping at the top level" in error for error in chp.check_package(path))


def test_reports_a_switch_that_sends_the_wrong_boolean(tmp_path: Path, package: dict) -> None:
    broken = yaml.safe_load(yaml.safe_dump(package))
    broken["template"][0]["switch"][0]["turn_off"][0]["data"]["enabled"] = True
    assert any("turn_off sends enabled=True" in error for error in chp.check_package(write(tmp_path, broken)))


def test_reports_the_deprecated_service_key(tmp_path: Path, package: dict) -> None:
    broken = yaml.safe_load(yaml.safe_dump(package))
    step = broken["template"][0]["switch"][0]["turn_on"][0]
    step["service"] = step.pop("action")
    assert any("deprecated 'service:'" in error for error in chp.check_package(write(tmp_path, broken)))


def test_reports_a_payload_with_a_python_boolean(tmp_path: Path, package: dict) -> None:
    broken = yaml.safe_load(yaml.safe_dump(package))
    command = broken["rest_command"]["adguard_youtube_kids_filter_set"]
    command["payload"] = command["payload"].replace("{{ 'true' if enabled else 'false' }}", "{{ enabled }}")
    assert any("not valid JSON" in error for error in chp.check_package(write(tmp_path, broken)))


def test_reports_a_missing_rest_command(tmp_path: Path, package: dict) -> None:
    broken = yaml.safe_load(yaml.safe_dump(package))
    del broken["rest_command"]["adguard_filters_refresh"]
    assert any("adguard_filters_refresh is missing" in error for error in chp.check_package(write(tmp_path, broken)))


def test_reports_a_sensor_without_a_unique_id(tmp_path: Path, package: dict) -> None:
    broken = yaml.safe_load(yaml.safe_dump(package))
    del broken["rest"][0]["sensor"][0]["unique_id"]
    assert any("unique_id" in error for error in chp.check_package(write(tmp_path, broken)))


def test_cli_returns_zero_for_the_shipped_package(capsys: pytest.CaptureFixture[str]) -> None:
    assert chp.main([str(PACKAGE)]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_returns_one_for_a_broken_package(tmp_path: Path) -> None:
    path = tmp_path / "package.yaml"
    path.write_text("rest_command: {}\n", encoding="utf-8")
    assert chp.main([str(path)]) == 1
