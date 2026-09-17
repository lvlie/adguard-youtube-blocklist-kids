<!-- markdownlint-disable-file MD041 -->
## What does this change?

<!-- One or two sentences. Link an issue with "Fixes #123" if there is one. -->

## Type of change

- [ ] Blocklist rules (domains added or removed)
- [ ] Home Assistant package
- [ ] Documentation
- [ ] Tooling / CI

## Checklist

- [ ] Every rule still carries `$client='Kids'` and `important`
- [ ] `! Version:` and `! Last modified:` bumped in `youtube-kids.txt` (rule changes only)
- [ ] `CHANGELOG.md` updated (rule changes only)
- [ ] `python3 scripts/validate_blocklist.py` passes
- [ ] `pytest -q` passes
- [ ] `pre-commit run --all-files` passes

## Tested on

<!-- e.g. AdGuard Home v0.107.x, Home Assistant 2026.9 -- or "documentation only". -->
