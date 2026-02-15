import os
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

    def get_stargazers(self, repo_url: str) -> Generator[Dict, None, None]:
        """
        Fetches stargazers for a given repository URL.
        Yields each stargazer's profile data.
        """
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/repos/{owner}/{repo}/stargazers"
        
        while url:
            try:
                response = self.session.get(url, headers=self.headers, params={"per_page": 100}, timeout=10)
                if response.status_code != 200:
                    print(f"Error fetching stargazers: {response.status_code} - {response.text}")
                    break
                
                users = response.json()
                if not users:
                    break
                    
                for user in users:
                    # Get detailed user info to find public email/blog
                    user_details = self.get_user_details(user["url"])
                    if user_details:
                        yield user_details
                
                # Pagination
                if "next" in response.links:
                    url = response.links["next"]["url"]
                else:
                    url = None
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")
                break

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
