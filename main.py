import requests
import pandas as pd
import re
import time
import os
import base64
import concurrent.futures
from collections import deque
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- CONFIGURATION ---
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO = 'surge-downloader/surge'
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}
TIMEOUT = 15  # Seconds to wait for a blog to load
CRAWL_MAX_DEPTH = 5  # Max link-follow depth for blog crawling
CRAWL_MAX_PAGES = 25  # Max pages to visit per blog

# --- LinkedIn URL pattern ---
LINKEDIN_RE = re.compile(
    r'https?://(?:www\.)?linkedin\.com/(in|pub|company|profile/view)\b[^\s\'"<>]*',
    re.IGNORECASE,
)


def is_linkedin_url(url):
    """Check if a URL is a LinkedIn profile/company/pub URL."""
    return bool(LINKEDIN_RE.search(url))


def extract_linkedin_url(text):
    """Extract the first LinkedIn URL from a block of text."""
    match = LINKEDIN_RE.search(text)
    return match.group(0) if match else None


def get_stargazers(repo):
    """Fetches all stargazers for a repo."""
    stargazers = []
    page = 1
    while True:
        url = f'https://api.github.com/repos/{repo}/stargazers?page={page}&per_page=100'
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code != 200:
                print(f"Error fetching stargazers: {response.json()}")
                break
            
            users = response.json()
            if not users:
                break
            
            for user in users:
                stargazers.append(user['login'])
            
            print(f"Fetched page {page} ({len(users)} users)...")
            page += 1
        except Exception as e:
            print(f"API Error: {e}")
            break
            
    return stargazers


def get_user_profile(username):
    """Fetches public profile data from GitHub."""
    url = f'https://api.github.com/users/{username}'
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"  [!] Error fetching profile for {username}: {e}")
    return None


def get_social_accounts(username):
    """Fetches social accounts from GitHub."""
    url = f'https://api.github.com/users/{username}/social_accounts'
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"  [!] Error fetching social accounts for {username}: {e}")
    return []


def get_readme_linkedin(username):
    """
    Fetches the profile README (username/username repo) and scans it
    for LinkedIn URLs. Returns the first match or None.
    """
    url = f'https://api.github.com/repos/{username}/{username}/readme'
    try:
        response = requests.get(url, headers={
            **HEADERS,
            'Accept': 'application/vnd.github.raw+json',
        })
        if response.status_code == 200:
            readme_text = response.text
            linkedin = extract_linkedin_url(readme_text)
            if linkedin:
                return linkedin
    except Exception as e:
        print(f"  [!] Error fetching README for {username}: {e}")
    return None


def crawl_site_for_linkedin(start_url, max_depth=CRAWL_MAX_DEPTH, max_pages=CRAWL_MAX_PAGES):
    """
    BFS-crawl a website up to `max_depth` link-hops and `max_pages` total
    pages, looking for LinkedIn URLs. Only follows same-domain links.
    Returns the first LinkedIn URL found, or None.
    """
    if not start_url:
        return None

    # Ensure URL has schema
    if not start_url.startswith(('http://', 'https://')):
        start_url = 'http://' + start_url

    parsed_start = urlparse(start_url)
    base_domain = parsed_start.netloc.lower()

    visited = set()
    queue = deque()  # (url, depth)
    queue.append((start_url, 0))

    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/91.0.4472.124 Safari/537.36'
    }

    while queue and len(visited) < max_pages:
        current_url, depth = queue.popleft()

        if current_url in visited:
            continue
        visited.add(current_url)

        print(f"   --> Crawling (depth {depth}) {current_url}")

        try:
            response = requests.get(current_url, headers=request_headers, timeout=TIMEOUT)
            if response.status_code != 200:
                continue
        except Exception:
            continue

        soup = BeautifulSoup(response.text, 'html.parser')

        # Check every link on this page
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute = urljoin(current_url, href)

            # Check if this link itself is a LinkedIn URL
            if is_linkedin_url(absolute):
                return absolute

            # Queue same-domain links for further crawling
            if depth < max_depth:
                parsed = urlparse(absolute)
                if parsed.netloc.lower() == base_domain and absolute not in visited:
                    queue.append((absolute, depth + 1))

        # Also scan raw page text for LinkedIn URLs not wrapped in <a> tags
        text_match = extract_linkedin_url(response.text)
        if text_match:
            return text_match

    return None


def process_user(username):
    """Process a single user and return their info dict."""
    try:
        print(f"Checking {username}...")
        profile = get_user_profile(username)

        if not profile:
            return None

        blog_url = profile.get('blog')
        linkedin_url = None
        linkedin_source = None

        # --- Gather all social account URLs ---
        socials = get_social_accounts(username)
        all_social_urls = [s.get('url', '') for s in socials if s.get('url')]

        # 1) Check social accounts for LinkedIn
        for social in socials:
            if is_linkedin_url(social.get('url', '')):
                linkedin_url = social['url']
                linkedin_source = 'social'
                print(f"   --> Found LinkedIn for {username} (social): {linkedin_url}")
                break

        # 2) If not found in socials, and they have a blog, crawl it
        if not linkedin_url and blog_url:
            linkedin_url = crawl_site_for_linkedin(blog_url)
            if linkedin_url:
                linkedin_source = 'blog'
                print(f"   --> Found LinkedIn for {username} (blog crawl): {linkedin_url}")

        # 3) If still not found, try the profile README
        if not linkedin_url:
            linkedin_url = get_readme_linkedin(username)
            if linkedin_url:
                linkedin_source = 'readme'
                print(f"   --> Found LinkedIn for {username} (README): {linkedin_url}")

        # Respectful pause (per thread)
        time.sleep(0.2)

        return {
            'Username': username,
            'Name': profile.get('name'),
            'Bio': profile.get('bio'),
            'Company': profile.get('company'),
            'Location': profile.get('location'),
            'Email': profile.get('email'),
            'Hireable': profile.get('hireable'),
            'Twitter': profile.get('twitter_username'),
            'Website': blog_url,
            'Found_LinkedIn': linkedin_url,
            'LinkedIn_Source': linkedin_source,
            'All_Social_Links': ', '.join(all_social_urls) if all_social_urls else None,
            'Followers': profile.get('followers'),
            'Following': profile.get('following'),
            'Public_Repos': profile.get('public_repos'),
            'Public_Gists': profile.get('public_gists'),
            'Avatar_URL': profile.get('avatar_url'),
            'Created_At': profile.get('created_at'),
            'Updated_At': profile.get('updated_at'),
            'GitHub_URL': profile.get('html_url'),
        }
    except Exception as e:
        print(f"Error processing {username}: {e}")
    return None


def main():
    print(f"Starting crawl for {REPO}...")
    stargazers = get_stargazers(REPO)

    final_data = []
    processed_usernames = set()

    # Load existing data if available to resume
    if os.path.exists('surge_leads.xlsx'):
        print("Found existing 'surge_leads.xlsx', loading to resume...")
        try:
            existing_df = pd.read_excel('surge_leads.xlsx')
            if 'Username' in existing_df.columns:
                processed_usernames = set(existing_df['Username'].tolist())
                final_data = existing_df.to_dict('records')
                print(f"Loaded {len(final_data)} existing records.")
        except Exception as e:
            print(f"Could not load existing file: {e}")

    # Filter out already processed users
    users_to_process = [u for u in stargazers if u not in processed_usernames]
    total = len(users_to_process)

    if total == 0:
        print("All users already processed!")
        return

    print(f"\nProcessing {total} new profiles (skipped {len(processed_usernames)}).")
    print("Press Ctrl+C to stop and save progress.\n")

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    try:
        # Submit all tasks
        future_to_user = {executor.submit(process_user, user): user for user in users_to_process}

        completed_count = 0
        for future in concurrent.futures.as_completed(future_to_user):
            user = future_to_user[future]
            try:
                result = future.result()
                if result:
                    final_data.append(result)

                completed_count += 1
                if completed_count % 10 == 0:
                    print(f"Progress: {completed_count}/{total}")

            except Exception as exc:
                print(f'{user} generated an exception: {exc}')

    except KeyboardInterrupt:
        print("\n\nStopping script (KeyboardInterrupt)...")
        print("Cancelling pending tasks...")
        executor.shutdown(wait=False, cancel_futures=True)
        print("Waiting for currently running tasks to finish (max 5)...")
    except Exception as e:
        print(f"\n\nAn unexpected error occurred: {e}")
    finally:
        # Ensure executor is closed
        executor.shutdown(wait=True)

        # Export
        print("\nSaving to Excel...")
        if final_data:
            df = pd.DataFrame(final_data)

            # Reorder columns — most important stuff first
            cols = [
                'Name', 'Found_LinkedIn', 'LinkedIn_Source', 'Bio',
                'Company', 'Email', 'Hireable', 'Twitter', 'Website',
                'All_Social_Links', 'Followers', 'Following',
                'Public_Repos', 'Public_Gists',
                'Username', 'GitHub_URL', 'Avatar_URL',
                'Created_At', 'Updated_At',
            ]
            # Filter to only include cols that actually exist
            cols = [c for c in cols if c in df.columns]
            # Add remaining columns not in our preferred order
            df = df[cols + [c for c in df.columns if c not in cols]]

            df.to_excel('surge_leads.xlsx', index=False)
            print(f"Done! Saved {len(df)} records to 'surge_leads.xlsx'.")
        else:
            print("No data to save.")


if __name__ == '__main__':
    main()