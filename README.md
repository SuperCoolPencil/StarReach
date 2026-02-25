# StarReach

StarReach is an automated lead generation and outreach tool tailored for GitHub stargazers.
It fetches the users who starred a specific GitHub repository, finds their social accounts (primarily LinkedIn) through their GitHub profiles or personal blogs, and provides a semi-automated way to connect and send outreach messages on LinkedIn.

## Features

- **GitHub Scraper (`main.py`)**:
  - Retrieves all stargazers of a specific GitHub repository.
  - Fetches their public GitHub profile and social accounts.
  - Automatically crawls their personal website/blog to find LinkedIn URLs if not provided directly on GitHub.
  - Uses concurrent threads for fast processing.
  - Saves the results to an Excel file (`surge_leads.xlsx`).
  - Supports resuming from a previous run.

- **LinkedIn Outreach (`linkedin.py`)**:
  - Reads the generated `surge_leads.xlsx` file.
  - Uses Playwright to open LinkedIn profiles one by one in a real browser.
  - Allows you to log in manually, then iterates through the leads.
  - Prints your customized outreach message to the console for easy copy-pasting.

## Setup

1. Make sure you have Python 3.11+ installed.
2. Install the dependencies using `uv` (recommended):
   ```bash
   uv sync
   ```
3. Set up your environment variables by creating a `.env` file:
   ```bash
   cp .env.example .env
   ```
   Add your GitHub Personal Access Token to the `.env` file:
   ```env
   GITHUB_TOKEN=ghp_your_personal_access_token_here
   ```

## Usage

### 1. Extract GitHub Leads

Edit the `REPO` variable in `main.py` if you want to target a different repository (default is `surge-downloader/surge`).

Run the scraper:

```bash
python main.py
```

This will generate or update `surge_leads.xlsx`.

### 2. LinkedIn Outreach

After the Excel file is generated, run the outreach script:

```bash
python linkedin.py # Make sure playwright browsers are installed: playwright install
```

You can also use the `--offset` argument to skip profiles already processed (e.g., resume from index 50):

```bash
python linkedin.py --offset 50
```

Follow the on-screen instructions to log in to LinkedIn, and press ENTER to cycle through the profiles.

## License

MIT
