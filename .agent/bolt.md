# Bolt's Journal

## 2026-02-15 - Synchronous GitHub API Calls blocking Event Loop

**Learning:** The `GitHubClient` performs synchronous `requests.get` calls inside a generator. When iterated in an async context (even with `asyncio.to_thread` or just directly), it blocks the _entire_ event loop if not properly offloaded. In `main.py`, the iteration happens directly in the async function, blocking everything, including concurrent Playwright scraping.

**Action:** Refactor `GitHubClient` to separate list fetching from detail fetching. Use `asyncio.to_thread` in `main.py` to offload the detail fetching to a thread pool, allowing network I/O to happen concurrently with scraping.
