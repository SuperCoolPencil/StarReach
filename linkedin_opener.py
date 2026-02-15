import pandas as pd
from playwright.sync_api import sync_playwright
import sys

def main():
    excel_file = 'stargazers.xlsx'
    
    try:
        df = pd.read_excel(excel_file)
    except FileNotFoundError:
        print(f"Error: Could not find {excel_file}")
        return
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return

    if 'LinkedIn' not in df.columns:
        print("Error: 'LinkedIn' column not found in the Excel file.")
        print(f"Available columns: {df.columns.tolist()}")
        return

    # Filter for valid LinkedIn URLs (not NaN and contains 'linkedin.com')
    linkedin_urls = df['LinkedIn'].dropna()
    linkedin_urls = linkedin_urls[linkedin_urls.str.contains('linkedin.com', case=False)].tolist()

    if not linkedin_urls:
        print("No valid LinkedIn URLs found.")
        return

    print(f"Found {len(linkedin_urls)} LinkedIn URLs. Starting...")

    with sync_playwright() as p:
        # Launch browser in headed mode so the user can see and interact
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        for i, url in enumerate(linkedin_urls):
            print(f"[{i+1}/{len(linkedin_urls)}] Opening: {url}")
            print("Close the tab to proceed to the next profile...")
            
            try:
                page = context.new_page()
                page.goto(url)
                
                # Wait for the user to close the page (tab)
                # If the user closes the browser window, this might raise an error
                # 10 minutes timeout (600,000 ms)
                page.wait_for_event("close", timeout=600000)
                
            except Exception as e:
                print(f"Context closed or error occurred: {e}")
                break
        
        print("All URLs processed or execution stopped.")
        try:
            browser.close()
        except:
            pass

if __name__ == "__main__":
    main()
