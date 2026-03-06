# Phase 1 — Data Ingestion (Scraper)

Scrapes HDFC Mutual Fund data from [INDmoney](https://www.indmoney.com/mutual-funds) using a headless Playwright browser.

## Folder Structure

```
phase1_scraper/
├── scraper.py          ← Main entry point (run this)
├── models.py           ← Pydantic data models + FUND_REGISTRY
├── requirements.txt    ← Python dependencies
├── scraper.log         ← Rotating log file (created on first run)
└── raw_data/
    ├── README.md
    ├── hdfc-small-cap-3580.json
    ├── hdfc-flexi-cap-3184.json
    ├── hdfc-elss-taxsaver-2685.json
    ├── hdfc-mid-cap-3097.json
    └── hdfc-large-cap-2989.json
```

## Setup

### 1. Install Python dependencies

```bash
cd phase1_scraper
pip install -r requirements.txt
```

### 2. Install Playwright browsers (one-time setup)

```bash
playwright install chromium
```

## Usage

### Scrape all 5 HDFC funds (headless — default)

```bash
python scraper.py
```

### Scrape with browser visible (useful for debugging)

```bash
python scraper.py --headful
```

### Scrape a specific fund by ID

```bash
python scraper.py --fund hdfc-small-cap-3580
```

### Scrape multiple specific funds

```bash
python scraper.py --fund hdfc-elss-taxsaver-2685 hdfc-mid-cap-3097
```

## Available Fund IDs

| Fund ID                        | Fund Name                                  |
|--------------------------------|--------------------------------------------|
| `hdfc-small-cap-3580`          | HDFC Small Cap Fund Direct Growth          |
| `hdfc-flexi-cap-3184`          | HDFC Flexi Cap Fund Direct Plan Growth     |
| `hdfc-elss-taxsaver-2685`      | HDFC ELSS Taxsaver Direct Plan Growth      |
| `hdfc-mid-cap-3097`            | HDFC Mid Cap Opportunities Fund            |
| `hdfc-large-cap-2989`          | HDFC Top 100 Fund (Large Cap)              |

## Output Format

Each fund produces a JSON file like `raw_data/hdfc-small-cap-3580.json`:

```json
{
  "fund_id": "hdfc-small-cap-3580",
  "fund_name": "HDFC Small Cap Fund Direct Growth",
  "category": "Small Cap Fund",
  "source_url": "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
  "scraped_at": "2026-03-03T17:00:00",
  "nav": {
    "price": 150.04,
    "currency": "INR",
    "date": "2026-03-02"
  },
  "expense_ratio": "0.67%",
  "exit_load": "1.00% (if redeemed within 1 year)",
  "minimum_sip": "₹100",
  "lock_in_period": "None",
  "riskometer": "Very High Risk",
  "top_holdings": [
    { "rank": 1, "name": "Firstsource Solutions Ltd", "percentage": 4.79 },
    { "rank": 2, "name": "Bank of Baroda", "percentage": 3.80 },
    { "rank": 3, "name": "eClerx Services Ltd", "percentage": 3.78 }
  ]
}
```

## Notes

- INDmoney pages are **JavaScript-rendered (SPA)** — the scraper uses Playwright instead of a simple HTTP client.
- The scraper waits 3 seconds after page load for the JS to fully render before extracting data.
- Each run **overwrites** the existing JSON file for that fund.
- Logs are written to `scraper.log` (rotated at 5 MB, kept for 7 days).
- Phase 6 (Scheduler) will automate running this scraper daily at 3:45 PM IST.
