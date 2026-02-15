import os
import asyncio
import argparse
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from github_client import GitHubClient
from scraper import ProfileScraper
from exporter import export_to_excel, load_existing_users

async def process_user(user, scraper, context, sem):
    """
    Process a single user: scrape additional info if blog/website is present.
    """
    blog = user.get("blog")
    if blog:
        # Use semaphore to limit concurrent browser tabs
        async with sem:
            try:
                scraped_data = await scraper.scrape_user_website(context, blog)
                user.update(scraped_data)
            except Exception as e:
                print(f"Error scraping {blog}: {e}")
    return user

async def main():
    parser = argparse.ArgumentParser(description="StarReach: Fetch and enrich GitHub stargazers.")
    parser.add_argument("repo_url", help="GitHub repository URL (e.g., https://github.com/owner/repo)")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of stargazers to fetch")
    args = parser.parse_args()

    load_dotenv()
    token = os.getenv("GITHUB_TOKEN")
    if not token or token == "your_github_token_here":
        print("Error: GITHUB_TOKEN not found or invalid in .env file.")
        print("Please create a .env file with GITHUB_TOKEN=...")
        return

    print(f"Fetching stargazers for {args.repo_url}...")
    client = GitHubClient(token)
    scraper = ProfileScraper()
    
    # Load existing users to skip
    existing_usernames = set(load_existing_users("stargazers.xlsx"))
    print(f"Found {len(existing_usernames)} existing users in stargazers.xlsx. These will be skipped.")
    
    stargazers = []
    
    # We'll use a semaphore to limit concurrent browser pages
    sem = asyncio.Semaphore(5) 

    async with async_playwright() as p:
        print("Launching browser...")
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
                    break
                
                # Check if user already exists
                if user.get("login") in existing_usernames:
                    skipped_count += 1
                    if skipped_count % 50 == 0:
                        print(f"Skipped {skipped_count} existing users...")
                    continue

                tasks.append(process_user(user, scraper, context, sem))
                total_fetched += 1
                
                if len(tasks) >= 20:
                    print(f"Processing batch of {len(tasks)} (Total new fetched: {total_fetched})...")
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Filter out exceptions from batch_results if any
                    valid_results = [r for r in batch_results if not isinstance(r, Exception)]
                    stargazers.extend(valid_results)
                    tasks = []
                    
                    # Incremental Save (Optional: append to file or just save what we have)
                    # For simplicity, let's just save the whole accumulated list + read current file to merge?
                    # Or just save at the end. Since we are skipping, user can just rerun.
                    # To be safe, let's verify exporting doesn't blow away partial progress if we were to crash *now*.
                    # But the requirement is "not do done stars again", which we handled via skipping.
                    # If we crash mid-execution, we lose the *current* run's memory data.
                    # So saving periodically is good.
                    
                    # Append logic is tricky with Excel. 
                    # Let's just save the TOTAL list (previous + current) if we loaded them, 
                    # BUT load_existing_users only returns names. We don't have the full objects.
                    # So we should probably just append the NEW ones to a separate list and merge at the end?
                    # OR, we read the existing file into a DataFrame, convert to dict, and keep it in memory.
                    pass

            if tasks:
                print(f"Processing final batch of {len(tasks)}...")
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                valid_results = [r for r in batch_results if not isinstance(r, Exception)]
                stargazers.extend(valid_results)
                tasks = []

        except KeyboardInterrupt:
            print("\nOperation stopped by user.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            # If tasks are left (e.g. exception in loop), we must await them to avoid warnings
            # or just cancel them.
            if tasks:
                print(f"Cleaning up {len(tasks)} pending tasks...")
                for t in tasks:
                     # tasks are coroutines here because process_user is called but not awaited
                     # Wait, tasks list holds COROUTINE OBJECTS.
                     # We should wrap them in Tasks or await them. 
                     # asyncio.gather expects coroutines or Futures.
                     pass
                # A simple gather with return_exceptions=True should handle them
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except:
                    pass

            await browser.close()

    print(f"Total new users processed: {len(stargazers)}")
    
    if stargazers:
        print("Exporting data...")
        # If we want to APPEND to existing file:
        if os.path.exists("stargazers.xlsx"):
            # We need to read it, append new data, and write back.
            # Ideally load_existing_users would have returned the whole DF, but we only got names.
            # Let's read it properly here.
            try:
                import pandas as pd
                existing_df = pd.read_excel("stargazers.xlsx")
                new_df = pd.DataFrame(stargazers)
                
                # Rename columns for new data to match export format
                columns_map = {
                    "login": "Username", "name": "Name", "email": "GitHub Email",
                    "scraped_email": "Scraped Email", "blog": "Website",
                    "company": "Company", "location": "Location",
                    "twitter_username": "Twitter", "scraped_linkedin": "LinkedIn",
                    "html_url": "GitHub Profile"
                }
                valid_cols = [c for c in columns_map.keys() if c in new_df.columns]
                new_df = new_df[valid_cols].rename(columns=columns_map)
                
                # Concatenate
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df.to_excel("stargazers.xlsx", index=False)
                print(f"Merged {len(new_df)} new records. Total records: {len(combined_df)}")
                return # Skip default export
            except Exception as e:
                print(f"Failed to merge with existing file: {e}")
                print("Saving to stargazers_new.xlsx instead.")
                export_to_excel(stargazers, "stargazers_new.xlsx")
                return

        export_to_excel(stargazers, "stargazers.xlsx")
    else:
        print("No new stargazers found.")

if __name__ == "__main__":
    asyncio.run(main())
