# Repository Guidelines

## Project Structure & Module Organization

This is a Python Telegram bot for downloading GPX tracks from nakarte.me. Runtime code lives in `src/`: `src/main.py` wires the application, `src/bot/handlers.py` contains Telegram handlers, `src/services/` holds GPX extraction and cache backends, and `src/utils/logger.py` configures structured logging. Root-level docs (`README.md`, `QUICKSTART.md`, `TESTING.md`, `PROJECT_STRUCTURE.md`) explain operation and troubleshooting. Docker support is in `Dockerfile` and `docker-compose.yml`. The current standalone test script is `test_nakarte.py`; generated runtime data such as `logs/`, `cache/`, `.env`, and Playwright artifacts should stay untracked.

## Build, Test, and Development Commands

- `python -m venv venv` then `venv\Scripts\activate` on Windows: create and enter a local environment.
- `pip install -r requirements.txt`: install bot, optional Redis client, logging, and Playwright dependencies.
- `playwright install chromium`: install the browser used by `NakarteService`.
- `python -m src.main`: run the bot locally after configuring `.env`.
- `python test_nakarte.py "https://nakarte.me/#...&nktl=TRACK_ID"`: exercise GPX extraction without Telegram.
- `docker-compose up -d`: start the bot with persistent file cache using containers.
- `docker-compose logs -f bot`: follow bot logs.

## Coding Style & Naming Conventions

Use Python 3.11+ async patterns already present in the codebase. Follow PEP 8 with 4-space indentation, `snake_case` for functions and variables, `PascalCase` for classes, and uppercase names for constants such as URL patterns. Keep service boundaries clear: Telegram behavior belongs in `src/bot`, browser/API extraction in `src/services/nakarte_service.py`, cache behavior in `src/services/cache_service.py`, and logging setup in `src/utils`.

## Testing Guidelines

Use `test_nakarte.py` for integration-style GPX checks and add focused automated tests as behavior grows. Prefer `pytest` with `pytest-asyncio` for async services; name files `test_*.py` and test functions `test_*`. For browser-dependent changes, verify both headless and `--no-headless` flows when debugging extraction issues. Document manual Telegram checks in the PR when they are required.

## Commit & Pull Request Guidelines

The existing history uses short imperative subjects, for example `Create Redisbkp.md`. Keep commits focused and describe the user-visible change. Pull requests should include a summary, configuration changes, test commands run, and any manual bot or nakarte.me validation. Link related issues when available and include screenshots or log snippets only when they clarify behavior.

## Security & Configuration Tips

Never commit `.env`, bot tokens, Redis passwords, generated GPX files, logs, or cache contents. File cache is the default and persists indefinitely; use `CACHE_TYPE=redis` only when running Redis separately. Keep timeouts and log levels configurable through environment variables rather than hard-coding operational values.
