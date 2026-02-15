import re
import asyncio
from typing import Dict, Optional
from playwright.async_api import BrowserContext, Page

class ProfileScraper:
    def __init__(self):
        self.email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        self.linkedin_regex = re.compile(r"linkedin\.com/in/[a-zA-Z0-9-]+")

    def extract_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extracts email and linkedin from raw text.
        """
        data = {"scraped_email": None, "scraped_linkedin": None}
        if not text:
            return data
            
        emails = self.email_regex.findall(text)
        linkedins = self.linkedin_regex.findall(text)

        if emails:
            data["scraped_email"] = emails[0]
        if linkedins:
            # Clean up partial match if needed, but regex looks for linkedin.com/in/...
            data["scraped_linkedin"] = "https://www." + linkedins[0] if not linkedins[0].startswith("http") else linkedins[0]
            
        return data

    async def scrape_url(self, context: BrowserContext, url: str) -> Dict[str, Optional[str]]:
        """
        Visits a URL (personal site, github profile, etc) to find contact info.
        """
        if not url.startswith("http"):
            url = "http://" + url

        data = {"scraped_email": None, "scraped_linkedin": None}
        page = await context.new_page()
        
        try:
            # Short timeout to avoid hanging
            await page.goto(url, timeout=10000, wait_until="domcontentloaded")
            content = await page.content()
            data = self.extract_from_text(content)

        except Exception as e:
            # Logging handled by caller usually, or we can just pass
            pass
        finally:
            await page.close()
        
        return data

    # Alias for backward compatibility if needed, using new logic
    async def scrape_user_website(self, context: BrowserContext, url: str) -> Dict[str, Optional[str]]:
        return await self.scrape_url(context, url)
