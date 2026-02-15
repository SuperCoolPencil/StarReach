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

    start_offset = 0
    if len(sys.argv) > 1:
        try:
            start_offset = int(sys.argv[1])
        except ValueError:
            print("Invalid offset provided. Usage: python linkedin.py [offset]")
            
    if start_offset >= len(linkedin_urls):
        print(f"Offset {start_offset} is larger than or equal to number of URLs ({len(linkedin_urls)}).")
        return

    linkedin_urls_subset = linkedin_urls[start_offset:]
    print(f"Starting from index {start_offset}. Processing {len(linkedin_urls_subset)} of {len(linkedin_urls)} URLs.")
    print(f"Found {len(linkedin_urls)} LinkedIn URLs total.")

    with sync_playwright() as p:
        # Launch browser in headed mode so the user can see and interact
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        for i, url in enumerate(linkedin_urls_subset):
            actual_index = start_offset + i + 1
            print(f"[{actual_index}/{len(linkedin_urls)}] Opening: {url}")
            print("Close the tab to proceed to the next profile...")
            
            try:
                page = context.new_page()
                page.goto(url)
                
                try:
                    # Brief wait for page to settle
                    page.wait_for_load_state("domcontentloaded")
                    
                    # Define the message
                    message = """Hey, thanks for the star on Surge (github.com/surge-downloader/surge)

I'm the creator (2nd year at IIITG). I am looking for an internship for the summer where I can write more backend/swe projects .

If you,  your team, or anyone you know is looking for someone, would love to connect!"""

                    # Attempt to find and click "Connect"
                    # Strategy 1: Primary Connect Button
                    connect_button = page.get_by_role("button", name="Connect", exact=True)
                    
                    if not connect_button.is_visible():
                        # Strategy 2: "More" dropdown -> Connect
                        more_button = page.get_by_role("button", name="More", exact=True)
                        if more_button.is_visible():
                            more_button.click()
                            # Wait for dropdown items
                            connect_button_in_menu = page.get_by_role("button", name="Connect", exact=True)
                            if connect_button_in_menu.is_visible():
                                connect_button_in_menu.click()
                                connect_button = connect_button_in_menu # Mark as found
                    else:
                        connect_button.click()
                    
                    # If we managed to click a Connect button, look for "Add a note"
                    if connect_button and connect_button.is_visible():
                        add_note_button = page.get_by_role("button", name="Add a note")
                        if add_note_button.is_visible(timeout=5000):
                            add_note_button.click()
                            
                            # Type the message
                            # Label usually is "Add a note" or we look for textarea
                            text_area = page.locator("textarea[name='message']")
                            if text_area.is_visible(timeout=5000):
                                text_area.fill(message)
                                print("Filled note. Waiting for you to review and send (or close)...")
                            else:
                                print("Could not find text area to fill note.")
                        else:
                            print("Could not find 'Add a note' button in modal.")
                    else:
                        print("Could not find 'Connect' button automatically.")

                except Exception as e:
                    print(f"Auto-fill failed (proceed manually): {e}")

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
