# Repository Guidelines

## Project Structure & Module Organization
StarReach is a small Python CLI app with a flat module layout at the repository root.
- `main.py`: CLI entrypoint and async orchestration pipeline.
- `github_client.py`: GitHub API pagination and profile fetching.
- `scraper.py`: Playwright-based website scraping for email/LinkedIn.
- `exporter.py`: Excel export via pandas/openpyxl.
- `.env.example`: required environment variable template.
- `pyproject.toml` and `uv.lock`: dependency and lock metadata.

If you add tests, place them under `tests/` and mirror module names (example: `tests/test_github_client.py`).

## Build, Test, and Development Commands
Use `uv` for local development.
- `uv sync`: install dependencies into the local environment.
- `uv run playwright install chromium`: install browser runtime used by scraper.
- `uv run python main.py https://github.com/owner/repo --limit 20`: run the end-to-end pipeline.
- `uv run python -m py_compile *.py`: quick syntax validation across root modules.

Output is written to `stargazers.xlsx` in the repo root by default.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions/variables, `PascalCase` for classes, and descriptive module names.
- Keep async boundaries explicit (`async def`, `await`) in scraping/orchestration code.
- Prefer type hints on public functions and return values.
- Keep modules focused: API access in `github_client.py`, scraping in `scraper.py`, export logic in `exporter.py`.

## Testing Guidelines
There is currently no committed automated test suite. For new work:
- Add `pytest` tests under `tests/` for pure logic (URL parsing, column mapping, data transforms).
- Mock network/Playwright calls; avoid live GitHub/browser calls in CI-style tests.
- Run with `uv run pytest` once tests are added.

Also run a manual smoke test of the CLI with `--limit` to validate integration behavior.

## Commit & Pull Request Guidelines
Current history uses short, imperative messages and Conventional Commit style (example: `feat: implement core functionality ...`).
- Prefer `feat:`, `fix:`, `refactor:`, `docs:`, `test:` prefixes.
- Keep commits scoped to one concern.
- PRs should include: what changed, why, how it was tested, and any env/config updates.
- Include sample command/output when behavior changes (for example, changed export columns or scrape fields).

## Security & Configuration Tips
- Never commit real tokens; use `.env` locally and keep `GITHUB_TOKEN` private.
- Treat scraped personal data carefully; export only fields needed for the use case.
