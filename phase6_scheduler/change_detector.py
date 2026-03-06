"""
Phase 6 — Change Detector.

Compares newly scraped JSON files against stored snapshots to determine
which funds actually changed. Only changed funds need to be re-processed
and re-embedded, saving compute and time.

Strategy:
  1. Load new JSON from phase1_scraper/raw_data/<fund_id>.json
  2. Load snapshot JSON from phase6_scheduler/snapshots/<fund_id>.json
  3. Use deepdiff to compare the two dicts (ignoring scraped_at timestamp)
  4. If diff found → mark fund as changed, update snapshot
  5. Return list of changed fund IDs

Usage (standalone test):
    python change_detector.py --test
    python change_detector.py --status     # Print current snapshot state
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR      = Path(__file__).parent.parent
RAW_DATA_DIR  = ROOT_DIR / "phase1_scraper" / "raw_data"
SNAPSHOT_DIR  = Path(__file__).parent / "snapshots"
SNAPSHOT_DIR.mkdir(exist_ok=True)

# Fields to ignore when diffing (change often but don't affect rag content)
IGNORE_KEYS = {"scraped_at", "processed_at"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Optional[dict]:
    """Load a JSON file and return its content as a dict, or None on error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning(f"  Could not load {path.name}: {exc}")
        return None


def _strip_volatile_keys(data: dict) -> dict:
    """
    Return a copy of data with volatile keys removed so diff focuses
    on meaningful fund-level data changes only.
    """
    cleaned = {}
    for k, v in data.items():
        if k in IGNORE_KEYS:
            continue
        if isinstance(v, dict):
            cleaned[k] = _strip_volatile_keys(v)
        else:
            cleaned[k] = v
    return cleaned


def _diff(old: dict, new: dict) -> dict:
    """Return a deepdiff dict between old and new (empty = no changes)."""
    try:
        from deepdiff import DeepDiff  # noqa: PLC0415
        result = DeepDiff(old, new, ignore_order=True, significant_digits=4)
        return dict(result)
    except ImportError:
        logger.warning("deepdiff not installed — falling back to simple equality check.")
        return {} if old == new else {"fallback_diff": "deepdiff unavailable"}


# ─────────────────────────────────────────────────────────────────────────────
# Core: detect changes for a single fund
# ─────────────────────────────────────────────────────────────────────────────

def detect_fund_change(fund_id: str, raw_data_dir: Path = RAW_DATA_DIR,
                       snapshot_dir: Path = SNAPSHOT_DIR) -> bool:
    """
    Compare the newly scraped JSON for `fund_id` against its snapshot.

    Returns:
        True  — data changed (needs re-processing + re-embedding)
        False — data unchanged (skip this fund)

    Side effect:
        If changed, the snapshot is updated to the new data.
        If no snapshot exists yet, creates one and returns True (treat as changed).
    """
    new_path      = raw_data_dir / f"{fund_id}.json"
    snapshot_path = snapshot_dir / f"{fund_id}.json"

    new_data = _load_json(new_path)
    if new_data is None:
        logger.error(f"  [{fund_id}] New data file not found — skipping.")
        return False

    old_data = _load_json(snapshot_path)
    if old_data is None:
        # First run — no snapshot exists yet.  Create one and treat as changed.
        logger.info(f"  [{fund_id}] No snapshot found — treating as changed (first run).")
        shutil.copy2(new_path, snapshot_path)
        return True

    # Strip volatile keys before diffing
    old_clean = _strip_volatile_keys(old_data)
    new_clean = _strip_volatile_keys(new_data)

    diff = _diff(old_clean, new_clean)

    if diff:
        logger.info(f"  [{fund_id}] CHANGED — {len(diff)} diff key(s): {list(diff.keys())}")
        # Update snapshot
        shutil.copy2(new_path, snapshot_path)
        return True

    logger.info(f"  [{fund_id}] UNCHANGED — skipping re-embed.")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Core: detect changes across all funds
# ─────────────────────────────────────────────────────────────────────────────

def detect_changes(
    raw_data_dir: Path = RAW_DATA_DIR,
    snapshot_dir: Path = SNAPSHOT_DIR,
    fund_ids: Optional[list[str]] = None,
) -> list[str]:
    """
    Run change detection for all (or specified) funds.

    Args:
        raw_data_dir: Directory of Phase 1 scraped JSON files.
        snapshot_dir: Directory of stored snapshots.
        fund_ids:    Specific fund IDs to check. None = check all JSON in raw_data_dir.

    Returns:
        List of fund_ids that changed (empty = nothing to re-embed).
    """
    logger.info("=" * 60)
    logger.info("Phase 6 — Change Detection")
    logger.info(f"Raw data dir : {raw_data_dir}")
    logger.info(f"Snapshot dir : {snapshot_dir}")
    logger.info("=" * 60)

    # Discover fund IDs from raw_data_dir if not specified
    if fund_ids is None:
        json_files = sorted(raw_data_dir.glob("*.json"))
        fund_ids = [f.stem for f in json_files if f.stem != "README"]

    if not fund_ids:
        logger.warning("No fund JSON files found in raw_data_dir.")
        return []

    logger.info(f"Checking {len(fund_ids)} fund(s): {fund_ids}")

    changed: list[str] = []
    for fid in fund_ids:
        if detect_fund_change(fid, raw_data_dir, snapshot_dir):
            changed.append(fid)

    logger.info("=" * 60)
    if changed:
        logger.success(f"Changed funds ({len(changed)}): {changed}")
    else:
        logger.info("No changes detected — vector store is up-to-date.")
    logger.info("=" * 60)

    return changed


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _print_status() -> None:
    """Print the current snapshot inventory and modification times."""
    snapshots = sorted(SNAPSHOT_DIR.glob("*.json"))
    if not snapshots:
        print("No snapshots stored yet.")
        return
    print(f"\nSnapshots in {SNAPSHOT_DIR}:")
    for s in snapshots:
        data = _load_json(s)
        scraped_at = data.get("scraped_at", "unknown") if data else "unreadable"
        nav_price  = data.get("nav", {}).get("price", "?") if data else "?"
        print(f"  {s.name:40s}  scraped_at={scraped_at:<30s}  nav=₹{nav_price}")


def _self_test() -> None:
    """Quick sanity test: create two mock JSON blobs, compare them."""
    import tempfile, os  # noqa: E401

    print("\nRunning self-test for change_detector...")

    fund_id = "_test_fund_"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        raw_dir  = tmp / "raw"
        snap_dir = tmp / "snap"
        raw_dir.mkdir(); snap_dir.mkdir()

        # ── Test 1: no snapshot → should be detected as changed ───────────────
        v1 = {"fund_id": fund_id, "nav": {"price": 100.0}, "scraped_at": "2026-01-01"}
        (raw_dir / f"{fund_id}.json").write_text(json.dumps(v1))
        changed = detect_fund_change(fund_id, raw_dir, snap_dir)
        assert changed, "Test 1 FAILED: expected changed=True (no snapshot)"
        print("  [PASS] Test 1: no snapshot -> detected as changed")

        # ── Test 2: same data -> no change ────────────────────────────────────
        (raw_dir / f"{fund_id}.json").write_text(json.dumps(v1))
        changed = detect_fund_change(fund_id, raw_dir, snap_dir)
        assert not changed, "Test 2 FAILED: expected changed=False (same data)"
        print("  [PASS] Test 2: same data -> no change detected")

        # ── Test 3: different NAV -> should detect change ─────────────────────
        v2 = {"fund_id": fund_id, "nav": {"price": 105.5}, "scraped_at": "2026-01-02"}
        (raw_dir / f"{fund_id}.json").write_text(json.dumps(v2))
        changed = detect_fund_change(fund_id, raw_dir, snap_dir)
        assert changed, "Test 3 FAILED: expected changed=True (different NAV)"
        print("  [PASS] Test 3: NAV price changed -> detected as changed")

        # ── Test 4: only scraped_at changed -> ignored ────────────────────────
        v3 = {"fund_id": fund_id, "nav": {"price": 105.5}, "scraped_at": "2026-01-03"}
        (raw_dir / f"{fund_id}.json").write_text(json.dumps(v3))
        changed = detect_fund_change(fund_id, raw_dir, snap_dir)
        assert not changed, "Test 4 FAILED: expected changed=False (only scraped_at changed)"
        print("  [PASS] Test 4: only scraped_at changed -> ignored")

    print("\nAll self-tests passed [OK]\n")


if __name__ == "__main__":
    import argparse

    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")

    parser = argparse.ArgumentParser(description="Phase 6: Change detection tool.")
    parser.add_argument("--test",   action="store_true", help="Run self-test and exit.")
    parser.add_argument("--status", action="store_true", help="Print snapshot status.")
    args = parser.parse_args()

    if args.test:
        _self_test()
        sys.exit(0)

    if args.status:
        _print_status()
        sys.exit(0)

    # Default: run change detection against current raw_data
    changed = detect_changes()
    sys.exit(0 if changed is not None else 1)
