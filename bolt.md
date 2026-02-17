## 2026-02-17 - Prevent Playwright Worker Hangs

**Learning:** Playwright's `context.new_page()` can hang indefinitely if the browser context becomes unresponsive, causing the entire worker pool to deadlock silently. This is a critical stability issue in long-running scraping jobs.
**Action:** Always wrap `context.new_page()` calls in `asyncio.timeout()` when using Playwright in async workers. This ensures that a single stuck page creation doesn't freeze the application.

## 2026-02-18 - Non-Blocking File I/O

**Learning:** Performing synchronous file I/O (like `pd.to_excel`) inside an async event loop blocks the loop entirely, pausing all concurrent tasks (network requests, etc.). This manifests as "hanging" or severe performance degradation as the file size grows.
**Action:** Offload expensive I/O operations to a separate thread using `asyncio.to_thread`. This allows the event loop to continue processing network events while the file is being saved in the background.
