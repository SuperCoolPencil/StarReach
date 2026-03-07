import pandas as pd
from playwright.sync_api import sync_playwright
import os
import argparse

# The message you wanted to send (printed for easy copying)
MESSAGE = """Hey, thanks for the star on Surge!

I'm the creator (2nd year at IIITG). I'm currently looking for a summer internship where I can build more backend/swe projects. 

If you, your team, or anyone you know is looking for an intern, I'd love to connect!"""


def detect_connection_status(page, timeout_ms=5000):
    """
    Detect the LinkedIn connection status for the currently loaded profile.

    Returns one of:
        'connect'  — not connected, show the message prompt
        'pending'  — connection request already sent
        'connected' — already connected (Message button visible)
        'unknown'  — could not determine
    """
    try:
        # Wait for the profile actions section to load
        page.wait_for_selector('div.pvs-profile-actions', timeout=timeout_ms)
    except Exception:
        # Fallback: the page structure may differ (e.g. company pages)
        return 'unknown'

    actions = page.query_selector('div.pvs-profile-actions')
    if not actions:
        return 'unknown'

    buttons_text = actions.inner_text().lower()

    if 'pending' in buttons_text:
        return 'pending'
    if 'message' in buttons_text and 'connect' not in buttons_text:
        return 'connected'
    if 'connect' in buttons_text:
        return 'connect'
    if 'follow' in buttons_text:
        return 'follow'

    return 'unknown'


def main():
    parser = argparse.ArgumentParser(description="LinkedIn Viewer")
    parser.add_argument("--offset", type=int, default=0, help="Start from this index (0-based)")
    parser.add_argument("--no-skip", action="store_true", help="Don't auto-skip any profiles")
    args = parser.parse_args()

    excel_file = 'surge_leads.xlsx'
    
    if not os.path.exists(excel_file):
        print(f"Error: Could not find '{excel_file}'. Run the crawler script first!")
        return

    # Load the data
    df = pd.read_excel(excel_file)
    
    # Filter for rows that actually have a LinkedIn URL found
    if 'Found_LinkedIn' not in df.columns:
        print("Error: 'Found_LinkedIn' column not found in Excel.")
        return
        
    leads = df[df['Found_LinkedIn'].notna()]
    urls = leads['Found_LinkedIn'].tolist()
    names = leads['Name'].tolist()
    
    total_leads = len(urls)
    offset = args.offset

    if offset > 0:
        if offset >= total_leads:
            print(f"Error: Offset {offset} is out of bounds (Total: {total_leads})")
            return
        print(f"Skipping first {offset} profiles. Starting from {offset + 1}.")
        urls = urls[offset:]
        names = names[offset:]

    if not urls:
        print("No LinkedIn URLs found in the Excel file.")
        return

    print(f"Found {len(urls)} profiles to process.")
    if not args.no_skip:
        print("Auto-skipping profiles with pending/accepted connections.")
        print("Use --no-skip to disable this.\n")

    skipped = 0
    processed = 0

    with sync_playwright() as p:
        # Launch browser (headless=False means you can see it)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print("\n--- STEP 1: LOGIN ---")
        print("The browser is now open.")
        print("1. Go to the browser window.")
        print("2. Log in to LinkedIn manually.")
        print("3. Handle any 2FA/captchas.")
        input("\n>>> Press ENTER here once you are logged in and ready to start <<<")

        print("\n--- STEP 2: OUTREACH ---")
        
        for i, url in enumerate(urls):
            name = names[i] if pd.notna(names[i]) else "there"
            current_idx = i + offset + 1
            
            print(f"\n[{current_idx}/{total_leads}] Opening profile for: {name}")
            print(f"URL: {url}")
            
            try:
                page.goto(url, wait_until='domcontentloaded')
                # Small wait for dynamic content to render
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"Could not load page: {e}")
                continue

            # Detect connection status and auto-skip if appropriate
            if not args.no_skip:
                status = detect_connection_status(page)

                if status == 'pending':
                    skipped += 1
                    print(f"   ⏭  SKIPPED — connection request already pending")
                    continue
                elif status == 'connected':
                    skipped += 1
                    print(f"   ⏭  SKIPPED — already connected")
                    continue
                elif status == 'connect':
                    print(f"   ✅ Not connected yet — ready for outreach")
                elif status == 'follow':
                    print(f"   ✅ Follow profile — use More > Connect to send request")
                elif status == 'unknown':
                    print(f"   ⚠️  Could not detect status — showing anyway")

            processed += 1
            print("-" * 50)
            print("MESSAGE TO COPY:")
            print(MESSAGE)
            print("-" * 50)
            
            user_input = input(">>> Press ENTER for next profile (or type 'q' to quit): ")
            if user_input.lower() == 'q':
                break

        print(f"\nFinished! Processed: {processed}, Skipped: {skipped}. Closing browser.")
        browser.close()


if __name__ == "__main__":
    main()