import re
import asyncio
from typing import Dict, Optional
from playwright.async_api import BrowserContext, Page

class ProfileScraper:
    def __init__(self):
        self.email_regex = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        self.linkedin_regex = re.compile(r"linkedin\.com/in/[a-zA-Z0-9-]+")
        self.twitter_regex = re.compile(r"(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)")
        self.facebook_regex = re.compile(r"facebook\.com/([a-zA-Z0-9._]+)")
        self.instagram_regex = re.compile(r"instagram\.com/([a-zA-Z0-9_.]+)")
        self.youtube_regex = re.compile(r"youtube\.com/(?:c/|channel/|user/|@)?([a-zA-Z0-9_-]+)")
        self.bluesky_regex = re.compile(r"bsky\.app/profile/([a-zA-Z0-9.-]+)")

    def extract_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extracts email and social links from raw text.
        """
        data = {
            "scraped_email": None, 
            "scraped_linkedin": None,
            "scraped_twitter": None,
            "scraped_facebook": None,
            "scraped_instagram": None,
            "scraped_youtube": None,
            "scraped_bluesky": None
        }
        if not text:
            return data
            
        emails = self.email_regex.findall(text)
        linkedins = self.linkedin_regex.findall(text)
        twitters = self.twitter_regex.findall(text)
        facebooks = self.facebook_regex.findall(text)
        instagrams = self.instagram_regex.findall(text)
        youtubes = self.youtube_regex.findall(text)
        blueskies = self.bluesky_regex.findall(text)

        if emails:
            data["scraped_email"] = emails[0]
        if linkedins:
            data["scraped_linkedin"] = "https://www." + linkedins[0] if not linkedins[0].startswith("http") else linkedins[0]
        if twitters:
            data["scraped_twitter"] = f"https://x.com/{twitters[0]}"
        if facebooks:
            data["scraped_facebook"] = f"https://facebook.com/{facebooks[0]}"
        if instagrams:
            data["scraped_instagram"] = f"https://instagram.com/{instagrams[0]}"
        if youtubes:
            data["scraped_youtube"] = f"https://youtube.com/{youtubes[0]}"
        if blueskies:
            data["scraped_bluesky"] = f"https://bsky.app/profile/{blueskies[0]}"

        return data

    async def scrape_url(self, context: BrowserContext, url: str) -> Dict[str, Optional[str]]:
        """
        Visits a URL (personal site, github profile, etc) to find contact info.
        """
        if not (url.startswith("http") or url.startswith("file")):
            url = "http://" + url

        data = {"scraped_email": None, "scraped_linkedin": None}
        page = None
        
        try:
            # Enforce a strict total timeout for the entire operation including new_page
            async with asyncio.timeout(30):
                page = await context.new_page()
                
                # logging.debug(f"Navigating to {url}...")
                await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                content = await page.content()
                data = self.extract_from_text(content)

        except asyncio.TimeoutError:
            # Re-raise timeout error so worker can handle it
            raise
        except Exception as e:
            # Re-raise other errors
            raise
        finally:
            if page:
                try:
                    # Protect against page.close() hanging
                    async with asyncio.timeout(2):
                        await page.close()
                except Exception:
                    pass
        
        return data

    # Alias for backward compatibility if needed, using new logic
    async def scrape_user_website(self, context: BrowserContext, url: str) -> Dict[str, Optional[str]]:
        return await self.scrape_url(context, url)
