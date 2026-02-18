import requests
import pandas as pd
import time
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# --- CONFIGURATION ---
GITHUB_TOKEN = '***REMOVED***'  # Replace with your actual token
REPO = 'surge-downloader/surge'
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'}
TIMEOUT = 5  # Seconds to wait for a blog to load

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
    except:
        pass
    return None

def get_social_accounts(username):
    """Fetches social accounts from GitHub."""
    url = f'https://api.github.com/users/{username}/social_accounts'
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []

def find_linkedin_on_website(website_url):
    """
    Visits a personal website and looks for a LinkedIn URL.
    Returns the first LinkedIn URL found, or None.
    """
    if not website_url:
        return None
    
    # Ensure URL has schema
    if not website_url.startswith(('http://', 'https://')):
        website_url = 'http://' + website_url

    print(f"   --> Crawling {website_url}...")
    
    try:
        # User-Agent is important so blogs don't block the bot immediately
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(website_url, headers=headers, timeout=TIMEOUT)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com/in/' in href:
                    return href
    except Exception as e:
        # specific errors like timeouts are normal for old/dead blogs
        pass
        
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

    print(f"\nProcessing {total} new profiles (skipped {len(processed_usernames)}). This might take a minute depending on their blog speeds.\n")
    print("Press Ctrl+C to stop and save progress.\n")
    
    try:
        for i, username in enumerate(users_to_process):
            print(f"[{i+1}/{total}] Checking {username}...")
            
            profile = get_user_profile(username)
            
            if profile:
                blog_url = profile.get('blog')
                linkedin_url = None
                
                # Check social accounts for LinkedIn
                socials = get_social_accounts(username)
                for social in socials:
                    if 'linkedin.com/in/' in social['url']:
                        linkedin_url = social['url']
                        print(f"   --> Found LinkedIn in social accounts: {linkedin_url}")
                        break

                # If not found in socials, and they have a blog, crawl it
                if not linkedin_url and blog_url:
                    linkedin_url = find_linkedin_on_website(blog_url)
                
                user_info = {
                    'Username': username,
                    'Name': profile.get('name'),
                    'Company': profile.get('company'),
                    'Location': profile.get('location'),
                    'Email': profile.get('email'), # Only if public
                    'Twitter': profile.get('twitter_username'),
                    'Website': blog_url,
                    'Found_LinkedIn': linkedin_url,
                    'GitHub_URL': profile.get('html_url')
                }
                final_data.append(user_info)
            
            # Respectful pause to avoid hitting GitHub API limits too hard
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\n\nStopping script (KeyboardInterrupt)...")
    except Exception as e:
        print(f"\n\nAn unexpected error occurred: {e}")
    finally:
        # Export
        print("\nSaving to Excel...")
        if final_data:
            df = pd.DataFrame(final_data)
            
            # Reorder columns to put mostly important stuff first
            cols = ['Name', 'Found_LinkedIn', 'Company', 'Email', 'Twitter', 'Website', 'Username', 'GitHub_URL']
            # Filter to only include cols that actually exist in the dataframe
            cols = [c for c in cols if c in df.columns] 
            
            # Add remaining columns
            df = df[cols + [c for c in df.columns if c not in cols]]
            
            df.to_excel('surge_leads.xlsx', index=False)
            print(f"Done! Saved {len(df)} records to 'surge_leads.xlsx'.")
        else:
            print("No data to save.")

if __name__ == '__main__':
    main()