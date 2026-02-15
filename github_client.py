import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict, Generator

class GitHubClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def fetch_stargazers_page(self, url: str) -> tuple[List[Dict], str | None, int]:
        """
        Fetches a single page of stargazers.
        Returns: (list_of_users, next_page_url, retry_after_seconds)
        - If success: (users, next_url, 0)
        - If rate limit: ([], url, retry_time)
        - If error: ([], None, 0)
        """
        try:
            response = self.session.get(url, headers=self.headers, params={"per_page": 100}, timeout=10)
            
            if response.status_code == 200:
                users = response.json()
                next_url = None
                if "next" in response.links:
                    next_url = response.links["next"]["url"]
                return users, next_url, 0
            
            if response.status_code in [403, 429]:
                retry_after = int(response.headers.get("Retry-After", 60))
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                sleep_time = retry_after
                if reset_time:
                     current_time = time.time()
                     sleep_time = max(sleep_time, int(reset_time - current_time + 1))
                return [], url, sleep_time
            
            print(f"Error fetching stargazers: {response.status_code} - {response.text}")
            return [], None, 0
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return [], url, 5 # Retry same URL after 5s on network error

    def get_stargazers(self, repo_url: str, fetch_details: bool = True) -> Generator[Dict, None, None]:
        """
        Fetches stargazers for a given repository URL.
        Yields each stargazer's profile data.
        NOTE: This is blocking! Use fetch_stargazers_page for async-friendly version.
        """
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/repos/{owner}/{repo}/stargazers"
        
        while url:
            # Robust retry loop for the request itself
            while True:
                users, next_url, retry_after = self.fetch_stargazers_page(url)
                
                if retry_after > 0:
                    print(f"Rate limit hit. Sleeping for {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                
                if not users and not next_url:
                     # Error or done
                     if not users: return # If users empty and no next_url, likely done or error
                     # If we got users but no next_url, we process users and break outer
                
                if not users: # Error case passed as empty list
                    return 

                break # Got users

            for user in users:
                if fetch_details:
                    # Get detailed user info to find public email/blog
                    user_details = self.get_user_details(user["url"])
                    if user_details:
                        yield user_details
                else:
                    yield user
            
            url = next_url

    def get_user_details(self, user_url: str) -> Dict:
        """
        Fetches detailed information for a specific user.
        """
        try:
            response = self.session.get(user_url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch user details for {user_url}: {e}")
        return {}

    def _parse_repo_url(self, repo_url: str) -> (str, str):
        """
        Extracts owner and repo name from a GitHub URL.
        Example: https://github.com/owner/repo -> (owner, repo)
        """
        parts = repo_url.rstrip("/").split("/")
        if len(parts) >= 2:
            return parts[-2], parts[-1]
        raise ValueError("Invalid GitHub Repository URL")

if __name__ == "__main__":
    # Test execution
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv("GITHUB_TOKEN")
    if token:
        client = GitHubClient(token)
        # Test with a small repo or limited output
        # for user in client.get_stargazers("https://github.com/octocat/Hello-World"):
        #     print(user.get("login"), user.get("email"))
    else:
        print("Please set GITHUB_TOKEN in .env")
