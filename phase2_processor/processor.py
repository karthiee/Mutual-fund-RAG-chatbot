"""
Phase 2 — Data Processing & Structuring.

Reads every raw JSON file produced by Phase 1 (phase1_scraper/raw_data/),
validates the data, splits each fund into 5 semantic document chunks,
and writes the result to processed_data/chunks.jsonl.

Each fund produces 5 chunks:
  A. overview    — fund name, category, riskometer
  B. pricing     — NAV price and date
  C. cost_fees   — expense ratio and exit load
  D. investment  — minimum SIP and lock-in period
  E. holdings    — top 3 stock holdings

Usage:
    python processor.py                  # Process all raw JSON files
    python processor.py --input path/to/raw_data      # Custom input directory
    python processor.py --output path/to/output.jsonl # Custom output file
    python processor.py --pretty                       # Pretty-print JSONL (one JSON per line, readable)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from pydantic import ValidationError

from models import (
    ChunkMetadata,
    ChunkType,
    DocumentChunk,
    RawFundData,
)

# ── Default paths ─────────────────────────────────────────────────────────────
ROOT_DIR          = Path(__file__).parent
DEFAULT_INPUT_DIR = ROOT_DIR.parent / "phase1_scraper" / "raw_data"
PROCESSED_DIR     = ROOT_DIR / "processed_data"
DEFAULT_OUTPUT    = PROCESSED_DIR / "chunks.jsonl"

PROCESSED_DIR.mkdir(exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
logger.add(ROOT_DIR / "processor.log", level="DEBUG", rotation="5 MB", retention="7 days")


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Load & validate a single raw JSON file
# ─────────────────────────────────────────────────────────────────────────────

def load_raw_fund(json_path: Path) -> RawFundData | None:
    """
    Load and validate one Phase 1 raw JSON file.

    Returns a validated RawFundData, or None if validation fails.
    """
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        fund = RawFundData.model_validate(raw)
        logger.debug(f"  Loaded: {fund.fund_id} — {fund.fund_name}")
        return fund
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error(f"  Validation failed for {json_path.name}: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Clean / normalise raw values
# ─────────────────────────────────────────────────────────────────────────────

def _clean(value: str | None, fallback: str = "Not available") -> str:
    """
    Return a stripped, non-empty string or a human-readable fallback.
    Normalises 'N/A', 'None', 'null', '-', empty strings to `fallback`.
    """
    if not value:
        return fallback
    v = str(value).strip()
    if v.lower() in ("n/a", "none", "null", "nil", "-", ""):
        return fallback
    return v


def _clean_category(raw_category: str) -> str:
    """Return a normalised category slug for metadata filtering."""
    mapping = {
        "small cap":  "small_cap",
        "mid cap":    "mid_cap",
        "large cap":  "large_cap",
        "flexi cap":  "flexi_cap",
        "elss":       "elss",
        "tax sav":    "elss",
    }
    lower = raw_category.lower()
    for key, slug in mapping.items():
        if key in lower:
            return slug
    return raw_category.lower().replace(" ", "_")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Build the 5 document chunks per fund
# ─────────────────────────────────────────────────────────────────────────────

def _make_metadata(fund: RawFundData, chunk_type: ChunkType) -> ChunkMetadata:
    """Construct ChunkMetadata shared across all chunks for this fund."""
    return ChunkMetadata(
        fund_id=fund.fund_id,
        fund_name=fund.fund_name,
        category=_clean_category(fund.category),
        chunk_type=chunk_type,
        source_url=fund.source_url,
        scraped_at=fund.scraped_at.isoformat(),
        processed_at=datetime.now(tz=timezone.utc).isoformat(),
    )


# ── Chunk A: Overview ─────────────────────────────────────────────────────────

def _chunk_overview(fund: RawFundData) -> DocumentChunk:
    """
    Chunk A — General fund overview.
    Answers: "Tell me about X fund" / "What is the risk level?"
    """
    riskometer = _clean(fund.riskometer, "Not disclosed")
    text = (
        f"Fund: {fund.fund_name}\n"
        f"Category: {fund.category}\n"
        f"Riskometer: {riskometer}\n"
        f"This is an HDFC mutual fund classified as a {fund.category}. "
        f"The fund carries a {riskometer} rating on the riskometer, "
        f"indicating the level of risk associated with investing in this fund. "
        f"Source: {fund.source_url}"
    )
    return DocumentChunk(
        chunk_id=f"{fund.fund_id}__{ChunkType.OVERVIEW}",
        text=text,
        metadata=_make_metadata(fund, ChunkType.OVERVIEW),
    )


# ── Chunk B: Pricing (NAV) ────────────────────────────────────────────────────

def _chunk_pricing(fund: RawFundData) -> DocumentChunk:
    """
    Chunk B — NAV / price information.
    Answers: "What is the NAV of X fund?" / "What is the current price?"
    """
    nav = fund.nav
    text = (
        f"Fund: {fund.fund_name}\n"
        f"Category: {fund.category}\n"
        f"NAV (Net Asset Value): ₹{nav.price:,.2f} as of {nav.nav_date.strftime('%B %d, %Y')}\n"
        f"Currency: {nav.currency}\n"
        f"The current Net Asset Value (NAV) of {fund.fund_name} is ₹{nav.price:,.2f}. "
        f"NAV represents the per-unit market value of the fund and is updated daily "
        f"after market close (3:30 PM IST on trading days)."
    )
    return DocumentChunk(
        chunk_id=f"{fund.fund_id}__{ChunkType.PRICING}",
        text=text,
        metadata=_make_metadata(fund, ChunkType.PRICING),
    )


# ── Chunk C: Cost & Fees ──────────────────────────────────────────────────────

def _chunk_cost_fees(fund: RawFundData) -> DocumentChunk:
    """
    Chunk C — Expense ratio and exit load.
    Answers: "What is the expense ratio?" / "Is there an exit load?"
    """
    expense_ratio = _clean(fund.expense_ratio, "Not disclosed")
    exit_load     = _clean(fund.exit_load, "Not applicable")

    # Derive a naturally-worded exit load sentence
    if exit_load.startswith("0") or "no exit" in exit_load.lower() or "nil" in exit_load.lower():
        exit_load_sentence = f"There is no exit load for {fund.fund_name}."
    else:
        exit_load_sentence = f"Exit load applies: {exit_load}."

    text = (
        f"Fund: {fund.fund_name}\n"
        f"Category: {fund.category}\n"
        f"Expense Ratio: {expense_ratio}\n"
        f"Exit Load: {exit_load}\n"
        f"The expense ratio of {fund.fund_name} is {expense_ratio}. "
        f"This is the annual fee charged by the fund house to manage your investment. "
        f"{exit_load_sentence}"
    )
    return DocumentChunk(
        chunk_id=f"{fund.fund_id}__{ChunkType.COST_FEES}",
        text=text,
        metadata=_make_metadata(fund, ChunkType.COST_FEES),
    )


# ── Chunk D: Investment Details ───────────────────────────────────────────────

def _chunk_investment(fund: RawFundData) -> DocumentChunk:
    """
    Chunk D — Minimum SIP and lock-in period.
    Answers: "What is the minimum SIP?" / "Is there a lock-in period?"
    """
    min_sip     = _clean(fund.minimum_sip, "Not specified")
    lock_in     = _clean(fund.lock_in_period, "None")
    category    = fund.category

    # Build lock-in sentence
    if lock_in.lower() in ("none", "not applicable", "not available", "nil", "-"):
        lock_in_sentence = f"{fund.fund_name} has no lock-in period. You can redeem your investment at any time."
    else:
        lock_in_sentence = (
            f"{fund.fund_name} has a mandatory lock-in period of {lock_in}. "
            f"This is typical for ELSS funds, which qualify for tax deductions under Section 80C."
        )

    text = (
        f"Fund: {fund.fund_name}\n"
        f"Category: {category}\n"
        f"Minimum SIP: {min_sip}\n"
        f"Lock-in Period: {lock_in}\n"
        f"The minimum SIP (Systematic Investment Plan) amount for {fund.fund_name} is {min_sip}. "
        f"{lock_in_sentence}"
    )
    return DocumentChunk(
        chunk_id=f"{fund.fund_id}__{ChunkType.INVESTMENT}",
        text=text,
        metadata=_make_metadata(fund, ChunkType.INVESTMENT),
    )


# ── Chunk E: Top Holdings ─────────────────────────────────────────────────────

def _chunk_holdings(fund: RawFundData) -> DocumentChunk:
    """
    Chunk E — Top 3 stock holdings.
    Answers: "What are the top holdings?" / "Which stocks does X fund invest in?"
    """
    nav_date = fund.nav.nav_date.strftime("%B %Y")  # e.g. "March 2026"

    if fund.top_holdings:
        holdings_lines = "\n".join(
            f"{h.rank}. {h.name} — {h.percentage:.2f}%"
            for h in sorted(fund.top_holdings, key=lambda h: h.rank)
        )
        holdings_sentence = (
            f"The top 3 holdings of {fund.fund_name} as of {nav_date} are:\n"
            f"{holdings_lines}"
        )
    else:
        holdings_lines = "Holdings data not available."
        holdings_sentence = f"Holdings data for {fund.fund_name} is not currently available."

    text = (
        f"Fund: {fund.fund_name}\n"
        f"Category: {fund.category}\n"
        f"Top 3 Holdings as of {nav_date}:\n"
        f"{holdings_lines}\n"
        f"{holdings_sentence}"
    )
    return DocumentChunk(
        chunk_id=f"{fund.fund_id}__{ChunkType.HOLDINGS}",
        text=text,
        metadata=_make_metadata(fund, ChunkType.HOLDINGS),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Assemble all 5 chunks for one fund
# ─────────────────────────────────────────────────────────────────────────────

def build_chunks(fund: RawFundData) -> list[DocumentChunk]:
    """
    Create all 5 semantic document chunks for a single fund.

    Chunk order:
        A. Overview   → fund overview + riskometer
        B. Pricing    → NAV price and date
        C. Cost Fees  → expense ratio + exit load
        D. Investment → minimum SIP + lock-in
        E. Holdings   → top 3 holdings
    """
    chunks = [
        _chunk_overview(fund),
        _chunk_pricing(fund),
        _chunk_cost_fees(fund),
        _chunk_investment(fund),
        _chunk_holdings(fund),
    ]
    logger.debug(f"  Built {len(chunks)} chunks for {fund.fund_id}")
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Write chunks to JSONL
# ─────────────────────────────────────────────────────────────────────────────

def write_jsonl(chunks: list[DocumentChunk], output_path: Path, pretty: bool = False) -> None:
    """
    Write a list of DocumentChunks to a JSONL file (one JSON object per line).

    Args:
        chunks:      List of DocumentChunk instances.
        output_path: Path to the output .jsonl file (overwritten if it exists).
        pretty:      If True, write each line with 2-space indentation (human-readable).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            obj = json.loads(chunk.model_dump_json())
            if pretty:
                line = json.dumps(obj, ensure_ascii=False, indent=2)
            else:
                line = json.dumps(obj, ensure_ascii=False)
            fh.write(line + "\n")
    logger.success(f"Wrote {len(chunks)} chunks -> {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main processing pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run(
    input_dir: Path = DEFAULT_INPUT_DIR,
    output_path: Path = DEFAULT_OUTPUT,
    pretty: bool = False,
) -> list[DocumentChunk]:
    """
    Full Phase 2 pipeline:
      1. Discover all *.json files in `input_dir`
      2. Load & validate each via RawFundData
      3. Build 5 semantic chunks per fund
      4. Write all chunks to `output_path` as JSONL

    Args:
        input_dir:   Directory containing Phase 1 raw JSON files.
        output_path: Path to write the output JSONL.
        pretty:      Pretty-print each JSON line.

    Returns:
        List of all DocumentChunk objects written.
    """
    logger.info("=" * 60)
    logger.info("Phase 2 — Data Processing & Structuring")
    logger.info(f"Input directory : {input_dir}")
    logger.info(f"Output file     : {output_path}")
    logger.info("=" * 60)

    # ── Discover raw JSON files ────────────────────────────────────────────────
    json_files = sorted(input_dir.glob("*.json"))
    # Exclude the README placeholder
    json_files = [f for f in json_files if f.stem != "README"]

    if not json_files:
        logger.warning(
            f"No JSON files found in {input_dir}. "
            "Run phase1_scraper/scraper.py first to generate data."
        )
        return []

    logger.info(f"Found {len(json_files)} raw JSON file(s): {[f.name for f in json_files]}")

    # ── Process each fund ─────────────────────────────────────────────────────
    all_chunks: list[DocumentChunk] = []
    failed: list[str] = []

    for json_path in json_files:
        logger.info(f"\nProcessing: {json_path.name}")
        fund = load_raw_fund(json_path)
        if fund is None:
            failed.append(json_path.name)
            continue

        chunks = build_chunks(fund)
        all_chunks.extend(chunks)

        # Log each chunk summary
        for c in chunks:
            preview = c.text[:80].replace("\n", " ")
            logger.debug(f"    [{c.metadata.chunk_type}] {preview}…")

    # ── Write output ──────────────────────────────────────────────────────────
    if all_chunks:
        write_jsonl(all_chunks, output_path, pretty=pretty)
    else:
        logger.warning("No chunks produced — nothing written to JSONL.")

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.success(
        f"Processing complete: {len(all_chunks)} chunks from "
        f"{len(json_files) - len(failed)} fund(s). "
        f"{f'Failed: {failed}' if failed else 'No failures.'}"
    )
    logger.info("=" * 60)

    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2: Process Phase 1 raw JSON files into semantic JSONL chunks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python processor.py
  python processor.py --input ../phase1_scraper/raw_data
  python processor.py --output processed_data/chunks.jsonl
  python processor.py --pretty
        """,
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        metavar="DIR",
        help=f"Directory containing Phase 1 raw JSON files. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        metavar="FILE",
        help=f"Output JSONL file path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=False,
        help="Pretty-print each JSON line (multi-line indented). Useful for inspection.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    chunks = run(
        input_dir=args.input,
        output_path=args.output,
        pretty=args.pretty,
    )
    sys.exit(0 if chunks else 1)
