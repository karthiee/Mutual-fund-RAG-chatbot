"""
Phase 6 — Scheduler & Automated Data Refresh.

Primary Scheduling: GitHub Actions (.github/workflows/daily_refresh.yml)
  Runs every day at 10:30 UTC = 4:00 PM IST via cron: "30 10 * * *"
  Processes ALL funds on every run (no change-detection gating).

Local / Server Fallback: APScheduler (this file)
  ┌─────────────────────────────────────────────────────────────────┐
  │  Daily Job    — 4:00 PM IST (aligns with GitHub Actions)            │
  │               Run Phase 1 → 2 → 3 for ALL funds                   │
  │                                                                     │
  │  Monthly Job  — 1st of every month, 6:00 AM IST                    │
  │               Full re-scrape + reset embeddings                    │
  └─────────────────────────────────────────────────────────────────┘

Error Handling:
  - 3 retry attempts with exponential back-off (60s, 120s, 240s)
  - All outcomes logged to scheduler.log (rotating, 30-day retention)

Usage:
    python scheduler.py                  # Start scheduler (runs forever)
    python scheduler.py --run-now        # One-shot immediate pipeline run
    python scheduler.py --run-now --reset # One-shot with full vector store reset
    python scheduler.py --status         # Print next scheduled run times
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

from loguru import logger

# ── Paths ─────────────────────────────────────────────────────────────────────
SCHEDULER_DIR = Path(__file__).parent
LOG_FILE      = SCHEDULER_DIR / "scheduler.log"

# ── Logging ───────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout, level="INFO", colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}"
)
logger.add(
    LOG_FILE, level="DEBUG", rotation="10 MB", retention="30 days",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}"
)

# ── Retry configuration ────────────────────────────────────────────────────────
MAX_RETRIES      = 3
RETRY_DELAYS     = [60, 120, 240]   # seconds between retries (exponential)


# ─────────────────────────────────────────────────────────────────────────────
# Job functions (called by APScheduler)
# ─────────────────────────────────────────────────────────────────────────────

def _import_runner():
    """Lazily import pipeline_runner so the scheduler can start without all deps."""
    sys.path.insert(0, str(SCHEDULER_DIR))
    from pipeline_runner import run_full_pipeline  # noqa: PLC0415
    return run_full_pipeline


def _run_with_retries(trigger: str, reset_embeddings: bool = False) -> None:
    """
    Execute the pipeline with up to MAX_RETRIES retries on failure.
    Logs outcome to scheduler.log on every attempt.
    """
    run_full_pipeline = _import_runner()

    logger.info(f"{'='*60}")
    logger.info(f"Scheduler triggered: {trigger}  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    logger.info(f"{'='*60}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = run_full_pipeline(
                trigger=trigger,
                reset_embeddings=reset_embeddings,
            )
            if result.success:
                logger.success(
                    f"Pipeline {trigger} completed successfully "
                    f"(attempt {attempt}/{MAX_RETRIES})."
                )
                return
            else:
                raise RuntimeError(
                    f"Pipeline reported failure — "
                    f"{[str(p) for p in result.phases if not p.success]}"
                )

        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"  Attempt {attempt}/{MAX_RETRIES} failed: {exc}"
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAYS[attempt - 1]
                logger.warning(f"  Retrying in {delay}s…")
                time.sleep(delay)
            else:
                logger.critical(
                    f"All {MAX_RETRIES} attempts failed for {trigger}. "
                    "Manual intervention may be required. Check scheduler.log."
                )


def daily_nav_refresh() -> None:
    """Daily job: refresh NAV prices (runs after NSE market close, 3:45 PM IST)."""
    _run_with_retries(trigger="daily_cron", reset_embeddings=False)


def monthly_full_refresh() -> None:
    """Monthly job: full re-scrape + reset vector store (1st of month, 6:00 AM IST)."""
    _run_with_retries(trigger="monthly_cron", reset_embeddings=True)


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler setup
# ─────────────────────────────────────────────────────────────────────────────

def build_scheduler():
    """Create and configure the APScheduler BackgroundScheduler."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler  # noqa: PLC0415
        from apscheduler.triggers.cron import CronTrigger              # noqa: PLC0415
    except ImportError:
        logger.error(
            "APScheduler not installed. Run:\n"
            "  pip install APScheduler>=3.10.0\n"
            "or install from phase6_scheduler/requirements.txt"
        )
        sys.exit(1)

    # BlockingScheduler keeps the main thread alive (ideal for a long-running process)
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")

    # ── Daily job: 4:00 PM IST — aligned with GitHub Actions cron (10:30 UTC) ──
    # Runs ALL funds every day — no change detection gating
    scheduler.add_job(
        daily_nav_refresh,
        trigger=CronTrigger(hour=16, minute=0, timezone="Asia/Kolkata"),
        id="daily_nav_refresh",
        name="Daily Full Refresh (4:00 PM IST)",
        misfire_grace_time=600,     # allow 10 min late start
        coalesce=True,              # merge multiple missed fires into one
        replace_existing=True,
    )

    # ── Monthly job: 1st of every month, 6:00 AM IST ─────────────────────────
    scheduler.add_job(
        monthly_full_refresh,
        trigger=CronTrigger(day=1, hour=6, minute=0, timezone="Asia/Kolkata"),
        id="monthly_full_refresh",
        name="Monthly Full Refresh (1st, 6:00 AM IST)",
        misfire_grace_time=3600,
        coalesce=True,
        replace_existing=True,
    )

    return scheduler


def print_status(scheduler) -> None:
    """Print the next run times for all scheduled jobs."""
    print("\n  Scheduled jobs:")
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        print(f"    • {job.name}")
        print(f"      Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S %Z') if next_run else 'not scheduled'}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 6: Automated scheduler for HDFC MF data refresh.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scheduler.py                   # Start scheduler (runs forever, Ctrl+C to stop)
  python scheduler.py --run-now         # Immediate one-shot pipeline run then exit
  python scheduler.py --run-now --reset # One-shot + clear vector store first
  python scheduler.py --status          # Show next run times then exit
        """,
    )
    parser.add_argument(
        "--run-now", action="store_true", default=False,
        help="Run the pipeline immediately (one-shot) then exit. Useful for testing."
    )
    parser.add_argument(
        "--reset", action="store_true", default=False,
        help="Reset (clear) the vector store before embedding. Use with --run-now."
    )
    parser.add_argument(
        "--status", action="store_true", default=False,
        help="Print next scheduled run times and exit."
    )
    args = parser.parse_args()

    # ── One-shot mode ────────────────────────────────────────────────────────
    if args.run_now:
        logger.info("--run-now flag set — executing pipeline immediately.")
        _run_with_retries(trigger="manual_run_now", reset_embeddings=args.reset)
        logger.info("One-shot run complete.  Exiting.")
        sys.exit(0)

    # ── Build scheduler ──────────────────────────────────────────────────────
    scheduler = build_scheduler()

    if args.status:
        # Need to start scheduler briefly to compute next run times
        scheduler.start(paused=True)
        print_status(scheduler)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    # ── Start scheduler (blocking — runs until Ctrl+C) ────────────────────────
    logger.info("=" * 60)
    logger.info("Phase 6 Scheduler starting…")
    logger.info(f"  Log file : {LOG_FILE}")
    logger.info("  Press Ctrl+C to stop.")
    logger.info("=" * 60)

    print_status(scheduler)   # harmless: BlockingScheduler computes next run at start

    try:
        scheduler.start()    # blocks here until shutdown
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped by user.")
    finally:
        if scheduler.running:
            scheduler.shutdown()
        logger.info("Scheduler shutdown complete.")


if __name__ == "__main__":
    main()
