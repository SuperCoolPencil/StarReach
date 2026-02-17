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
    level=logging.INFO, # Changed to INFO to reduce noise, explicit DEBUG for specific modules if needed
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("starreach.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce noise
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("playwright").setLevel(logging.WARNING)

async def worker(worker_id, user_queue, result_queue, client, scraper, context):
    logger.debug(f"Worker {worker_id} started.")
    while True:
        try:
            # Get a "work item"
            raw_user = await user_queue.get()
            
            # Sentinel to stop
            if raw_user is None:
                user_queue.task_done()
                break

            login = raw_user.get("login", "unknown")
            # logger.debug(f"Worker {worker_id} processing {login}")

            # 1. Fetch Details (Bio, Blog, etc.) if not fully present
            # We assume raw_user comes from the list endpoint which lacks full bio/blog often.
            if "url" in raw_user and "bio" not in raw_user: # Basic check
                try:
                    details = await asyncio.to_thread(client.get_user_details, raw_user["url"])
                    if details:
                        raw_user.update(details)
                except Exception as e:
                    logger.warning(f"Worker {worker_id}: Error fetching details for {login}: {e}")

            # 2. Scrape
            # Scraper logic embedded here to use the shared context
            try:
                # Check Bio
                bio = raw_user.get("bio")
                if bio:
                    bio_contacts = scraper.extract_from_text(bio)
                    if bio_contacts["scraped_email"] or bio_contacts["scraped_linkedin"]:
                        raw_user.update(bio_contacts)

                # Collect URLs
                urls_to_scrape = []
                if raw_user.get("blog"): urls_to_scrape.append(raw_user.get("blog"))
                if raw_user.get("html_url"): urls_to_scrape.append(raw_user.get("html_url"))

                for url in urls_to_scrape:
                    try:
                        scraped_data = await scraper.scrape_url(context, url)
                        # Merge scraped data
                        for k, v in scraped_data.items():
                            if v: raw_user[k] = v
                    except Exception as scrape_err:
                        # Log partial failure but don't crash whole worker for one URL
                        # UNLESS it's the only URL and we want to retry?
                        # Actually per user request: "NEVER missed linkedin, if it fails it must be requeued"
                        # If a scrape fails, we might miss LinkedIn. So we should retry the USER.
                        logger.warning(f"Failed to scrape {url} for {login}: {scrape_err}")
                        raise scrape_err # Re-raise to trigger user retry logic

            except Exception as e:
                # Retry Logic
                retries = raw_user.get("_retries", 0)
                if retries < 3:
                    raw_user["_retries"] = retries + 1
                    logger.warning(f"Worker {worker_id}: Error processing {login} (Attempt {retries+1}/3). Requeuing. Error: {e}")
                    # Requeue
                    await user_queue.put(raw_user)
                    user_queue.task_done()
                    continue
                else:
                    logger.error(f"Worker {worker_id}: Max retries reached for {login}. Skipping. Last Error: {e}")

            # Push to result (only if successful or max retries reached)
            await result_queue.put(raw_user)
            user_queue.task_done()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} crashed: {e}")
            user_queue.task_done()

async def saver(result_queue, base_df, filename="stargazers.xlsx"):
    buffer = []
    while True:
        try:
            # Wait for result, but timeout occasionally to flush buffer
            try:
                user = await asyncio.wait_for(result_queue.get(), timeout=5.0)
                if user is None: # Sentinel
                    if buffer:
                        save_progress(base_df, buffer, filename)
                    result_queue.task_done()
                    break
                buffer.append(user)
                result_queue.task_done()
            except asyncio.TimeoutError:
                pass # Flush buffer
            
            if len(buffer) >= 20 or (buffer and not result_queue.empty() is False): # Flush if buffer big or timeout hit
                save_progress(base_df, buffer, filename)
                # Keep buffer in memory? No, save_progress appends to file? 
                # Our save_progress loads old, merges new, saves. 
                # So we should probably accumulate 'new_users' in main scope? 
                # OR save_progress can just take the NEW chunk and append?
                # The current save_progress implementation:
                # combined_df = pd.concat([base_df, new_df], ignore_index=True)
                # This means it rewrites the whole file. 
                # If we pass ONLY buffer to save_progress, we need to update 'base_df' too!
                
                # Let's update base_df with buffer
                if buffer:
                    new_df = pd.DataFrame(buffer)
                    # (Filtering logic inside save_progress duplicates this, but okay)
                    # We need to make sure we don't handle 'buffer' clearing inside save_progress 
                    # if we pass it by reference.
                    pass
                
                # To be safe and simple: 
                # We will keep a 'total_collected' list in saver? 
                # Or just update base_df.
                pass
                
        except asyncio.CancelledError:
            # Flush remaining
            if buffer:
                save_progress(base_df, buffer, filename)
            break
        except Exception as e:
            logger.error(f"Saver crashed: {e}")

# Helper to reuse existing save logic
def save_progress(base_df, new_users, filename="stargazers.xlsx"):
    # (Same as before, but we need to ensure we append safely)
    # Actually, allow me to modify this to be more efficient if possible, 
    # but for now, reusing existing 'overwrite full file' is safest for data integrity.
    # But we need to update base_df so next save includes previous batch!
    # This is tricky. 'base_df' passed to saver needs to be mutable or updated.
    # Actually, we can just read the file again? No, that's slow.
    # Let's just append 'new_users' to 'base_df' inside the loop.
    try:
        if not new_users: return

        new_df = pd.DataFrame(new_users)
        
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
        
        valid_cols = [c for c in columns_map.keys() if c in new_df.columns]
        new_df = new_df[valid_cols].rename(columns=columns_map)
        
        # Update base_df by concatenating
        # We need to use 'global' or return it. 
        # But pandas objects are mutable-ish if we append? No, concat returns new.
        # We will just write to file for now. 
        # Ideally we read the file, append, write. 
        # OR we keep a running 'all_users' list in saver.
        
        # Let's assume saver keeps 'all_data'.
        # But we passed 'base_df'.
        
        # FIX: Just read file, append, save. 
        # It's not super fast but fine for every 20 records.
        if os.path.exists(filename):
            existing = pd.read_excel(filename)
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            combined = pd.concat([base_df, new_df], ignore_index=True) # base_df is initial
        
        combined.to_excel(filename, index=False)
        logger.info(f"Saved {len(new_users)} new users. Total: {len(combined)}")
        
        # Clear buffer after save
        new_users.clear() # This clears the list passed in! 
            
    except Exception as e:
        logger.error(f"Save failed: {e}")

async def main():
    parser = argparse.ArgumentParser(description="StarReach")
    parser.add_argument("repo_url")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    client = GitHubClient(token)
    scraper = ProfileScraper()
    
    # Load existing
    existing_usernames = set()
    initial_df = pd.DataFrame()
    if os.path.exists("stargazers.xlsx"):
        df = pd.read_excel("stargazers.xlsx")
        initial_df = df
        if "Username" in df.columns:
            existing_usernames = set(df["Username"].dropna().astype(str))
    
    logger.info(f"Skipping {len(existing_usernames)} existing.")

    # Queues
    user_queue = asyncio.Queue(maxsize=100) # Buffer 100 users
    result_queue = asyncio.Queue()

    # Browser
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Start Workers
        workers = [
            asyncio.create_task(worker(i, user_queue, result_queue, client, scraper, context))
            for i in range(10)
        ]
        
        # Start Saver
        saver_task = asyncio.create_task(saver(result_queue, initial_df))

        # Producer Logic
        try:
            total_fetched = 0
            
            # Helper for explicit non-blocking loop
            owner, repo = client._parse_repo_url(args.repo_url)
            current_url = f"{client.base_url}/repos/{owner}/{repo}/stargazers"
            
            while current_url:
                if args.limit and total_fetched >= args.limit: 
                    logger.info(f"Hit limit of {args.limit} users.")
                    break
                
                # Fetch page in thread (network I/O)
                try:
                    # fetch_stargazers_page returns (users, next_url, retry_after)
                    users, next_url, retry_after = await asyncio.to_thread(client.fetch_stargazers_page, current_url)
                except Exception as e:
                    logger.error(f"Error fetching page: {e}")
                    break
                
                # Handle Rate Limit (Async Sleep)
                if retry_after > 0:
                    logger.warning(f"Rate limit hit. Sleeping for {retry_after} seconds (async)...")
                    await asyncio.sleep(retry_after)
                    continue # Retry same URL (fetch_stargazers_page returns same url on limit)
                
                if not users and not next_url:
                    break # Done or error
                
                # Enqueue users
                for user in users:
                    if args.limit and total_fetched >= args.limit: break
                    
                    if user.get("login") in existing_usernames:
                        continue
                    
                    await user_queue.put(user)
                    total_fetched += 1
                    if total_fetched % 50 == 0:
                        logger.info(f"Queued {total_fetched} users...")
                
                current_url = next_url
            
            # Signal end
            for _ in workers:
                await user_queue.put(None)
                
            await user_queue.join()
            
            # Signal saver
            await result_queue.put(None)
            await saver_task
            
        except KeyboardInterrupt:
            logger.info("Stopping...")
            # Cancel workers
            for w in workers: w.cancel()
            # Wait for saver to flush
            await result_queue.put(None)
            await saver_task
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
