# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Status is a self-hosted uptime monitoring and status page service. It monitors websites via HTTP checks (every 3 minutes), runs Lighthouse audits (daily), and crawls sites for SEO analysis (weekly). Alerts are sent via email and Discord webhooks on state transitions.

## Development Commands

```bash
make                  # Install deps + run Django dev server + Vite watch (parallel)
make scheduler        # Run the monitoring scheduler (separate terminal)
make clean            # Remove node_modules, .venv, db, media
make pull             # Rsync production database and media locally
make push             # Push to all git remotes
```

Dependencies: Python (uv), JS (bun). Node is installed only so the `lighthouse` npm CLI can run — Bun doesn't execute Lighthouse correctly (bun issue #4958). Default dev credentials: admin/admin.

### Linting (no test runner)

```bash
uv run black .
uv run isort .
uv run flake8
```

Black profile: 88 char lines. isort uses `profile=black`. Flake8 ignores E203. All Python tool configs are in `pyproject.toml`.

## Architecture

### Django Apps

- **accounts** - Custom User model (UUID PK) with `discord_webhook_url` field. Standard auth views.
- **properties** - Core app. `Property` model tracks a URL's monitoring state; `Check` model stores individual HTTP check results. Property behavior is split into mixins: `SecurityMixin` (header analysis), `AlertsMixin` (state machine for up/down notifications), `CrawlerMixin` (Scrapy SEO data).
- **pages** - Static marketing pages (home, changelog, robots.txt, sitemap).

### Scheduler (`properties/management/commands/scheduler.py`)

Single management command that runs in an infinite loop (30-second cycle). Uses two thread pools with `queue.Queue`:
- **Status checks**: Properties where `next_run_at` has passed (3-min intervals). HTTP timeout is 10s. SSL errors map to status 526, timeouts to 408.
- **Lighthouse + Crawler**: Daily Lighthouse via Node CLI wrapper (`status/lighthouse.py`), weekly Scrapy crawl via subprocess (`crawler/runner.py`).

Cleans up checks older than 3 days each cycle.

### Alert State Machine (`properties/mixins/alerts.py`)

Two states: `up` (default) and `down`. Transitions:
- **UP -> DOWN**: Requires 2 consecutive non-200 checks (avoids false positives).
- **DOWN -> UP**: Immediate on 200 status code.

Alerts (email + Discord webhook) only fire on state transitions, not on every check.

### Frontend (Vite)

Three entry points in `vite.config.js`, all output to `status/static/` with stable filenames (no hashing) so templates reference them via plain `{% static %}`:
- `status/static_src/index.js` -> base Bootstrap 5 bundle
- `pages/static_src/index.js` -> homepage styles
- `properties/static_src/index.js` -> Chart.js graphs, D3/Datamaps, print styles

`bun run dev` runs `vite build --watch`; refresh the browser manually to see changes. The `fixDatamapsStrictMode` Vite plugin patches datamaps/d3v3 for ESM-strict mode at transform time.

### External Tool Wrappers

- `status/lighthouse.py` - Invokes `node_modules/.bin/lighthouse` with headless Chrome flags, parses JSON scores.
- `status/chromium.py` - Headless Chromium for PDF report generation. Auto-detects `chromium` vs `chromium-browser` binary.
- `crawler/` - Scrapy project with `seo_spider.py` CrawlSpider. Extracts title, meta description, canonical URL, OG tags, H1 per page.

### Settings

Split settings: `status/settings/__init__.py` (shared), `development.py`, `production.py`. Django picks based on `DJANGO_SETTINGS_MODULE` env var (defaults to development). Production uses env vars for SECRET_KEY, BASE_URL, IPINFO_TOKEN and stores SQLite at `/data/db/`.

### Production

Docker Compose runs a single `web` service. `entrypoint.py` spawns Gunicorn (Uvicorn workers) and the `scheduler` management command side-by-side in that container — if either process exits, the container stops and Docker restarts it. Deploys via `git push server master` triggering a post-receive hook.
