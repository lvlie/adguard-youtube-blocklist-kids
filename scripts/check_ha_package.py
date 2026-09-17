#!/usr/bin/env python3
"""Sanity-check the Home Assistant package shipped in this repository.

Home Assistant only reports a broken package when it starts up, which is a slow
way to find a typo. This script does the cheap half of that check offline:

* the YAML parses, including Home Assistant's custom tags (``!secret`` etc.)
* the entities this repository documents are actually defined
* the Jinja templates render, and render the *right* values for known AdGuard
  Home API responses
* the payload sent to AdGuard Home is valid JSON with a real boolean

Usage:
    python3 scripts/check_ha_package.py [FILE ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import jinja2
    import yaml
except ImportError as exc:  # pragma: no cover - depends on the environment
    print(f"missing dependency: {exc.name} (pip install -r requirements-dev.txt)", file=sys.stderr)
    raise SystemExit(2) from exc

DEFAULT_FILES = ("homeassistant/packages/adguard_youtube_kids.yaml",)

REQUIRED_REST_COMMANDS = ("adguard_youtube_kids_filter_set", "adguard_filters_refresh")
REQUIRED_SENSOR = "AdGuard YouTube Kids filter"
REQUIRED_SWITCH = "YouTube blocked for Kids"

# Home Assistant deprecated `service:` in favour of `action:` in 2024.8.
FORBIDDEN_ACTION_KEYS = ("service",)


class HomeAssistantLoader(yaml.SafeLoader):
    """A SafeLoader that tolerates Home Assistant's custom YAML tags."""


def _opaque_tag(loader: yaml.Loader, node: yaml.Node) -> str:
    return f"<{node.tag}>"


for tag in ("!secret", "!include", "!include_dir_named", "!include_dir_list", "!env_var"):
    HomeAssistantLoader.add_constructor(tag, _opaque_tag)


def render(template: str, **context: Any) -> str:
    """Render like Home Assistant does: Jinja, then strip."""
    return jinja2.Environment(undefined=jinja2.Undefined).from_string(template).render(**context).strip()


def check_rest_commands(package: dict[str, Any], errors: list[str]) -> None:
    commands = package.get("rest_command") or {}
    for name in REQUIRED_REST_COMMANDS:
        if name not in commands:
            errors.append(f"rest_command.{name} is missing")

    command = commands.get(REQUIRED_REST_COMMANDS[0])
    if not command:
        return

    if str(command.get("method", "")).lower() != "post":
        errors.append(f"rest_command.{REQUIRED_REST_COMMANDS[0]} must use method: post")
    if "set_url" not in str(command.get("url", "")):
        errors.append("the toggle command must post to /control/filtering/set_url")

    payload = command.get("payload", "")
    for enabled in (True, False):
        rendered = render(payload, enabled=enabled)
        try:
            body = json.loads(rendered)
        except json.JSONDecodeError as exc:
            errors.append(f"payload is not valid JSON for enabled={enabled}: {exc}")
            continue
        if body.get("data", {}).get("enabled") is not enabled:
            errors.append(
                f"payload for enabled={enabled} sends data.enabled="
                f"{body.get('data', {}).get('enabled')!r}, expected a JSON boolean"
            )
        if body.get("url") != body.get("data", {}).get("url"):
            errors.append("payload url and data.url must be identical")


def check_sensor(package: dict[str, Any], errors: list[str]) -> str | None:
    """Verify the REST sensor and return the blocklist URL it matches on."""
    sensors = [sensor for entry in package.get("rest") or [] for sensor in entry.get("sensor") or []]
    sensor = next((s for s in sensors if s.get("name") == REQUIRED_SENSOR), None)
    if sensor is None:
        errors.append(f"REST sensor {REQUIRED_SENSOR!r} is missing")
        return None

    if not sensor.get("unique_id"):
        errors.append(f"REST sensor {REQUIRED_SENSOR!r} needs a unique_id so it can be renamed in the UI")

    resources = [str(entry.get("resource", "")) for entry in package.get("rest") or []]
    if not any("filtering/status" in resource for resource in resources):
        errors.append("the REST sensor must read /control/filtering/status")

    template = sensor.get("value_template", "")
    url = next((line.split("'")[1] for line in template.splitlines() if "set url = " in line), None)
    if url is None:
        errors.append("could not find the blocklist URL in the sensor's value_template")
        return None

    cases = [
        ({"filters": [{"url": url, "enabled": True}]}, "on"),
        ({"filters": [{"url": url, "enabled": False}]}, "off"),
        ({"filters": [{"url": "https://example.org/other.txt", "enabled": True}]}, "unknown"),
        ({"filters": None}, "unknown"),
        ({}, "unknown"),
    ]
    for payload, expected in cases:
        actual = render(template, value_json=payload)
        if actual != expected:
            errors.append(f"value_template rendered {actual!r} for {payload!r}, expected {expected!r}")

    return url


def check_switch(package: dict[str, Any], errors: list[str]) -> None:
    switches = [switch for entry in package.get("template") or [] for switch in entry.get("switch") or []]
    switch = next((s for s in switches if s.get("name") == REQUIRED_SWITCH), None)
    if switch is None:
        errors.append(f"template switch {REQUIRED_SWITCH!r} is missing")
        return

    if not switch.get("unique_id"):
        errors.append(f"template switch {REQUIRED_SWITCH!r} needs a unique_id")

    for key in ("state", "turn_on", "turn_off"):
        if key not in switch:
            errors.append(f"template switch is missing '{key}'")

    for direction, expected in (("turn_on", True), ("turn_off", False)):
        steps = switch.get(direction) or []

        # Check this first: a step still using `service:` has no `action:` to
        # match on below, and "must call rest_command..." would hide the cause.
        for step in steps:
            for forbidden in FORBIDDEN_ACTION_KEYS:
                if forbidden in step:
                    errors.append(f"{direction} uses the deprecated '{forbidden}:' key, use 'action:'")

        calls = [step for step in steps if step.get("action") == f"rest_command.{REQUIRED_REST_COMMANDS[0]}"]
        if not calls:
            errors.append(f"{direction} must call rest_command.{REQUIRED_REST_COMMANDS[0]}")
            continue

        sent = calls[0].get("data", {}).get("enabled")
        if sent is not expected:
            errors.append(f"{direction} sends enabled={sent!r}, expected {expected}")
        if not any(step.get("action") == "homeassistant.update_entity" for step in steps):
            errors.append(f"{direction} should refresh the sensor with homeassistant.update_entity")


def check_package(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        package = yaml.load(path.read_text(encoding="utf-8"), Loader=HomeAssistantLoader)
    except FileNotFoundError:
        return [f"{path}: file not found"]
    except yaml.YAMLError as exc:
        return [f"{path}: invalid YAML: {exc}"]

    if not isinstance(package, dict):
        return [f"{path}: expected a mapping at the top level"]

    check_rest_commands(package, errors)
    check_sensor(package, errors)
    check_switch(package, errors)
    return [f"{path}: {error}" for error in errors]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", default=list(DEFAULT_FILES), help="package files to check")
    args = parser.parse_args(argv)

    failed = False
    for name in args.files or DEFAULT_FILES:
        path = Path(name)
        errors = check_package(path)
        for error in errors:
            print(error, file=sys.stderr)
        if errors:
            failed = True
        else:
            print(f"{path}: OK")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
