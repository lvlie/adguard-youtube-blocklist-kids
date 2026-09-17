"""Tests for the AdGuard-integration package and the dashboard section.

These two files have to agree with each other: the dashboard buttons call
scripts by entity_id, and the cards read entities by entity_id. Nothing
validates that at runtime -- a rename just produces a dead button -- so it is
pinned here instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = REPO_ROOT / "homeassistant" / "packages" / "youtube_kids_native.yaml"
DASHBOARD = REPO_ROOT / "homeassistant" / "dashboard" / "admin-adguard-section.yaml"
BLOCKLIST_URL = "https://raw.githubusercontent.com/lvlie/adguard-youtube-blocklist-kids/main/youtube-kids.txt"

TOGGLE = "input_boolean.youtube_blocked_for_kids"
ALLOWANCE = "timer.youtube_allowance_kids"


@pytest.fixture(scope="module")
def package() -> dict:
    return yaml.safe_load(PACKAGE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dashboard() -> dict:
    return yaml.safe_load(DASHBOARD.read_text(encoding="utf-8"))


# --- the package --------------------------------------------------------------


def test_package_defines_the_expected_objects(package: dict) -> None:
    assert set(package) == {"input_boolean", "timer", "script", "automation"}
    assert "youtube_blocked_for_kids" in package["input_boolean"]
    assert "youtube_allowance_kids" in package["timer"]
    assert set(package["script"]) == {
        "youtube_kids_allow",
        "youtube_kids_block",
        "youtube_kids_extend_30",
    }


def test_allowance_timer_survives_a_restart(package: dict) -> None:
    assert package["timer"]["youtube_allowance_kids"]["restore"] is True


def test_every_automation_has_a_stable_id(package: dict) -> None:
    # Without an id an automation cannot be edited in the UI.
    assert all(automation.get("id") for automation in package["automation"])


def test_the_adguard_calls_use_the_blocklist_url(package: dict) -> None:
    sync = next(a for a in package["automation"] if a["id"] == "kids_sync_youtube_blocklist_to_adguard")
    calls = {
        branch["sequence"][0]["action"]: branch["sequence"][0]["data"]["url"]
        for branch in sync["actions"][0]["choose"]
    }
    assert calls == {"adguard.enable_url": BLOCKLIST_URL, "adguard.disable_url": BLOCKLIST_URL}


def test_allow_and_block_cancel_a_running_allowance(package: dict) -> None:
    # Otherwise a leftover timer would silently re-block later.
    for script_id in ("youtube_kids_allow", "youtube_kids_block"):
        actions = [step.get("action") for step in package["script"][script_id]["sequence"]]
        assert "timer.cancel" in actions, script_id


def _actions(steps: list) -> set[str]:
    """Every action called by a sequence, including inside choose branches."""
    found: set[str] = set()
    for step in steps:
        if "action" in step:
            found.add(step["action"])
        for branch in step.get("choose", []):
            found |= _actions(branch["sequence"])
        found |= _actions(step.get("default", []))
    return found


def test_extend_never_uses_timer_change(package: dict) -> None:
    # timer.change refuses to extend a timer beyond its configured duration,
    # which is exactly what the second press of +30 needs to do. Checked on the
    # parsed actions, not the raw text, which also mentions it in a comment.
    called = _actions(package["script"]["youtube_kids_extend_30"]["sequence"])
    assert "timer.change" not in called
    assert "timer.start" in called


def test_extend_derives_remaining_from_finishes_at(package: dict) -> None:
    # The `remaining` attribute is only refreshed on state transitions, so it
    # reads stale while the timer counts down.
    running = package["script"]["youtube_kids_extend_30"]["sequence"][1]["choose"][0]
    duration = running["sequence"][0]["data"]["duration"]
    assert "finishes_at" in duration
    assert "1800" in duration


def test_extend_is_queued_so_fast_presses_all_count(package: dict) -> None:
    assert package["script"]["youtube_kids_extend_30"]["mode"] == "queued"


def test_reblock_triggers_only_on_timer_finished(package: dict) -> None:
    # timer.cancel raises timer.cancelled, so Allow/Block must not re-block.
    reblock = next(a for a in package["automation"] if a["id"] == "kids_block_youtube_when_allowance_finishes")
    trigger = reblock["triggers"][0]
    assert trigger["event_type"] == "timer.finished"
    assert trigger["event_data"]["entity_id"] == ALLOWANCE


# --- the dashboard ------------------------------------------------------------


def _buttons(dashboard: dict) -> list[dict]:
    grid = next(card for card in dashboard["cards"] if card["type"] == "grid")
    return grid["cards"]


def test_dashboard_buttons_call_scripts_that_exist(dashboard: dict, package: dict) -> None:
    called = {button["tap_action"]["perform_action"] for button in _buttons(dashboard)}
    defined = {f"script.{name}" for name in package["script"]}
    assert called == defined


def test_dashboard_buttons_use_the_current_action_syntax(dashboard: dict) -> None:
    # `call-service` and `service:` were renamed in 2024.8.
    for button in _buttons(dashboard):
        assert button["tap_action"]["action"] == "perform-action"
        assert "service" not in button["tap_action"]


def test_dashboard_reads_entities_the_package_defines(dashboard: dict) -> None:
    markdown = next(card for card in dashboard["cards"] if card["type"] == "markdown")
    assert set(markdown["entity_id"]) == {TOGGLE, ALLOWANCE}
    assert TOGGLE in markdown["content"]
    assert ALLOWANCE in markdown["content"]


def test_timer_card_is_hidden_while_idle(dashboard: dict) -> None:
    conditional = next(card for card in dashboard["cards"] if card["type"] == "conditional")
    condition = conditional["conditions"][0]
    assert condition["entity"] == ALLOWANCE
    assert condition["state_not"] == "idle"
    assert conditional["card"]["entity"] == ALLOWANCE


def test_dashboard_starts_with_a_heading(dashboard: dict) -> None:
    # Section `title` is deprecated in favour of a leading heading card.
    assert dashboard["cards"][0]["type"] == "heading"
