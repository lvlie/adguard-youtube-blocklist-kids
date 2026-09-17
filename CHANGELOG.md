# Changelog

All notable changes to the blocklist are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the list version follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **major** — a change that can break an existing setup, such as a different client name
- **minor** — domains added or removed
- **patch** — comments, metadata and fixes that do not change what is blocked

## [Unreleased]

## [1.0.0] - 2026-09-17

### Added

- Initial blocklist: 20 rules scoped to the AdGuard Home client `Kids`, covering the YouTube web
  properties, YouTube Kids, the app/TV API endpoints, thumbnail CDNs and the common country aliases.
- Home Assistant package with a `switch.youtube_blocked_for_kids` template switch, a REST sensor that
  mirrors the state of the list in AdGuard Home, and REST commands to toggle and refresh it.
- `scripts/validate_blocklist.py` plus a test suite, a pre-commit configuration and a CI workflow.

[Unreleased]: https://github.com/lvlie/adguard-youtube-blocklist-kids/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/lvlie/adguard-youtube-blocklist-kids/releases/tag/v1.0.0
