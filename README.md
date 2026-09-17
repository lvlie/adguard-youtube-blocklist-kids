# AdGuard YouTube blocklist — "Kids" client

[![CI](https://github.com/lvlie/adguard-youtube-blocklist-kids/actions/workflows/ci.yml/badge.svg)](https://github.com/lvlie/adguard-youtube-blocklist-kids/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An [AdGuard Home](https://github.com/AdguardTeam/AdGuardHome) blocklist that blocks YouTube **for one client only** —
the client you named `Kids` — and leaves every other device on the network untouched. It also documents how to flip
the list on and off from Home Assistant, so "no YouTube after dinner" becomes a button, a timed allowance, an
automation or a voice command.

```text
||youtube.com^$client='Kids',important
```

## Contents

- [How it works](#how-it-works)
- [What gets blocked](#what-gets-blocked)
- [Setup in AdGuard Home](#setup-in-adguard-home)
- [Toggling the list from Home Assistant](#toggling-the-list-from-home-assistant)
- [Verifying and troubleshooting](#verifying-and-troubleshooting)
- [Using a different client name](#using-a-different-client-name)
- [Repository layout](#repository-layout)
- [Development](#development)

## How it works

AdGuard Home filter lists are **global**: a list is either enabled or disabled for the whole server, and there is no
per-client "subscribe to this list" setting. Per-client filtering is expressed *inside the rules* instead, using the
[`$client` modifier](https://github.com/AdguardTeam/AdGuardHome/wiki/Clients):

| Part | Meaning |
| --- | --- |
| `\|\|youtube.com^` | Block `youtube.com` and every subdomain |
| `$client='Kids'` | …but only for the persistent client named exactly `Kids` |
| `important` | …and let this rule win over allowlist rules in other lists |

Because every rule in [`youtube-kids.txt`](youtube-kids.txt) is scoped this way, enabling the list globally is safe:
the rules simply never match anyone else. A CI check enforces that — a rule without `$client='Kids'` fails the build.

> [!IMPORTANT]
> `$client` matches by **name** only for *persistent* clients, i.e. clients you added manually under
> **Settings → Client settings**. A device that AdGuard Home merely discovered ("runtime client") has no name to
> match, so the rules will not apply to it. Creating that client is step 1 below.

## What gets blocked

This list is deliberately **domain-level**: it blocks YouTube's own domains, not the `googlevideo.com` CDN. That
keeps the blast radius small — nothing else Google-related breaks for the Kids client — while still stopping the
site and the apps from loading.

| Group | Domains |
| --- | --- |
| Web and apps | `youtube.com`, `youtu.be`, `yt.be`, `youtube-nocookie.com`, `youtubekids.com`, `youtubeeducation.com` |
| App / TV API endpoints | `youtubei.googleapis.com`, `youtube.googleapis.com`, `youtubeembeddedplayer.googleapis.com` |
| Thumbnails and avatars | `ytimg.com`, `yt3.ggpht.com`, `yt4.ggpht.com` |
| Country aliases | `youtube.nl`, `youtube.be`, `youtube.de`, `youtube.fr`, `youtube.co.uk`, `youtube.ie`, `youtube.es`, `youtube.it` |

Notes:

- **YouTube Kids is blocked too** (`youtubekids.com`, and `kids.youtube.com` via the `youtube.com` rule). If you want
  to keep it available, add an exception rule — see [Using a different client name](#using-a-different-client-name)
  for where to edit.
- Subdomains are covered automatically, so `m.`, `music.`, `tv.` and `studio.youtube.com` need no separate rules.
- Videos **embedded** on other sites keep their player shell but will not load, because the embed calls
  `youtube.com` / `youtube-nocookie.com`.

## Setup in AdGuard Home

### 1. Create the persistent client

**Settings → Client settings → Add client**:

- **Name**: `Kids` (exact, case-sensitive — this is what `$client='Kids'` matches)
- **Identifier**: the device's IP address, MAC address, ClientID or CIDR range. Use a MAC address or a DHCP
  reservation so it survives a reboot.

Add every device that belongs to the kids as an identifier of this one client — a client can have several.

### 2. Add the blocklist

**Filters → DNS blocklists → Add blocklist → Add a custom list**:

- **Name**: `YouTube blocklist for Kids`
- **URL**:

  ```text
  https://raw.githubusercontent.com/lvlie/adguard-youtube-blocklist-kids/main/youtube-kids.txt
  ```

AdGuard Home should report ~20 rules. Keep the name and URL exactly as above if you plan to use the Home Assistant
package unchanged — it matches the list by its URL.

### 3. Check it

From a device that belongs to the `Kids` client, open <https://www.youtube.com>. It should fail to resolve. From any
other device it should still work. **Query log** shows the matching rule and the client name for each request.

## Toggling the list from Home Assistant

Two ways, depending on whether you run the AdGuard Home integration.

| | Option A — AdGuard integration | Option B — REST commands |
| --- | --- | --- |
| Needs | The AdGuard Home integration | AdGuard URL + admin password in `secrets.yaml` |
| Several AdGuard servers | Handled — every loaded instance is updated | One `rest_command` per server |
| Reads the real state back | No — Home Assistant is the source of truth | Yes, via a REST sensor |
| Credentials | Already held by the integration | Duplicated into `secrets.yaml` |

### Option A — the AdGuard Home integration (recommended)

The integration's switches cover protection, filtering, safe search and parental control, and none of them touch an
individual filter list. Its **services** do: `adguard.enable_url` and `adguard.disable_url` each take a blocklist
URL, which is exactly the handle this list needs.

They apply to *every loaded AdGuard config entry*, so a primary/replica pair stays in step with no extra work:

```python
# homeassistant/components/adguard/__init__.py
async def enable_url(call: ServiceCall) -> None:
    for adguard in _get_adguard_instances(call.hass):
        await adguard.filtering.enable_url(allowlist=False, url=call.data[CONF_URL])
```

#### Install

1. Copy [`homeassistant/packages/youtube_kids_native.yaml`](homeassistant/packages/youtube_kids_native.yaml) to
   `<config>/packages/youtube_kids_native.yaml`.
2. Make sure `configuration.yaml` loads packages:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

3. If you forked this repo, change the blocklist URL in the package.
4. **Developer tools → YAML → Check configuration**, then restart Home Assistant.

No credentials go in this package — the integration already has them.

Everything in the package can equally be created from the UI (Settings → Devices & Services → Helpers, plus
Scripts and Automations). Do one or the other, not both, or you get duplicate entities.

#### What you get

| Entity | Purpose |
| --- | --- |
| `input_boolean.youtube_blocked_for_kids` | The toggle. **On = YouTube is blocked** for the Kids client. |
| `timer.youtube_allowance_kids` | Runs while a temporary allowance is active. `restore: true`, so it survives a restart. |
| `script.youtube_kids_allow` | Allow with no time limit; cancels any allowance. |
| `script.youtube_kids_block` | Block now; cancels any allowance. |
| `script.youtube_kids_extend_30` | +30 minutes. Twice gives 60, three times 90. |
| `automation.kids_sync_youtube_blocklist_to_adguard` | Pushes the toggle into AdGuard; re-asserts on HA start. |
| `automation.kids_block_youtube_when_the_allowance_timer_finishes` | Re-blocks when the allowance runs out. |

The toggle is the source of truth: Home Assistant writes to AdGuard, never the other way round. If you flip the list
in AdGuard's own UI, Home Assistant will not notice until the next restart or toggle. Option B is the one that reads
state back.

#### Two things that will bite you

Both are why `script.youtube_kids_extend_30` looks the way it does:

- **`timer.change` cannot extend a timer past its configured duration.** A second press of a +30 button on a
  30-minute timer fails with `Not possible to change timer ... beyond duration`. Use `timer.start` with a fresh
  total instead.
- **`remaining` goes stale while a timer runs.** It is only refreshed on state transitions, so a timer started 10
  minutes ago still reports the full 30. Derive the live remainder from `finishes_at`:

  ```jinja
  {{ ((as_timestamp(state_attr('timer.youtube_allowance_kids', 'finishes_at')) - as_timestamp(now())) | int) + 1800 }}
  ```

  An **idle** timer reports `remaining: None`, so guard that branch — a paused timer is the one case where
  `remaining` is accurate.

#### The dashboard section

[`homeassistant/dashboard/admin-adguard-section.yaml`](homeassistant/dashboard/admin-adguard-section.yaml) is a
section for a `type: sections` view: a status line, the allowance timer (shown only while one runs), and Allow /
+30 min / Block buttons.

Paste it into the `sections:` list of a view via the dashboard's three-dot menu → **Raw configuration editor**.

![AdGuard section on the Admin dashboard: status line, allowance countdown, and the three buttons][dashboard-screenshot]

[dashboard-screenshot]: docs/dashboard-admin-section.png

The status line is a markdown card — the only built-in card that renders templates, and the reason the dashboard can
say "Blocked" instead of showing a raw `on`.

#### Example: block on school nights

```yaml
automation:
  - alias: "Kids: block YouTube on school nights"
    description: "YouTube off at 19:00, back on at 07:00 the next morning."
    mode: single
    triggers:
      - trigger: time
        at: "19:00:00"
        id: block
      - trigger: time
        at: "07:00:00"
        id: unblock
    conditions:
      - condition: time
        weekday: [sun, mon, tue, wed, thu]
    actions:
      - choose:
          - conditions:
              - condition: trigger
                id: block
            sequence:
              - action: script.youtube_kids_block
          - conditions:
              - condition: trigger
                id: unblock
            sequence:
              - action: script.youtube_kids_allow
```

Both scripts cancel a running allowance, so a schedule always wins over a half-used +30.

### Option B — REST commands (fallback)

Use this when you do not run the AdGuard Home integration, or when you want Home Assistant to read the list's real
state back out of AdGuard instead of assuming it. It calls the API directly:
`POST /control/filtering/set_url` with `{"data": {"enabled": true|false, …}}`.

1. Copy [`homeassistant/packages/adguard_youtube_kids.yaml`](homeassistant/packages/adguard_youtube_kids.yaml) to
   `<config>/packages/adguard_youtube_kids.yaml`.
2. Load packages as in Option A.
3. Add your AdGuard Home login to `<config>/secrets.yaml`
   (see [`homeassistant/secrets.example.yaml`](homeassistant/secrets.example.yaml)):

   ```yaml
   adguard_username: admin
   adguard_password: your-adguard-password
   ```

4. Edit the two `EDIT ME` values at the top of the package: your AdGuard Home base URL
   (`http://homeassistant.local:3000` by default) and, if you forked this repo, the blocklist URL.
5. **Developer tools → YAML → Check configuration**, then restart Home Assistant.

| Entity | Purpose |
| --- | --- |
| `switch.youtube_blocked_for_kids` | **On = YouTube is blocked** for the Kids client. |
| `sensor.adguard_youtube_kids_filter` | The list's real state in AdGuard (`on` / `off` / `unknown`), polled every 60 s. |
| `rest_command.adguard_youtube_kids_filter_set` | Enables/disables the list; takes `enabled: true\|false`. |
| `rest_command.adguard_filters_refresh` | Forces AdGuard Home to re-download its lists. |

`unknown` on the sensor (and an unavailable switch) means AdGuard Home has no list with that exact URL — check for a
typo, or that you updated the URL after forking.

Running several AdGuard servers? Duplicate the `rest_command` once per server and call both from the switch; unlike
Option A, nothing fans out for you.

After the first install, reload just this config with **Developer tools → Actions** → `rest.reload`,
`rest_command.reload` and `template.reload` instead of restarting.

### Without Home Assistant

The same two calls with `curl`, if you want to script it elsewhere:

```bash
ADGUARD="http://homeassistant.local:3000"
LIST="https://raw.githubusercontent.com/lvlie/adguard-youtube-blocklist-kids/main/youtube-kids.txt"

# Enable (block YouTube for Kids) — use false to disable.
curl -u admin:password -X POST "$ADGUARD/control/filtering/set_url" \
  -H 'Content-Type: application/json' \
  -d "{\"url\":\"$LIST\",\"whitelist\":false,
       \"data\":{\"enabled\":true,\"name\":\"YouTube blocklist for Kids\",\"url\":\"$LIST\"}}"

# Read the current state of every list.
curl -s -u admin:password "$ADGUARD/control/filtering/status" | jq '.filters[] | {name, url, enabled}'
```

## Verifying and troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Rules do not apply to the device | It is a *runtime* client, not a persistent one, or the name is not exactly `Kids` |
| Still loads right after enabling | DNS cache on the device or in AdGuard Home — reconnect Wi-Fi, or flush the cache |
| Works on the phone, blocked on the laptop | The phone uses DNS-over-HTTPS or a VPN and never asks AdGuard Home |
| Nothing is blocked anywhere | The device has a hard-coded DNS server (8.8.8.8) instead of AdGuard Home |
| Another list unblocks YouTube | Should not happen — that is what `important` prevents. Check **Query log** for the matching rule |

**Query log** (filter by the `Kids` client) is the fastest way to see which rule matched and which list it came from.

Blocking DNS cannot stop a device that does not use your DNS server. If the kids' devices support it, also disable
"Private DNS" / "Secure DNS" on them, or block outbound DNS and DoH at the router.

## Using a different client name

1. Rename the client in the rules and in the `! Client:` header of [`youtube-kids.txt`](youtube-kids.txt):

   ```bash
   sed -i "s/\$client='Kids'/\$client='Teens'/g; s/^! Client: Kids$/! Client: Teens/" youtube-kids.txt
   python3 scripts/validate_blocklist.py
   ```

   The validator cross-checks the header against every rule, so a half-finished rename fails the build.

2. Names containing a `'` must escape it: `$client='Frank\'s laptop'`.
3. To keep a domain reachable for that client, add an exception rule *after* the block rules:

   ```text
   @@||youtubekids.com^$client='Kids',important
   ```

## Repository layout

```text
youtube-kids.txt                                     the blocklist
homeassistant/packages/youtube_kids_native.yaml      option A: AdGuard integration (recommended)
homeassistant/packages/adguard_youtube_kids.yaml     option B: rest_command + REST sensor + switch
homeassistant/dashboard/admin-adguard-section.yaml   dashboard section for the controls
homeassistant/secrets.example.yaml                   credentials for option B
docs/dashboard-admin-section.png                     screenshot used by the README
scripts/validate_blocklist.py                        syntax + client-scope validator
scripts/check_ha_package.py                          parses the option B package, renders its templates
tests/                                               tests for both scripts and for what they check
requirements-dev.txt                                 tooling used by the tests and CI
.pre-commit-config.yaml                              Markdown, YAML, blocklist and package hooks
.github/workflows/ci.yml                             validate, test, lint
```

## Development

```bash
pip install -r requirements-dev.txt
pre-commit install --hook-type pre-commit --hook-type pre-push

python3 scripts/validate_blocklist.py   # rules are well-formed and scoped to one client
python3 scripts/check_ha_package.py     # the HA package parses and its templates render
pytest -q                               # run the tests
pre-commit run --all-files              # run every hook
```

The pre-commit hooks lint Markdown and YAML, validate the blocklist and check the Home Assistant package;
the pre-push hook runs the tests. CI runs the same checks on every push and once a week.

Bump `! Version:` and `! Last modified:` in the blocklist header whenever you change the rules, and add a line to
[`CHANGELOG.md`](CHANGELOG.md). See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © lvlie
