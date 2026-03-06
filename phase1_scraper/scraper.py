"""
Phase 1 — Mutual Fund Data Scraper.

Scrapes NAV, expense ratio, exit load, minimum SIP, lock-in period,
riskometer, and top 3 holdings for 5 HDFC mutual funds from INDmoney.

Usage:
    python scraper.py                    # Scrape all 5 funds
    python scraper.py --fund hdfc-small-cap-3580   # Scrape a single fund by ID
    python scraper.py --headful          # Run browser in visible mode (useful for debugging)

Output:
    raw_data/<fund_id>.json  — one file per fund
"""

import argparse
import json
import re
import sys
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.sync_api import Page, sync_playwright, TimeoutError as PlaywrightTimeout

from models import FUND_REGISTRY, FundModel, HoldingModel, NAVModel

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
RAW_DATA_DIR = ROOT_DIR / "raw_data"
RAW_DATA_DIR.mkdir(exist_ok=True)

# ── Logging setup ─────────────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
logger.add(ROOT_DIR / "scraper.log", level="DEBUG", rotation="5 MB", retention="7 days")

# ── Timeouts / waits ──────────────────────────────────────────────────────────
PAGE_TIMEOUT_MS    = 30_000   # max time to wait for page load
ELEMENT_TIMEOUT_MS = 10_000   # max time to wait for individual elements
POST_CLICK_WAIT_MS = 2_000    # wait after clicking a tab


# ─────────────────────────────────────────────────────────────────────────────
# Helper: safe text extraction
# ─────────────────────────────────────────────────────────────────────────────

def _safe_text(page: Page, selector: str, default: str = "N/A") -> str:
    """
    Return the inner text of the first element matching `selector`,
    or `default` if the element is not found within ELEMENT_TIMEOUT_MS.
    Strips whitespace and newlines from the result.
    """
    try:
        element = page.wait_for_selector(selector, timeout=ELEMENT_TIMEOUT_MS)
        if element:
            return element.inner_text().strip()
    except PlaywrightTimeout:
        pass
    return default


def _click_tab(page: Page, tab_label: str) -> bool:
    """
    Click a navigation tab by its visible text.
    Returns True if the click succeeded, False otherwise.
    """
    try:
        # INDmoney tabs are <button> or <a> elements with the tab text
        tab = page.get_by_role("tab", name=tab_label, exact=False)
        if not tab.count():
            # Fallback: look for any clickable element with matching text
            tab = page.get_by_text(tab_label, exact=False).first
        tab.click(timeout=ELEMENT_TIMEOUT_MS)
        page.wait_for_timeout(POST_CLICK_WAIT_MS)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"  Could not click tab '{tab_label}': {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# NAV extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_nav(page: Page) -> NAVModel:
    """
    Extract the fund's NAV price and the date it was last updated.
    INDmoney shows these near the top of the page.

    Expected patterns (as of 2026):
        Price text:  "₹150.04"
        Date text:   "as of Mar 02, 2026"  or  "02 Mar 2026"
    """
    # Common selectors for NAV price on INDmoney
    nav_selectors = [
        "[data-testid='nav-price']",
        ".nav-price",
        "span:has-text('₹')",           # fallback: any rupee span
    ]
    raw_price = "0"
    for sel in nav_selectors:
        try:
            elem = page.locator(sel).first
            if elem.count():
                text = elem.inner_text().strip()
                raw_price = text
                break
        except Exception:  # noqa: BLE001
            continue

    # Strip currency symbol and commas → float
    price_str = re.sub(r"[^\d.]", "", raw_price.replace(",", ""))
    try:
        nav_price = float(price_str) if price_str else 0.0
    except ValueError:
        nav_price = 0.0

    # NAV date — look for "as of" pattern anywhere on page
    page_text = page.inner_text("body")
    nav_date = date.today()
    date_match = re.search(
        r"(?:as of|As of|NAV as on)\s+([A-Za-z]{3}\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]{3}\s+\d{4})",
        page_text,
    )
    if date_match:
        raw_date_str = date_match.group(1).replace(",", "").strip()
        for fmt in ("%b %d %Y", "%d %b %Y"):
            try:
                nav_date = datetime.strptime(raw_date_str, fmt).date()
                break
            except ValueError:
                continue

    return NAVModel(price=nav_price, currency="INR", nav_date=nav_date)


# ─────────────────────────────────────────────────────────────────────────────
# Overview tab extraction (expense ratio, exit load, SIP, lock-in, riskometer)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_overview(page: Page) -> dict:
    """
    Navigate to the 'Overview' tab and extract fund detail fields.

    Returns a dict with keys:
        expense_ratio, exit_load, minimum_sip, lock_in_period, riskometer, fund_name, category
    """
    _click_tab(page, "Overview")

    page_text = page.inner_text("body")

    def _find_field(patterns: list[str]) -> str:
        for pattern in patterns:
            m = re.search(pattern, page_text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return "N/A"

    # Expense ratio  — e.g. "Expense Ratio  0.67%"
    expense_ratio = _find_field([
        r"Expense\s+Ratio[:\s]+(\d+\.?\d*%)",
        r"Expense\s+Ratio[^0-9]*(\d+\.?\d*\s*%)",
    ])

    # Exit load — e.g. "Exit Load  1%" or "Exit Load  Nil"
    exit_load = _find_field([
        r"Exit\s+Load[:\s]+([^\n\r]+?)(?:\n|\r|$)",
    ])
    if exit_load and len(exit_load) > 100:
        # guard against over-greedy match
        exit_load = exit_load[:80]

    # Minimum SIP — e.g. "Min SIP  ₹100"
    minimum_sip = _find_field([
        r"Min(?:imum)?\s+SIP[:\s]+([\₹\d,\s]+)",
        r"SIP\s+Amount[:\s]+([\₹\d,\s]+)",
    ])
    minimum_sip = minimum_sip.strip().rstrip(",") if minimum_sip != "N/A" else "N/A"

    # Lock-in period — only ELSS will have a non-None value
    lock_in_period = _find_field([
        r"Lock[\s-]?in\s+Period[:\s]+([^\n\r]+?)(?:\n|\r|$)",
        r"Lock[\s-]?in[:\s]+([^\n\r]+?)(?:\n|\r|$)",
    ])
    if lock_in_period and lock_in_period.lower() in ("n/a", "nil", "na", "-", ""):
        lock_in_period = "None"

    # Riskometer
    riskometer = _find_field([
        r"Riskometer[:\s]+([^\n\r]+?)(?:\n|\r|$)",
        r"Risk[:\s]+(Very High Risk|High Risk|Moderately High Risk|Moderate Risk|Low Risk)",
    ])

    # Fund name from page <h1> or <title>
    fund_name = _safe_text(page, "h1") or _safe_text(page, "title")

    # Category — look for common category strings
    category = "N/A"
    category_patterns = [
        (r"Small\s*Cap\s+Fund", "Small Cap Fund"),
        (r"Mid\s*Cap\s+Fund", "Mid Cap Fund"),
        (r"Large\s*Cap\s+Fund", "Large Cap Fund"),
        (r"Flexi\s*Cap\s+Fund", "Flexi Cap Fund"),
        (r"ELSS|Tax\s*Sav", "ELSS (Tax Savings)"),
    ]
    for pat, label in category_patterns:
        if re.search(pat, page_text, re.IGNORECASE):
            category = label
            break

    return {
        "expense_ratio": expense_ratio,
        "exit_load": exit_load,
        "minimum_sip": minimum_sip,
        "lock_in_period": lock_in_period,
        "riskometer": riskometer,
        "fund_name": fund_name,
        "category": category,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Holdings tab extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_holdings(page: Page) -> list[HoldingModel]:
    """
    Navigate to the 'Holdings' tab and return the top 3 holdings.

    INDmoney lists holdings as rows of (company name, percentage).
    We look for patterns like:
        "Firstsource Solutions Ltd  4.79%"
    in the full page text, then extract the first 3.
    """
    _click_tab(page, "Holdings")

    page_text = page.inner_text("body")

    # Pattern: a stock name followed by a percentage on the same or next line.
    # Stock names are typically title-case words (may include &, Ltd, etc.)
    holding_pattern = re.compile(
        r"([A-Z][A-Za-z0-9\s\&\.\(\)\-,]{3,60?})\s+(\d+\.?\d*)\s*%",
        re.MULTILINE,
    )
    matches = holding_pattern.findall(page_text)

    holdings = []
    seen_names: set[str] = set()
    rank = 1
    for raw_name, raw_pct in matches:
        name = raw_name.strip()
        # Skip very short, duplicate, or generic matches
        if len(name) < 4 or name in seen_names:
            continue
        # Skip lines that look like section headers / noise
        noise_keywords = ("Sector", "Asset", "Category", "Fund", "Holdings",
                          "Riskometer", "Overview", "Performance", "Compare",
                          "Mutual", "Direct", "Growth", "Returns")
        if any(kw.lower() in name.lower() for kw in noise_keywords):
            continue
        seen_names.add(name)
        pct = float(raw_pct)
        holdings.append(HoldingModel(rank=rank, name=name, percentage=pct))
        rank += 1
        if rank > 3:
            break

    if not holdings:
        logger.warning("  No holdings extracted — page structure may have changed.")

    return holdings


# ─────────────────────────────────────────────────────────────────────────────
# Core: scrape a single fund
# ─────────────────────────────────────────────────────────────────────────────

def scrape_fund(page: Page, fund_meta: dict) -> FundModel:
    """
    Scrape a single HDFC mutual fund from INDmoney.

    Args:
        page: Playwright Page instance (already opened).
        fund_meta: Entry from FUND_REGISTRY with keys fund_id, display_name, url.

    Returns:
        A validated FundModel instance.
    """
    fund_id = fund_meta["fund_id"]
    url = fund_meta["url"]

    logger.info(f"Scraping: {fund_meta['display_name']} ({fund_id})")
    logger.debug(f"  URL: {url}")

    # ── Navigate ──────────────────────────────────────────────────────────────
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    # Extra wait for JS-heavy SPA to settle
    page.wait_for_timeout(3_000)

    # ── Extract NAV ───────────────────────────────────────────────────────────
    logger.debug("  Extracting NAV...")
    nav = _extract_nav(page)
    logger.info(f"  NAV: ₹{nav.price} ({nav.date})")

    # ── Extract Overview fields ───────────────────────────────────────────────
    logger.debug("  Extracting overview fields (expense ratio, exit load, SIP, lock-in, riskometer)...")
    overview = _extract_overview(page)
    logger.info(f"  Expense Ratio: {overview['expense_ratio']} | "
                f"Exit Load: {overview['exit_load']} | "
                f"Min SIP: {overview['minimum_sip']} | "
                f"Lock-in: {overview['lock_in_period']} | "
                f"Risk: {overview['riskometer']}")

    # ── Extract Holdings ──────────────────────────────────────────────────────
    logger.debug("  Extracting top 3 holdings...")
    holdings = _extract_holdings(page)
    for h in holdings:
        logger.info(f"  Holding #{h.rank}: {h.name} ({h.percentage}%)")

    # ── Build and validate model ──────────────────────────────────────────────
    fund = FundModel(
        fund_id=fund_id,
        fund_name=overview.get("fund_name") or fund_meta["display_name"],
        category=overview.get("category", "N/A"),
        source_url=url,
        scraped_at=datetime.now(tz=timezone.utc),
        nav=nav,
        expense_ratio=overview["expense_ratio"],
        exit_load=overview["exit_load"],
        minimum_sip=overview["minimum_sip"],
        lock_in_period=overview["lock_in_period"],
        riskometer=overview["riskometer"],
        top_holdings=holdings,
    )

    return fund


# ─────────────────────────────────────────────────────────────────────────────
# Save a fund model to JSON
# ─────────────────────────────────────────────────────────────────────────────

def save_fund(fund: FundModel) -> Path:
    """
    Serialise and write a FundModel to raw_data/<fund_id>.json.
    Overwrites any existing file for the same fund_id.

    Returns the path of the written file.
    """
    output_path = RAW_DATA_DIR / f"{fund.fund_id}.json"
    data = json.loads(fund.model_dump_json(indent=2))
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    logger.success(f"  Saved → {output_path.relative_to(ROOT_DIR)}")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def run(fund_ids: Optional[list[str]] = None, headless: bool = True) -> list[Path]:
    """
    Run the scraper for the specified funds (or all funds if fund_ids is None).

    Args:
        fund_ids: List of fund_id strings to scrape. None = scrape all.
        headless: Whether to run the browser in headless mode.

    Returns:
        List of paths to the written JSON files.
    """
    targets = [
        f for f in FUND_REGISTRY
        if fund_ids is None or f["fund_id"] in fund_ids
    ]

    if not targets:
        logger.error(f"No matching funds found for IDs: {fund_ids}")
        logger.info(f"Available IDs: {[f['fund_id'] for f in FUND_REGISTRY]}")
        return []

    written_files: list[Path] = []
    failed_funds: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-IN",
        )
        page = context.new_page()

        for fund_meta in targets:
            try:
                fund = scrape_fund(page, fund_meta)
                path = save_fund(fund)
                written_files.append(path)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"Failed to scrape {fund_meta['fund_id']}: {exc}", exc_info=True
                )
                failed_funds.append(fund_meta["fund_id"])

        context.close()
        browser.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.success(f"Scrape complete: {len(written_files)} succeeded, {len(failed_funds)} failed.")
    if failed_funds:
        logger.warning(f"Failed funds: {failed_funds}")
    logger.info("=" * 60)

    return written_files


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 1: Scrape HDFC Mutual Fund data from INDmoney.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper.py                              # Scrape all 5 funds (headless)
  python scraper.py --headful                    # Scrape all funds (browser visible)
  python scraper.py --fund hdfc-small-cap-3580   # Scrape a single fund
  python scraper.py --fund hdfc-elss-taxsaver-2685 hdfc-mid-cap-3097
        """,
    )
    parser.add_argument(
        "--fund",
        nargs="+",
        metavar="FUND_ID",
        help="One or more fund IDs to scrape. Omit to scrape all funds.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        default=False,
        help="Run browser in visible (non-headless) mode for debugging.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    paths = run(
        fund_ids=args.fund if args.fund else None,
        headless=not args.headful,
    )
    sys.exit(0 if paths else 1)
