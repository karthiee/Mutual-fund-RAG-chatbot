"""
Phase 6 — Pipeline Runner.

Orchestrates Phase 1 → Phase 2 → Phase 3 in sequence for ALL funds on every run.
Change detection is available but NOT applied during scheduled runs — every run
refreshes everything to ensure the vector store is always fully up to date.

Flow:
    1. Run Phase 1 (scraper) for all or specified funds
    2. Run Phase 2 (processor) on ALL raw data
    3. Run Phase 3 (embedder) — optionally with --reset to clear vector store first

Usage:
    python pipeline_runner.py               # Full refresh (all funds)
    python pipeline_runner.py --reset       # Full re-embed (clears vector store)
    python pipeline_runner.py --skip-scrape # Skip Phase 1 (use existing raw data)
    python pipeline_runner.py --fund hdfc-mid-cap-3097   # Single fund
    python pipeline_runner.py --smart       # Enable change detection (skip unchanged)
    python pipeline_runner.py --trigger github_actions   # Tag the trigger source
"""

import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).parent.parent
PHASE1_DIR = ROOT_DIR / "phase1_scraper"
PHASE2_DIR = ROOT_DIR / "phase2_processor"
PHASE3_DIR = ROOT_DIR / "phase3_embedder"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "scheduler.log"

logger.remove()
logger.add(
    sys.stdout, level="INFO", colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}"
)
logger.add(
    LOG_FILE, level="DEBUG", rotation="10 MB", retention="30 days", encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {message}"
)


# ─────────────────────────────────────────────────────────────────────────────
# RunResult — structured result returned after each pipeline run
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PhaseResult:
    phase: str
    success: bool
    skipped: bool = False
    detail: str   = ""
    elapsed_s: float = 0.0

    def __str__(self) -> str:
        status = "SKIP" if self.skipped else ("OK" if self.success else "FAIL")
        elapsed = f" ({self.elapsed_s:.1f}s)" if not self.skipped else ""
        detail  = f" — {self.detail}" if self.detail else ""
        return f"  [{status}] {self.phase}{elapsed}{detail}"


@dataclass
class RunResult:
    started_at:  str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    trigger:     str = "manual"
    phases:      list[PhaseResult] = field(default_factory=list)
    changed_funds: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(p.success or p.skipped for p in self.phases)

    def summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            f"  Pipeline run — {'SUCCESS' if self.success else 'FAILURE'}",
            f"  Trigger  : {self.trigger}",
            f"  Started  : {self.started_at}",
            f"  Finished : {self.finished_at}",
        ]
        for p in self.phases:
            lines.append(str(p))
        lines.append("=" * 60)
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Phase runners (thin wrappers that capture timing + errors)
# ─────────────────────────────────────────────────────────────────────────────

def _run_phase1(fund_ids: Optional[list[str]], headless: bool = True) -> PhaseResult:
    """Run Phase 1 scraper and return a PhaseResult."""
    logger.info("─" * 60)
    logger.info("Phase 1 — Scraping fund data from INDmoney…")
    t0 = time.time()
    try:
        sys.path.insert(0, str(PHASE1_DIR))
        from scraper import run as scraper_run  # noqa: PLC0415
        paths = scraper_run(fund_ids=fund_ids, headless=headless)
        sys.path.pop(0)

        elapsed = time.time() - t0
        if paths:
            return PhaseResult("Phase 1 (Scraper)", True,
                               detail=f"{len(paths)} fund(s) scraped",
                               elapsed_s=elapsed)
        return PhaseResult("Phase 1 (Scraper)", False,
                           detail="Scraper returned no files", elapsed_s=elapsed)
    except Exception as exc:  # noqa: BLE001
        if str(PHASE1_DIR) in sys.path:
            sys.path.remove(str(PHASE1_DIR))
        elapsed = time.time() - t0
        logger.error(f"Phase 1 failed: {exc}", exc_info=True)
        return PhaseResult("Phase 1 (Scraper)", False,
                           detail=str(exc)[:120], elapsed_s=elapsed)


def _run_change_detection(fund_ids: Optional[list[str]]) -> tuple[list[str], PhaseResult]:
    """Run change detection and return (changed_ids, PhaseResult)."""
    logger.info("─" * 60)
    logger.info("Phase 6 — Change detection…")
    t0 = time.time()
    try:
        sys.path.insert(0, str(PHASE1_DIR))
        from change_detector import detect_changes  # noqa: PLC0415
        changed = detect_changes(fund_ids=fund_ids)
        sys.path.pop(0)
        sys.modules.pop("change_detector", None)

        elapsed = time.time() - t0
        detail = f"{len(changed)} changed: {changed}" if changed else "no changes"
        return changed, PhaseResult("Change Detection", True, detail=detail, elapsed_s=elapsed)
    except Exception as exc:  # noqa: BLE001
        if str(PHASE1_DIR) in sys.path:
            sys.path.remove(str(PHASE1_DIR))
        elapsed = time.time() - t0
        logger.error(f"Change detection failed: {exc}", exc_info=True)
        # On error, assume all funds changed (conservative)
        logger.warning("Change detection error — treating all funds as changed.")
        return fund_ids or [], PhaseResult("Change Detection", False,
                                          detail=str(exc)[:120], elapsed_s=elapsed)


def _run_phase2() -> PhaseResult:
    """Run Phase 2 processor on all raw data."""
    logger.info("─" * 60)
    logger.info("Phase 2 — Processing and chunking fund data…")
    t0 = time.time()
    try:
        sys.path.insert(0, str(PHASE2_DIR))
        from processor import run as processor_run  # noqa: PLC0415
        chunks = processor_run()
        sys.path.pop(0)
        sys.modules.pop("processor", None)

        elapsed = time.time() - t0
        if chunks:
            return PhaseResult("Phase 2 (Processor)", True,
                               detail=f"{len(chunks)} chunks produced",
                               elapsed_s=elapsed)
        return PhaseResult("Phase 2 (Processor)", False,
                           detail="No chunks produced", elapsed_s=elapsed)
    except Exception as exc:  # noqa: BLE001
        if str(PHASE2_DIR) in sys.path:
            sys.path.remove(str(PHASE2_DIR))
        elapsed = time.time() - t0
        logger.error(f"Phase 2 failed: {exc}", exc_info=True)
        return PhaseResult("Phase 2 (Processor)", False,
                           detail=str(exc)[:120], elapsed_s=elapsed)


def _run_phase3(reset: bool = False) -> PhaseResult:
    """Run Phase 3 embedder to upsert chunks into vector store."""
    logger.info("─" * 60)
    logger.info(f"Phase 3 — Embedding chunks into vector store (reset={reset})…")
    t0 = time.time()
    try:
        sys.path.insert(0, str(PHASE3_DIR))
        from embedder import run as embedder_run  # noqa: PLC0415
        n = embedder_run(reset=reset)
        sys.path.pop(0)
        sys.modules.pop("embedder", None)
        sys.modules.pop("vector_store_lib", None)

        elapsed = time.time() - t0
        if n > 0:
            return PhaseResult("Phase 3 (Embedder)", True,
                               detail=f"{n} chunks embedded",
                               elapsed_s=elapsed)
        return PhaseResult("Phase 3 (Embedder)", False,
                           detail="0 chunks embedded", elapsed_s=elapsed)
    except Exception as exc:  # noqa: BLE001
        if str(PHASE3_DIR) in sys.path:
            sys.path.remove(str(PHASE3_DIR))
        elapsed = time.time() - t0
        logger.error(f"Phase 3 failed: {exc}", exc_info=True)
        return PhaseResult("Phase 3 (Embedder)", False,
                           detail=str(exc)[:120], elapsed_s=elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_full_pipeline(
    fund_ids:         Optional[list[str]] = None,
    skip_scrape:      bool = False,
    reset_embeddings: bool = False,
    trigger:          str  = "manual",
    headless:         bool = True,
    force_smart:      bool = False,   # True = use change detection to skip unchanged
) -> RunResult:
    """
    Run the full Phase 1 → 2 → 3 pipeline for ALL funds.

    By default every run re-processes and re-embeds ALL scraped data so the
    vector store is always fully in sync.  Set force_smart=True (or --smart CLI
    flag) to enable change detection and skip unchanged funds.

    Args:
        fund_ids:          Specific fund IDs to process. None = all funds.
        skip_scrape:       If True, skip Phase 1 (use existing raw data).
        reset_embeddings:  If True, clear the vector store before re-embedding.
        trigger:           Label for the log ('github_actions', 'daily_cron', 'manual').
        headless:          Whether Phase 1 runs the browser headlessly.
        force_smart:       If True, apply change detection and skip unchanged funds.

    Returns:
        RunResult with per-phase outcomes.
    """
    result = RunResult(trigger=trigger)

    logger.info("=" * 60)
    logger.info(f"Phase 6 — Pipeline Start  [trigger={trigger}]")
    logger.info(f"  fund_ids         : {fund_ids or 'all'}")
    logger.info(f"  skip_scrape      : {skip_scrape}")
    logger.info(f"  reset_embeddings : {reset_embeddings}")
    logger.info(f"  change_detection : {'enabled (--smart)' if force_smart else 'disabled — full refresh'}")
    logger.info("=" * 60)

    # ── Phase 1: Scrape ────────────────────────────────────────────────────────
    if skip_scrape:
        p1 = PhaseResult("Phase 1 (Scraper)", True, skipped=True,
                         detail="--skip-scrape flag set — using existing raw data")
        logger.info("  Skipped Phase 1 — using existing raw_data.")
    else:
        p1 = _run_phase1(fund_ids, headless=headless)
    result.phases.append(p1)

    if not p1.success and not p1.skipped:
        logger.error("Phase 1 failed — aborting pipeline.")
        result.finished_at = datetime.now(timezone.utc).isoformat()
        logger.info(result.summary())
        return result

    # ── Optional Change Detection (only when --smart is set) ──────────────────
    if force_smart:
        changed, cd_result = _run_change_detection(fund_ids)
        result.phases.append(cd_result)
        result.changed_funds = changed

        if not changed and not reset_embeddings:
            logger.info("No changes detected — skipping Phase 2 and Phase 3.")
            for phase_name in ["Phase 2 (Processor)", "Phase 3 (Embedder)"]:
                result.phases.append(
                    PhaseResult(phase_name, True, skipped=True,
                                detail="No data changes detected — skipped")
                )
            result.finished_at = datetime.now(timezone.utc).isoformat()
            logger.info(result.summary())
            return result
    else:
        logger.info("Change detection skipped — processing ALL funds (full refresh mode).")

    # ── Phase 2: Process ALL raw data ─────────────────────────────────────────
    p2 = _run_phase2()
    result.phases.append(p2)

    if not p2.success:
        logger.error("Phase 2 failed — aborting before Phase 3.")
        result.finished_at = datetime.now(timezone.utc).isoformat()
        logger.info(result.summary())
        return result

    # ── Phase 3: Embed ALL chunks ─────────────────────────────────────────────
    p3 = _run_phase3(reset=reset_embeddings)
    result.phases.append(p3)

    result.finished_at = datetime.now(timezone.utc).isoformat()
    logger.info(result.summary())
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Phase 6: Run the full data refresh pipeline (Phase 1→2→3).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline_runner.py                          # Full refresh ALL funds
  python pipeline_runner.py --reset                  # Full re-embed (clear store)
  python pipeline_runner.py --skip-scrape            # Process existing raw data
  python pipeline_runner.py --fund hdfc-mid-cap-3097 # Single fund
  python pipeline_runner.py --smart                  # Enable change detection
  python pipeline_runner.py --trigger github_actions # Tag trigger source
        """,
    )
    parser.add_argument("--fund",        nargs="+", metavar="FUND_ID",
                        help="One or more fund IDs. Omit for all funds.")
    parser.add_argument("--skip-scrape", action="store_true", default=False,
                        help="Skip Phase 1 and use existing raw JSON data.")
    parser.add_argument("--reset",       action="store_true", default=False,
                        help="Reset (clear) the vector store before embedding.")
    parser.add_argument("--headful",     action="store_true", default=False,
                        help="Run browser in visible mode (debug scraping).")
    parser.add_argument("--smart",       action="store_true", default=False,
                        help="Enable change detection — only re-embed changed funds.")
    parser.add_argument("--trigger",     type=str, default="manual",
                        help="Trigger label (e.g. github_actions, daily_cron). Default: manual.")
    args = parser.parse_args()

    run_result = run_full_pipeline(
        fund_ids=args.fund,
        skip_scrape=args.skip_scrape,
        reset_embeddings=args.reset,
        headless=not args.headful,
        force_smart=args.smart,
        trigger=args.trigger,
    )
    sys.exit(0 if run_result.success else 1)
