# AGENTS.md

## What This Repo Is
- `src/app.py` is the runtime entrypoint and Qt orchestrator (PyQt6 + QML + Qt WebEngine kiosk dashboard).
- `src/functions.py` contains most UI-agnostic logic (API fetch, caching, wifi/network, update checks, env/log setup).
- `src/ui_qml.py` stores the full UI as inline `qml_code` loaded via `QQmlApplicationEngine.loadData(...)`.
- `src/globe.html` is a Three.js page served locally and embedded in QML WebEngine views.

## Startup and Data Flow (Read This First)
- `app.py` calls `setup_dashboard_environment()` **before** importing PyQt modules; keep this ordering.
- App boots local HTTP server (`start_http_server`) first; this serves `globe.html`, YouTube wrappers, and Spotify callback endpoint.
- `Backend` initializes from caches, then starts async boot diagnostics + `DataLoader` threads.
- `DataLoader.run()` delegates to `perform_full_dashboard_data_load(...)` in `functions.py`; results are pushed to QML via Qt signals/properties.
- QML connects to backend signals (`reloadWebContent`, `updateGlobeTrajectory`, `firstOnline`, etc.) and injects JS into embedded pages.

## Cache and Persistence Model
- Seed cache in repo: `cache/previous_launches_cache.json`, `cache/upcoming_launches_cache.json`, `cache/trajectory_cache.json`.
- Runtime/persistent cache: `~/.cache/spacex-dashboard` (launches/weather/narratives/calendar/chart + settings + wifi data).
- Launch data uses merged model: runtime combined cache first, then repo seed fallback (`load_launch_cache`).
- Avoid changing cache schemas casually; many startup paths assume `{"data": ..., "timestamp": ...}`.

## External Integrations
- Launch/weather/narrative API base is `LAUNCH_API_BASE_URL` in `src/functions.py`.
- Spotify OAuth uses local callback `http://127.0.0.1:8080-8084/spotify/callback` and env vars `SPOTIFY_CLIENT_ID` (+ optional secret).
- Update checks hit GitHub commits API (`check_github_for_updates`) and branch preference is persisted.

## Project-Specific Conventions
- Keep business/data logic in `functions.py`; keep `app.py` focused on Qt objects, threading, and signal wiring.
- Do not rename Qt signal/property identifiers without updating QML bindings in `src/ui_qml.py`.
- Web content reloads are intentionally debounced/throttled in both Python and QML to avoid UI stutter.
- `src/globe.html` includes watchdog/recovery logic for long-run Pi stability; preserve these guard paths when editing animation code.
- Tests in `tests/` often parse source text/regex (not runtime behavior), so string-level changes can break regressions.

## Known Sharp Edges
- `src/functions.py` currently has duplicate function names near the end (e.g., remembered network helpers); later definitions override earlier ones.
- `src/app.py` imports `functions` as a top-level module, so run from `src/` (or set `PYTHONPATH` accordingly).
- Pi setup scripts are opinionated and large (`scripts/setup_pi.sh`); treat as deployment automation, not app runtime logic.

## Developer Workflows
- Run app locally (matching repo scripts/systemd): `cd src && python3 app.py`
- Source-level regression checks: `python3 -m pytest tests/test_globe_freeze_fixes.py tests/test_ticker_speed.py tests/test_youtube_embed.py`
- Quick syntax/import sanity scripts: `python3 tests/syntax_check.py` and `python3 tests/syntax_check_braces.py`
- Raspberry Pi provisioning: `sudo bash scripts/setup_pi.sh` (or `scripts/setup_pi_dfr1125.sh` for DFR1125 display profile).

## When Making Changes
- If you touch `globe.html` or QML WebEngine behavior, run the targeted regression tests that parse those files.
- If you change startup/cache/network behavior, verify both offline fallback and first-online transition paths.
- Prefer small, signal-safe edits: startup is heavily asynchronous and ordering-sensitive by design.

