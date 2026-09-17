# Contributing

Thanks for helping out. This repository is small on purpose: one blocklist, one Home Assistant package,
and enough tooling to stop a broken list from ever reaching a device.

## Ground rules for the blocklist

- **Every rule is client-scoped.** A rule without `$client='Kids'` would apply to the whole network.
  CI rejects it, and so should a reviewer.
- **Keep `important` on every rule.** It is what stops an allowlist rule in another list from
  quietly re-enabling YouTube.
- **Domain-level only.** No `googlevideo.com` or other shared Google CDNs — they break unrelated
  services for the Kids client. If you think a shared domain is worth the trade-off, open an issue first.
- **No redundant subdomains.** `||youtube.com^` already covers `music.youtube.com`; the validator
  flags the extra rule.
- **Bump the header.** Update `! Version:` and `! Last modified:` in `youtube-kids.txt` and add a
  `CHANGELOG.md` entry with every rule change.

## Setting up

```bash
pip install -r requirements-dev.txt
pre-commit install --hook-type pre-commit --hook-type pre-push
```

The pre-commit hook lints Markdown and YAML and validates the blocklist; the pre-push hook runs the tests.

## Before you open a pull request

```bash
python3 scripts/validate_blocklist.py
pytest -q
pre-commit run --all-files
```

If you add a rule, add or adjust a test in `tests/test_validate_blocklist.py` so the behaviour is pinned.

## Changing the Home Assistant package

Validate it in Home Assistant with **Developer tools → YAML → Check configuration** before submitting, and
mention which Home Assistant version you tested on. Use the current action syntax (`action:`, `triggers:`,
`conditions:`, `actions:`) and keep credentials in `secrets.yaml` — never in the package.

## Reporting a domain that slips through

Open an issue with the domain, the device or app it came from, and the relevant line from the AdGuard Home
**Query log** (it shows the client and the rule that matched, or that nothing did).
