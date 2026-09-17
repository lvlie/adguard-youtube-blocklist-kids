# Changelog

All notable changes to the blocklist are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the list version follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **major** — a change that can break an existing setup, such as a different client name
- **minor** — domains added or removed
- **patch** — comments, metadata and fixes that do not change what is blocked

## [Unreleased]

### Added

- `homeassistant/packages/youtube_kids_native.yaml` — control the blocklist through the AdGuard Home
  integration's `adguard.enable_url` / `adguard.disable_url` services. No credentials, and it fans out to
  every loaded AdGuard config entry, so a primary/replica pair stays in step. Adds a timed allowance:
  `+30 minutes`, pressed again for 60, with an automatic re-block when the timer finishes.
- `homeassistant/dashboard/admin-adguard-section.yaml` — dashboard section with a plain-language status
  line, the allowance timer (only while running), and Allow / +30 min / Block buttons.
- Tests pinning the package and the dashboard to each other, so a renamed script cannot leave a dead button.

### Changed

- The README now leads with the AdGuard integration; the `rest_command` package stays documented as the
  fallback for setups without the integration, or that want the list's real state read back.

### Fixed

- Corrected the claim that the AdGuard Home integration cannot toggle an individual filter list. It has no
  switch entity for one, but `adguard.enable_url` / `adguard.disable_url` do exactly that.

## [1.0.0] - 2026-09-17

### Added

- Initial blocklist: 20 rules scoped to the AdGuard Home client `Kids`, covering the YouTube web
  properties, YouTube Kids, the app/TV API endpoints, thumbnail CDNs and the common country aliases.
- Home Assistant package with a `switch.youtube_blocked_for_kids` template switch, a REST sensor that
  mirrors the state of the list in AdGuard Home, and REST commands to toggle and refresh it.
- `scripts/validate_blocklist.py` plus a test suite, a pre-commit configuration and a CI workflow.

[Unreleased]: https://github.com/lvlie/adguard-youtube-blocklist-kids/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/lvlie/adguard-youtube-blocklist-kids/releases/tag/v1.0.0
