import pandas as pd
from playwright.sync_api import sync_playwright
import os

# The message you wanted to send (printed for easy copying)
MESSAGE = """Hey, thanks for the star on Surge!

I'm the creator (2nd year at IIITG). I'm currently looking for a summer internship where I can build more backend/swe projects. 

If you, your team, or anyone you know is looking for an intern, I'd love to connect!"""

def main():
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

    if not urls:
        print("No LinkedIn URLs found in the Excel file.")
        return

    print(f"Found {len(urls)} profiles to process.")

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
            
            print(f"\n[{i+1}/{len(urls)}] Opening profile for: {name}")
            print(f"URL: {url}")
            
            try:
                page.goto(url)
            except Exception as e:
                print(f"Could not load page: {e}")
                continue

            print("-" * 50)
            print("MESSAGE TO COPY:")
            print(MESSAGE)
            print("-" * 50)
            
            user_input = input(">>> Press ENTER for next profile (or type 'q' to quit): ")
            if user_input.lower() == 'q':
                break

        print("Finished processing list. Closing browser.")
        browser.close()

if __name__ == "__main__":
    main()