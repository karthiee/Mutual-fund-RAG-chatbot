# Phase 2 — Data Processing & Structuring

Reads raw JSON files produced by Phase 1, validates and cleans the data, splits each fund into **5 semantic document chunks**, and writes a JSONL corpus for Phase 3 (embedding).

## Folder Structure

```
phase2_processor/
├── processor.py          ← Main entry point (run this)
├── processor_models.py   ← Pydantic models (ChunkType, RawFundData, DocumentChunk)
├── requirements.txt      ← Python dependencies
├── processor.log         ← Rotating log file (created on first run)
└── processed_data/
    ├── README.md
    └── chunks.jsonl      ← Output: 25 chunks (5 funds × 5 types)
```

## Setup

```bash
cd phase2_processor
pip install -r requirements.txt
```

> **Note:** Phase 1 must have run successfully first so that `phase1_scraper/raw_data/` contains JSON files.

## Usage

### Process all raw JSON files (default)

```bash
python processor.py
```

### Process with a custom input directory

```bash
python processor.py --input ../phase1_scraper/raw_data
```

### Human-readable output (pretty JSONL)

```bash
python processor.py --pretty
```

### Custom output file path

```bash
python processor.py --output processed_data/chunks.jsonl
```

## Chunk Types

Each fund is split into exactly **5 semantic chunks**:

| Chunk Type   | Content                               | Answers questions like…                        |
|--------------|---------------------------------------|------------------------------------------------|
| `overview`   | Fund name, category, riskometer       | "Tell me about HDFC Small Cap Fund"            |
| `pricing`    | NAV price and date                    | "What is the current NAV?"                     |
| `cost_fees`  | Expense ratio, exit load              | "What is the expense ratio?" / "Any exit load?"|
| `investment` | Minimum SIP, lock-in period           | "What is the minimum SIP?" / "Lock-in period?" |
| `holdings`   | Top 3 stock holdings + percentages    | "What stocks does this fund hold?"             |

## Output Format (JSONL)

`processed_data/chunks.jsonl` — one JSON object per line, 25 lines total:

```json
{
  "chunk_id": "hdfc-small-cap-3580__cost_fees",
  "text": "Fund: HDFC Small Cap Fund Direct Growth\nCategory: Small Cap Fund\nExpense Ratio: 0.67%\nExit Load: 1.00% if redeemed within 1 year.\nThe expense ratio of HDFC Small Cap Fund Direct Growth is 0.67%...",
  "metadata": {
    "fund_id": "hdfc-small-cap-3580",
    "fund_name": "HDFC Small Cap Fund Direct Growth",
    "category": "small_cap",
    "chunk_type": "cost_fees",
    "source_url": "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
    "scraped_at": "2026-03-02T10:00:00",
    "processed_at": "2026-03-02T11:00:00"
  }
}
```

## Pipeline Flow

```
phase1_scraper/raw_data/*.json
        │
        ▼  load_raw_fund()  → validates via RawFundData (Pydantic)
        │
        ▼  build_chunks()   → creates 5 DocumentChunk objects per fund
           ├── _chunk_overview()
           ├── _chunk_pricing()
           ├── _chunk_cost_fees()
           ├── _chunk_investment()
           └── _chunk_holdings()
        │
        ▼  write_jsonl()    → writes processed_data/chunks.jsonl
```

## Notes

- The `chunk_id` is `<fund_id>__<chunk_type>` and is globally unique — safe to use as a vector DB document ID in Phase 3.
- The metadata `category` field is normalised to a slug (e.g. `small_cap`, `elss`) for efficient filtering in ChromaDB.
- Logs are written to `processor.log` (rotated at 5 MB, kept 7 days).
- Phase 6 (Scheduler) will call this processor automatically after each Phase 1 scrape run.
