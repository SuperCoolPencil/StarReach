import asyncio
import os
import pandas as pd
from scraper import ProfileScraper
from exporter import export_to_excel, load_existing_users
from playwright.async_api import async_playwright

async def verify():
    print("Starting verification (Enhanced Scraping - All Data)...")
    
    scraper = ProfileScraper()

    # 1. Test Text Extraction (Multi-social)
    bio_text = """
    Software Engineer | Contact: test@bio.com 
    Find me on:
    linkedin.com/in/bio-user
    twitter.com/dev_twitter
    instagram.com/dev_insta
    youtube.com/c/dev_channel
    bsky.app/profile/dev.bsky.social
    """
    extracted = scraper.extract_from_text(bio_text)
    
    checks = {
        "scraped_email": "test@bio.com",
        "scraped_twitter": "https://x.com/dev_twitter",
        "scraped_instagram": "https://instagram.com/dev_insta",
        "scraped_youtube": "https://youtube.com/dev_channel",
        "scraped_bluesky": "https://bsky.app/profile/dev.bsky.social"
    }
    
    all_passed = True
    for key, expected in checks.items():
        if extracted.get(key) != expected:
            print(f"❌ {key} failed. Expected {expected}, got {extracted.get(key)}")
            all_passed = False
    
    if all_passed:
        print("✅ Multi-social extraction verified.")

    # 2. Test Generic URL Scraping (Localhost)
    if not os.path.exists("test_site"):
        os.makedirs("test_site")
    
    html_content = """
    <html><body>
        <p>Contact: page@example.com</p>
        <a href="https://www.linkedin.com/in/page-user">LinkedIn</a>
        <a href="https://twitter.com/page_twitter">Twitter</a>
        <a href="https://facebook.com/page_fb">Facebook</a>
    </body></html>
    """
    
    with open("test_site/index.html", "w") as f:
         f.write(html_content)
    
    abs_path = os.path.abspath("test_site/index.html")
    file_url = f"file://{abs_path}"
    
    print(f"Scraping {file_url}...")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            scraped_data = await scraper.scrape_url(context, file_url)
            
            # Check all fields
            passed = True
            if scraped_data.get("scraped_email") != "page@example.com":
                 print(f"❌ Email mismatch: {scraped_data.get('scraped_email')}")
                 passed = False
            if scraped_data.get("scraped_twitter") != "https://x.com/page_twitter":
                 print(f"❌ Twitter mismatch: {scraped_data.get('scraped_twitter')}")
                 passed = False
            if scraped_data.get("scraped_facebook") != "https://facebook.com/page_fb":
                 print(f"❌ Facebook mismatch: {scraped_data.get('scraped_facebook')}")
                 passed = False
            if scraped_data.get("scraped_linkedin") != "https://www.linkedin.com/in/page-user":
                 print(f"❌ LinkedIn mismatch: {scraped_data.get('scraped_linkedin')}")
                 passed = False

            if passed:
                 print("✅ Generic URL scraping verified.")

            await browser.close()
    except Exception as e:
        print(f"Playwright verification error: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
