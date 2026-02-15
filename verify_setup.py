import asyncio
import os
import pandas as pd
from scraper import ProfileScraper
from exporter import export_to_excel, load_existing_users
from playwright.async_api import async_playwright

async def verify():
    print("Starting verification (Enhanced Scraping)...")
    
    scraper = ProfileScraper()

    # 1. Test Text Extraction
    bio_text = "Software Engineer | Contact: test@bio.com | linkedin.com/in/bio-user"
    extracted = scraper.extract_from_text(bio_text)
    if extracted["scraped_email"] == "test@bio.com" and "bio-user" in extracted["scraped_linkedin"]:
        print("✅ Text/Bio extraction verified.")
    else:
        print(f"❌ Text/Bio extraction failed. Got: {extracted}")

    # 2. Test Generic URL Scraping (Localhost)
    # We assume localhost:8080 is still running or we skip
    mock_url = "http://localhost:8080/index.html"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            print(f"Scraping {file_url}...")
            # We assume the file exists from previous step, or we create it?
            if not os.path.exists("test_site"):
                os.makedirs("test_site")
            
            with open("test_site/index.html", "w") as f:
                 f.write('<html><body><p>Contact: page@example.com</p><a href="https://www.linkedin.com/in/page-user">LinkedIn</a></body></html>')
            
            abs_path = os.path.abspath("test_site/index.html")
            file_url = f"file://{abs_path}"
            
            scraped_data = await scraper.scrape_url(context, file_url)
            
            if scraped_data.get("scraped_email") == "page@example.com":
                 print("✅ Generic URL scraping verified.")
            else:
                 print(f"❌ Generic URL scraping failed. Got: {scraped_data}")

            await browser.close()
    except Exception as e:
        print(f"Playwright verification error: {e}")

if __name__ == "__main__":
    # Ensure test dir exists
    if not os.path.exists("test_site"):
        os.makedirs("test_site")
    asyncio.run(verify())
