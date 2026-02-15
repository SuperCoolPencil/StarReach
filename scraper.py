import re
import asyncio
from typing import Dict, Optional
from playwright.async_api import BrowserContext, Page

class ProfileScraper:
    def __init__(self):
        self.email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        self.linkedin_regex = re.compile(r"linkedin\.com/in/[a-zA-Z0-9-]+")

    async def scrape_user_website(self, context: BrowserContext, url: str) -> Dict[str, Optional[str]]:
        """
        Visits a user's personal website using the provided browser context.
        Return dict with email and linkedin if found.
        """
        if not url.startswith("http"):
            url = "http://" + url

        data = {"scraped_email": None, "scraped_linkedin": None}
        page = await context.new_page()
        
        try:
            # Short timeout to avoid hanging on slow sites
            await page.goto(url, timeout=10000, wait_until="domcontentloaded")
            content = await page.content()
            
            emails = self.email_regex.findall(content)
            linkedins = self.linkedin_regex.findall(content)

            if emails:
                data["scraped_email"] = emails[0]
            if linkedins:
                data["scraped_linkedin"] = "https://www." + linkedins[0]

        except Exception as e:
            # Verify verbose logging if needed, otherwise keep silent on failures
            # print(f"Failed to scrape {url}: {e}")
            pass
        finally:
            await page.close()
        
        return data
