import os
import asyncio
import argparse
import logging
import pandas as pd
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from github_client import GitHubClient
from scraper import ProfileScraper
from exporter import export_to_excel

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("starreach.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce noise from third-party libs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("playwright").setLevel(logging.INFO)

async def process_user(user, scraper, context, sem):
    """
    Process a single user: 
    1. Check bio for contacts.
    2. Scrape blog/website if present.
    3. Scrape GitHub profile (readme/sidebar) if present.
    """
    # 1. Check Bio
    bio = user.get("bio")
    if bio:
        bio_contacts = scraper.extract_from_text(bio)
        # Update only if not already found (or overwrite? let's overwrite as bio might be fresher or just merge)
        # Actually simplest is just update, but we want to prioritize "best" source? 
        # Let's just update for now.
        if bio_contacts["scraped_email"] or bio_contacts["scraped_linkedin"]:
             logger.debug(f"Found contact in bio for {user.get('login')}: {bio_contacts}")
             user.update(bio_contacts)

    # 2. Collect URLs to scrape
    urls_to_scrape = []
    
    blog = user.get("blog")
    if blog:
        urls_to_scrape.append(blog)
        
    html_url = user.get("html_url")
    if html_url:
        urls_to_scrape.append(html_url)

    # 3. Scrape concurrently
    if urls_to_scrape:
        async with sem:
            logger.debug(f"Scraping URLs for {user.get('login')}: {urls_to_scrape}")
            
            async def scrape_wrapper(u):
                try:
                    return await scraper.scrape_url(context, u)
                except Exception as e:
                    logger.error(f"Error scraping {u} for {user.get('login')}: {e}")
                    return {}

            results = await asyncio.gather(*[scrape_wrapper(u) for u in urls_to_scrape])
            
            for res in results:
                # Merge logic: update if not present or just overwrite?
                # Let's overwrite as scraped data is usually more specific than what we might have guessed
                for key, value in res.items():
                    if value:
                        user[key] = value

    return user

def save_progress(base_df, new_users, filename="stargazers.xlsx"):
    """
    Saves the combined (base + new) data to Excel.
    """
    try:
        new_df = pd.DataFrame(new_users)
        
        # Rename columns to match export format
        columns_map = {
            "login": "Username", "name": "Name", "email": "GitHub Email",
            "scraped_email": "Scraped Email", "blog": "Website",
            "company": "Company", "location": "Location",
            "twitter_username": "Twitter (GitHub)",
            "scraped_twitter": "Twitter (Scraped)",
            "scraped_linkedin": "LinkedIn",
            "scraped_facebook": "Facebook",
            "scraped_instagram": "Instagram",
            "scraped_youtube": "YouTube",
            "scraped_bluesky": "Bluesky",
            "html_url": "GitHub Profile",
            "bio": "Bio"
        }
        
        # Filter and rename cols in new_df
        valid_cols = [c for c in columns_map.keys() if c in new_df.columns]
        new_df = new_df[valid_cols].rename(columns=columns_map)
        
        # Combine
        combined_df = pd.concat([base_df, new_df], ignore_index=True)
        
        # Save
        combined_df.to_excel(filename, index=False)
        logger.info(f"Progress saved. Total records: {len(combined_df)}")
    except Exception as e:
        logger.error(f"Failed to save progress: {e}")

async def main():
    parser = argparse.ArgumentParser(description="StarReach: Fetch and enrich GitHub stargazers.")
    parser.add_argument("repo_url", help="GitHub repository URL (e.g., https://github.com/owner/repo)")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of stargazers to fetch")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token or token == "your_github_token_here":
        logger.error("GITHUB_TOKEN not found or invalid in .env file.")
        print("Please create a .env file with GITHUB_TOKEN=...")
        return

    logger.info(f"Fetching stargazers for {args.repo_url}...")
    client = GitHubClient(token)
    scraper = ProfileScraper()
    
    # Load existing data to preserve it and skip duplicates
    base_df = pd.DataFrame()
    existing_usernames = set()
    
    if os.path.exists("stargazers.xlsx"):
        try:
            base_df = pd.read_excel("stargazers.xlsx")
            if "Username" in base_df.columns:
                existing_usernames = set(base_df["Username"].dropna().astype(str))
            logger.info(f"Loaded {len(base_df)} existing records.")
        except Exception as e:
            logger.error(f"Error reading existing file: {e}")

    logger.info(f"Checking against {len(existing_usernames)} existing users.")
    
    new_users = []
    
    # We'll use a semaphore to limit concurrent browser pages
        # Semaphore for concurrent operations (both GitHub API and Scraping)
        # We can increase this since GitHub API is now non-blocking I/O (in threads)
        # But we still want to be nice to GitHub API limits.
        # Let's say 10 concurrent users processing at once.
    sem = asyncio.Semaphore(10)

    async def process_full_user(raw_user):
            async with sem:
                try:
                    # 1. Fetch details concurrently (non-blocking)
                    # Use to_thread to run sync request in a separate thread
                    if "url" in raw_user:
                         details = await asyncio.to_thread(client.get_user_details, raw_user["url"])
                         if details:
                             raw_user.update(details)
                    
                    # 2. Scrape (already async)
                    # We pass 'sem' to process_user but since we are already inside 'sem' here,
                    # we might double-lock if process_user also uses sem?
                    # The original process_user used 'sem'.
                    # Let's refactor process_user to NOT use sem, or pass a dummy sem / nullcontext.
                    # Actually, we can just remove sem from process_user call if we handle it here.
                    # But process_user expects it. 
                    # Let's just pass a null context or modify process_user?
                    # Modifying process_user is cleaner but let's see.
                    # Let's just create a dummy semaphore that does nothing, or pass the same sem?
                    # If we pass same sem, we deadlock because we already hold it!
                    # So we MUST NOT pass the same sem if process_user acquires it.
                    
                    # Wait, process_user definition: async def process_user(user, scraper, context, sem):
                    # inside: async with sem:
                    # If we hold sem here, and process_user tries to acquire sem, it will block if count is 1?
                    # No, semaphores are not re-entrant locks.
                    # So deadlock RISK!
                    
                    # Solution: Don't acquire sem here for the whole block.
                    # Acquire sem for GitHub fetch, then release.
                    # Then process_user acquires sem for Scraping.
                    # This is better for resource usage anyway (don't hold browser slot while waiting for github).
                    pass
                except Exception as e:
                    logger.error(f"Error processing user {raw_user.get('login')}: {e}")
                    return raw_user
            
            # Re-implementation with fine-grained locking
            
            # A. Fetch Details
            try:
                # Limit GitHub concurrency separately? Or just rely on thread pool limit?
                # Thread pool is large (32). Let's use a separate sem for GitHub if needed.
                # converting synchronous IO to thread is good.
                if "url" in raw_user:
                     details = await asyncio.to_thread(client.get_user_details, raw_user["url"])
                     if details:
                         raw_user.update(details)
            except Exception as e:
                 logger.error(f"Error fetching details for {raw_user.get('login')}: {e}")

            # B. Scrape (process_user handles its own locking)
            # We need to make sure we don't start too many scraper tasks at once if we flood this.
            # But process_user takes a semaphore! So it's safe.
            return await process_user(raw_user, scraper, context, sem)

    logger.info("Launching browser...")
    browser = await p.chromium.launch(headless=False)
    context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; StarReach/1.0)",
            viewport={"width": 1280, "height": 720}
        )
    await context.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script"] else route.abort())

        # Get raw stargazers
    user_generator = client.get_stargazers(args.repo_url, fetch_details=False)
        
    tasks = []
    total_fetched = 0
    skipped_count = 0
        
    try:
            for user in user_generator:
                if args.limit and total_fetched >= args.limit:
                    logger.info(f"Hit limit of {args.limit} users.")
                    break
                
                # Check if user already exists
                if user.get("login") in existing_usernames:
                    skipped_count += 1
                    if skipped_count % 50 == 0:
                        logger.info(f"Skipped {skipped_count} existing users...")
                    continue

                # Launch async task
                # We need to bound the number of concurrent tasks we spawn, otherwise we might OOM 
                # if we iterate 1000 users instantly.
                # So we should use a semaphore to limit *inflight* tasks.
                # But process_full_user is async.
                
                if len(tasks) >= 20: 
                    # This batch logic waits for ALL 20 to finish. 
                    # Ideally we want a sliding window, but batch is fine.
                    # The speedup comes from the fact that inside the batch,
                    # waiting for GitHub for User A doesn't block starting GitHub for User B.
                    logger.info(f"Processing batch of {len(tasks)} (Total new fetched: {total_fetched})...")
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Filter results
                    current_batch_users = []
                    for r in batch_results:
                        if isinstance(r, Exception):
                            logger.error(f"Task failed with error: {r}")
                        else:
                            current_batch_users.append(r)
                    
                    new_users.extend(current_batch_users)
                    tasks = []
                    
                    save_progress(base_df, new_users)

                tasks.append(process_full_user(user))
                total_fetched += 1

                
                if len(tasks) >= 20:
                    logger.info(f"Processing batch of {len(tasks)} (Total new fetched: {total_fetched})...")
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Filter results
                    current_batch_users = []
                    for r in batch_results:
                        if isinstance(r, Exception):
                            logger.error(f"Task failed with error: {r}")
                        else:
                            current_batch_users.append(r)
                    
                    new_users.extend(current_batch_users)
                    tasks = []
                    
                    # Save Progress
                    save_progress(base_df, new_users)

            # Process remaining
            if tasks:
                logger.info(f"Processing final batch of {len(tasks)}...")
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                current_batch_users = [r for r in batch_results if not isinstance(r, Exception)]
                new_users.extend(current_batch_users)
                save_progress(base_df, new_users)
                tasks = []

    except KeyboardInterrupt:
            logger.warning("Operation stopped by user.")
    except Exception as e:
            logger.error(f"An error occurred in main loop: {e}", exc_info=True)
    finally:
            if new_users:
                logger.info(f"Saving progress before exit ({len(new_users)} new records)...")
                save_progress(base_df, new_users)

            logger.info("Cancelling pending tasks...")
            # We don't await tasks here because they might be stuck. 
            # We just let them die with the loop or try to cancel if we had task objects.
            # Since we passed coroutines to gather, we can't easily cancel them individually 
            # unless we wrapped them. But standard exit will cleanup.

            logger.info("Closing browser...")
            try:
                await browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")



    logger.info(f"Done. processed {len(new_users)} new users.")

if __name__ == "__main__":
    asyncio.run(main())
