import os
import asyncio
import argparse
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from github_client import GitHubClient
from scraper import ProfileScraper
from exporter import export_to_excel

async def process_user(user, scraper, context, sem):
    """
    Process a single user: scrape additional info if blog/website is present.
    """
    blog = user.get("blog")
    if blog:
        # Use semaphore to limit concurrent browser tabs
        async with sem:
            # print(f"Scraping website for {user.get('login')}: {blog}")
            try:
                scraped_data = await scraper.scrape_user_website(context, blog)
                # user is a dict, modification in place is fine or return new dict
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
    
    stargazers = []
    
    # We'll use a semaphore to limit concurrent browser pages
    sem = asyncio.Semaphore(5) 

    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (compatible; StarReach/1.0)",
            viewport={"width": 1280, "height": 720}
        )
        
        # Block resources to save bandwidth and speed up loading
        await context.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script"] else route.abort())

        # Fetch users from GitHub
        user_generator = client.get_stargazers(args.repo_url)
        
        tasks = []
        count = 0
        total_fetched = 0
        
        try:
            for user in user_generator:
                if args.limit and total_fetched >= args.limit:
                    break
                
                # Create a task for processing this user
                tasks.append(process_user(user, scraper, context, sem))
                total_fetched += 1
                
                # Execute in batches to keep memory usage low and provide feedback
                if len(tasks) >= 20:
                    print(f"Processing batch of {len(tasks)} (Total fetched: {total_fetched})...")
                    batch_results = await asyncio.gather(*tasks)
                    stargazers.extend(batch_results)
                    tasks = []
            
            # Process any remaining tasks
            if tasks:
                print(f"Processing final batch of {len(tasks)}...")
                batch_results = await asyncio.gather(*tasks)
                stargazers.extend(batch_results)
                
        except Exception as e:
            print(f"An error occurred during processing: {e}")
        finally:
            await browser.close()

    print(f"Total users processed: {len(stargazers)}")
    
    # Export
    if stargazers:
        print("Exporting data to stargazers.xlsx...")
        export_to_excel(stargazers, "stargazers.xlsx")
        print("Done!")
    else:
        print("No stargazers found or processed.")

if __name__ == "__main__":
    asyncio.run(main())
