# Phase 6 — Scheduler & Automated Data Refresh

Automated refresh pipeline that keeps the HDFC MF chatbot's vector store up-to-date without manual intervention.

## Files

| File | Purpose |
|---|---|
| `scheduler.py` | APScheduler entry point — daily + monthly cron jobs |
| `pipeline_runner.py` | Orchestrates Phase 1 → 2 → 3 with change detection |
| `change_detector.py` | deepdiff-based snapshot comparison per fund |
| `snapshots/` | Stored JSON snapshots for change comparison |
| `scheduler.log` | Rotating log (auto-created on first run) |
| `requirements.txt` | Dependencies for this phase |

## Install

```bash
pip install -r phase6_scheduler/requirements.txt
```

## Usage

```bash
# Start the scheduler (runs forever, Ctrl+C to stop)
python phase6_scheduler/scheduler.py

# One-shot: run the full pipeline immediately and exit (great for testing)
python phase6_scheduler/scheduler.py --run-now

# One-shot with full vector store reset (monthly-style refresh)
python phase6_scheduler/scheduler.py --run-now --reset

# Show next scheduled run times
python phase6_scheduler/scheduler.py --status

# Run pipeline_runner directly
python phase6_scheduler/pipeline_runner.py
python phase6_scheduler/pipeline_runner.py --skip-scrape   # use existing raw data
python phase6_scheduler/pipeline_runner.py --reset         # clear vector store

# Test change detector in isolation
python phase6_scheduler/change_detector.py --test
python phase6_scheduler/change_detector.py --status
```

## Schedule

| Job | Trigger | Purpose |
|---|---|---|
| **Daily NAV Refresh** | Every day at **3:45 PM IST** | Picks up updated NAV prices post-market |
| **Monthly Full Refresh** | **1st of each month** at 6:00 AM IST | Re-scrapes holdings & expense ratios |

## Smart Refresh — Change Detection

Phase 2 and Phase 3 only run when data actually changed:

```
Phase 1 (Scrape) → Change Detection → Phase 2+3 only if changed
                             ↓
                        No change? → Skip (vector store stays as-is)
```

Change detection ignores volatile fields (`scraped_at`, `processed_at`) and uses `deepdiff` to compare meaningul fund data field-by-field.

## Error Handling

- **3 automatic retries** with exponential back-off (60s → 120s → 240s)
- All attempts logged to `scheduler.log`
- On total failure: logs CRITICAL-level alert — check `scheduler.log`

## Prerequisites

Phases 1–3 must have been run at least once before the scheduler starts:

```bash
phase3_embedder/vector_store/    ← must exist
.env                             ← must contain GROQ_API_KEY
```
