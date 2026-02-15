import pandas as pd
from typing import List, Dict
import os

def export_to_excel(data: List[Dict], filename: str = "stargazers.xlsx"):
    """
    Exports a list of user dictionaries to an Excel file.
    """
    if not data:
        print("No data to export.")
        return

    # Select and rename columns for clarity
    df = pd.DataFrame(data)
    
    # Define columns we care about
    columns_map = {
        "login": "Username",
        "name": "Name",
        "email": "GitHub Email",
        "scraped_email": "Scraped Email",
        "blog": "Website",
        "company": "Company",
        "location": "Location",
        "twitter_username": "Twitter",
        "scraped_linkedin": "LinkedIn",
        "html_url": "GitHub Profile"
    }
    
    # Filter for existing columns only
    available_cols = [col for col in columns_map.keys() if col in df.columns]
    df = df[available_cols]
    df = df.rename(columns=columns_map)
    
    # Deduplicate emails if Scraped Email is same as GitHub Email (Optional logic)
    
    try:
        if os.path.exists(filename):
            # If file exists, we might want to append? 
            # For now, let's just overwrite but we need a way to read existing to skip.
            pass
        
        df.to_excel(filename, index=False)
        print(f"Successfully exported {len(df)} records to {os.path.abspath(filename)}")
    except Exception as e:
        print(f"Error exporting to Excel: {e}")

def load_existing_users(filename: str = "stargazers.xlsx") -> List[str]:
    """
    Loads existing usernames from the Excel file to avoid reprocessing.
    """
    if not os.path.exists(filename):
        return []
    
    try:
        df = pd.read_excel(filename)
        # Check if 'Username' column exists (based on our export_to_excel mapping)
        if "Username" in df.columns:
            return df["Username"].dropna().astype(str).tolist()
        # Fallback if column name is different or raw data
        if "login" in df.columns:
            return df["login"].dropna().astype(str).tolist()
    except Exception as e:
        print(f"Error loading existing users: {e}")
    
    return []
