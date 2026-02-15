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
                # Merge results. valid non-None values overwrite previous ones.
                # If we want to keep email from blog if github profile has none, or vice versa?
                # Let's simple merge: if res has value, take it.
                if res.get("scraped_email"):
                    user["scraped_email"] = res["scraped_email"]
                if res.get("scraped_linkedin"):
                    user["scraped_linkedin"] = res["scraped_linkedin"]

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
            "twitter_username": "Twitter", "scraped_linkedin": "LinkedIn",
            "html_url": "GitHub Profile"
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
    sem = asyncio.Semaphore(5) 

    async with async_playwright() as p:
        logger.info("Launching browser...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; StarReach/1.0)",
            viewport={"width": 1280, "height": 720}
        )
        await context.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script"] else route.abort())

        user_generator = client.get_stargazers(args.repo_url)
        
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

                tasks.append(process_user(user, scraper, context, sem))
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
            if tasks:
                logger.info("Cleaning up pending tasks...")
                await asyncio.gather(*tasks, return_exceptions=True)

            logger.info("Closing browser...")
            try:
                await browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")

    logger.info(f"Done. processed {len(new_users)} new users.")

if __name__ == "__main__":
    asyncio.run(main())
