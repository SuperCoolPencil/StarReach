## 2026-02-17 - Prevent Playwright Worker Hangs

**Learning:** Playwright's `context.new_page()` can hang indefinitely if the browser context becomes unresponsive, causing the entire worker pool to deadlock silently. This is a critical stability issue in long-running scraping jobs.
**Action:** Always wrap `context.new_page()` calls in `asyncio.timeout()` when using Playwright in async workers. This ensures that a single stuck page creation doesn't freeze the application.
