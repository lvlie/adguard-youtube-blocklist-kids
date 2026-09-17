#!/usr/bin/env python3
"""Validate AdGuard Home blocklists that are scoped to a single client.

The whole point of this repository is that the list can never affect a client
other than the one it was written for, so that is what this script checks
hardest: every rule must carry ``$client='<name>'`` and the name must match the
``! Client:`` header of the file.

Usage:
    python3 scripts/validate_blocklist.py [FILE ...]

Exits 0 when every file is valid, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_FILES = ("youtube-kids.txt",)

REQUIRED_HEADERS = (
    "Title",
    "Description",
    "Homepage",
    "License",
    "Version",
    "Last modified",
    "Client",
)

HEADER_RE = re.compile(r"^!\s*(?P<key>[A-Za-z][A-Za-z ]*?)\s*:\s*(?P<value>.+?)\s*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
LAST_MODIFIED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$")
LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

RULE_RE = re.compile(
    r"^(?P<exception>@@)?\|\|"
    r"(?P<domain>[^\^]+)"
    r"\^\$client='(?P<client>(?:[^'\\]|\\.)*)'"
    r"(?P<modifiers>(?:,[a-z_]+)*)$"
)

REQUIRED_MODIFIERS = ("important",)


@dataclass
class Rule:
    """A single parsed filtering rule."""

    lineno: int
    text: str
    domain: str
    client: str
    exception: bool


@dataclass
class Result:
    """Outcome of validating one file."""

    path: Path
    errors: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, lineno: int | None, message: str) -> None:
        where = f"{self.path}:{lineno}" if lineno else str(self.path)
        self.errors.append(f"{where}: {message}")


def is_valid_domain(domain: str) -> bool:
    """Check a plain (non-wildcard) DNS name."""
    if not domain or len(domain) > 253 or domain != domain.lower():
        return False
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    if not all(LABEL_RE.match(label) and len(label) <= 63 for label in labels):
        return False
    tld = labels[-1]
    return len(tld) >= 2 and tld.isalpha()


def parse_headers(lines: list[str], result: Result) -> dict[str, str]:
    """Collect ``! Key: value`` pairs from the comment block at the top."""
    headers: dict[str, str] = {}
    for lineno, line in enumerate(lines, start=1):
        if not line.startswith("!"):
            break
        match = HEADER_RE.match(line)
        if not match:
            continue
        key = match.group("key")
        if key in REQUIRED_HEADERS and key in headers:
            result.error(lineno, f"duplicate header '{key}'")
        headers.setdefault(key, match.group("value"))
    return headers


def check_headers(headers: dict[str, str], result: Result) -> None:
    for key in REQUIRED_HEADERS:
        if key not in headers:
            result.error(None, f"missing '! {key}:' header")

    version = headers.get("Version")
    if version is not None and not VERSION_RE.match(version):
        result.error(None, f"'! Version:' must be MAJOR.MINOR.PATCH, got '{version}'")

    last_modified = headers.get("Last modified")
    if last_modified is not None and not LAST_MODIFIED_RE.match(last_modified):
        result.error(
            None,
            f"'! Last modified:' must be ISO 8601 (2026-09-17T00:00:00Z), got '{last_modified}'",
        )


def check_whitespace(raw: str, lines: list[str], result: Result) -> None:
    if "\r" in raw:
        result.error(None, "file uses CRLF line endings, expected LF")
    if raw and not raw.endswith("\n"):
        result.error(None, "file does not end with a newline")
    if raw.endswith("\n\n"):
        result.error(None, "file ends with a blank line")
    for lineno, line in enumerate(lines, start=1):
        if line != line.rstrip():
            result.error(lineno, "trailing whitespace")
        if "\t" in line:
            result.error(lineno, "tab character, use spaces")


def parse_rules(lines: list[str], expected_client: str | None, result: Result) -> None:
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("!") or stripped.startswith("#"):
            continue

        match = RULE_RE.match(stripped)
        if not match:
            result.error(
                lineno,
                f"not a client-scoped rule: {stripped!r} "
                "(expected ||domain^$client='Name',important)",
            )
            continue

        domain = match.group("domain")
        client = match.group("client")
        modifiers = [m for m in match.group("modifiers").split(",") if m]

        if not is_valid_domain(domain):
            result.error(lineno, f"invalid domain '{domain}'")
        if expected_client is not None and client != expected_client:
            result.error(
                lineno,
                f"rule targets client '{client}' but the file header declares '{expected_client}'",
            )
        for modifier in REQUIRED_MODIFIERS:
            if modifier not in modifiers:
                result.error(lineno, f"rule is missing the '{modifier}' modifier")

        result.rules.append(
            Rule(
                lineno=lineno,
                text=stripped,
                domain=domain,
                client=client,
                exception=bool(match.group("exception")),
            )
        )


def check_rule_set(result: Result) -> None:
    if not result.rules:
        result.error(None, "file contains no rules")
        return

    seen: dict[tuple[bool, str], int] = {}
    for rule in result.rules:
        key = (rule.exception, rule.domain)
        if key in seen:
            result.error(rule.lineno, f"duplicate rule for '{rule.domain}' (first seen on line {seen[key]})")
        else:
            seen[key] = rule.lineno

    blocked = {rule.domain: rule for rule in result.rules if not rule.exception}
    for domain, rule in blocked.items():
        parts = domain.split(".")
        for index in range(1, len(parts) - 1):
            parent = ".".join(parts[index:])
            if parent in blocked:
                result.error(
                    rule.lineno,
                    f"'{domain}' is redundant, '{parent}' on line {blocked[parent].lineno} already covers it",
                )
                break


def validate(path: Path) -> Result:
    result = Result(path=path)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except FileNotFoundError:
        result.error(None, "file not found")
        return result
    except UnicodeDecodeError as exc:
        result.error(None, f"file is not valid UTF-8: {exc}")
        return result

    lines = raw.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()

    check_whitespace(raw, lines, result)
    headers = parse_headers(lines, result)
    check_headers(headers, result)
    parse_rules(lines, headers.get("Client"), result)
    check_rule_set(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", default=list(DEFAULT_FILES), help="blocklist files to validate")
    parser.add_argument("-q", "--quiet", action="store_true", help="only print errors")
    args = parser.parse_args(argv)

    failed = False
    for name in args.files or DEFAULT_FILES:
        result = validate(Path(name))
        for error in result.errors:
            print(error, file=sys.stderr)
        if result.ok:
            if not args.quiet:
                blocked = sum(1 for rule in result.rules if not rule.exception)
                allowed = len(result.rules) - blocked
                clients = sorted({rule.client for rule in result.rules})
                print(
                    f"{result.path}: OK -- {blocked} blocked, {allowed} allowed, "
                    f"client(s): {', '.join(clients)}"
                )
        else:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
