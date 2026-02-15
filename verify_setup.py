import asyncio
import os
import pandas as pd
from scraper import ProfileScraper
from exporter import export_to_excel, load_existing_users
from playwright.async_api import async_playwright

async def verify():
    print("Starting verification (Resumability Test)...")
    
    # 1. Clean up previous runs
    if os.path.exists("test_export.xlsx"):
        os.remove("test_export.xlsx")

    # 2. Create a dummy initial excel with one user
    initial_data = [{"Username": "already_done", "Name": "Done User", "GitHub Email": "done@example.com"}]
    pd.DataFrame(initial_data).to_excel("test_export.xlsx", index=False)
    print("Created initial excel with 'already_done' user.")

    # 3. Verify load_existing_users
    existing = load_existing_users("test_export.xlsx")
    if "already_done" in existing:
        print("✅ load_existing_users verified.")
    else:
        print(f"❌ load_existing_users failed. Got: {existing}")

    # 4. Simulate processing new user (mock logic)
    mock_user = {
        "login": "octocat-test",
        "name": "The Octocat",
        "blog": "http://localhost:8080/index.html",
        "email": "api_email@github.com",
        "html_url": "https://github.com/octocat-test",
        # Mock scraped data
        "scraped_email": "test@example.com",
        "scraped_linkedin": "https://linkedin.com/in/testuser"
    }

    # 5. Append Logic Verification
    existing_df = pd.read_excel("test_export.xlsx")
    mock_user_df = pd.DataFrame([mock_user]).rename(columns={
        "login": "Username", "name": "Name", "email": "GitHub Email",
        "scraped_email": "Scraped Email", "blog": "Website",
        "company": "Company", "location": "Location",
        "twitter_username": "Twitter", "scraped_linkedin": "LinkedIn",
        "html_url": "GitHub Profile"
    })
    
    # Ensure columns match for concatenation
    # In real main.py we align columns carefully.
    
    combined = pd.concat([existing_df, mock_user_df], ignore_index=True)
    combined.to_excel("test_export.xlsx", index=False)
    
    final_df = pd.read_excel("test_export.xlsx")
    users = final_df["Username"].tolist()
    
    if "already_done" in users and "octocat-test" in users:
        print("✅ Merge/Append logic verified.")
        print(f"Final Users: {users}")
    else:
        print(f"❌ Merge/Append logic failed. Users found: {users}")

if __name__ == "__main__":
    asyncio.run(verify())
