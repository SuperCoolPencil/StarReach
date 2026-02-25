import requests
import json
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Use the token from main.py if available, otherwise just try unauthenticated (might get rate limited)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
HEADERS = {'Authorization': f'token {GITHUB_TOKEN}'} if GITHUB_TOKEN else {}

def check_user(username):
    url = f'https://api.github.com/users/{username}'
    print(f"Checking {url}...")
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            print("--- Main Profile Data ---")
            # Print keys to differeniate main vs social
            print(data.keys())
            if 'social_accounts' in data:
                 print("\nSocial Accounts found in main response:")
                 print(json.dumps(data['social_accounts'], indent=2))
            else:
                 print("\nNo 'social_accounts' key in main response.")

            # Check dedicated endpoint
            social_url = f'https://api.github.com/users/{username}/social_accounts'
            print(f"\nChecking {social_url}...")
            resp_social = requests.get(social_url, headers=HEADERS)
            if resp_social.status_code == 200:
                print("--- Social Accounts Endpoint Data ---")
                print(json.dumps(resp_social.json(), indent=2))
            else:
                print(f"Social accounts endpoint returned {resp_social.status_code}")

        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    # Test with a user who likely has social accounts.
    # 'fabpot' (Symfony creator) or 'antitez' (Redis) or 'torvalds' (Linux) - but let's try someone more likely to have LinkedIn
    # 'sindresorhus' is very active.
    # Start with 'sindresorhus'
    check_user('sindresorhus')
