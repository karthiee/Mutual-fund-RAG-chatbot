"""
Pydantic data models for HDFC Mutual Fund data (Phase 1).

These models define and validate the structure of scraped fund data
before it is written to raw JSON files.
"""

from datetime import datetime, date, timezone
from typing import Optional
from pydantic import BaseModel, Field


class HoldingModel(BaseModel):
    """Represents a single portfolio holding within a fund."""
    rank: int = Field(..., ge=1, le=3, description="Rank of the holding (1-3)")
    name: str = Field(..., description="Name of the stock or asset")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Holding weight as a percentage")


class NAVModel(BaseModel):
    """Net Asset Value details for a fund."""
    price: float = Field(..., gt=0, description="NAV price in INR")
    currency: str = Field(default="INR", description="Currency of NAV")
    nav_date: date = Field(..., description="Date for which NAV is reported")


class FundModel(BaseModel):
    """
    Complete data model for a single HDFC Mutual Fund.
    Populated by the Playwright scraper and validated before writing to JSON.
    """
    fund_id: str = Field(..., description="Unique identifier slug for the fund")
    fund_name: str = Field(..., description="Full official name of the fund")
    category: str = Field(
        ...,
        description="Fund category (e.g. 'Small Cap Fund', 'ELSS (Tax Savings)')"
    )
    source_url: str = Field(..., description="INDmoney URL of the fund page")
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="UTC timestamp when the data was scraped"
    )

    nav: NAVModel = Field(..., description="NAV price details")
    expense_ratio: Optional[str] = Field(None, description="Expense ratio as string (e.g. '0.67%')")
    exit_load: Optional[str] = Field(None, description="Exit load description")
    minimum_sip: Optional[str] = Field(None, description="Minimum SIP amount (e.g. '₹100')")
    lock_in_period: Optional[str] = Field(None, description="Lock-in period (e.g. '3 Years' or 'None')")
    riskometer: Optional[str] = Field(None, description="Risk level (e.g. 'Very High Risk')")
    top_holdings: list[HoldingModel] = Field(
        default_factory=list,
        description="Top 3 portfolio holdings"
    )

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat(), date: lambda v: v.isoformat()}}


# ── Fund registry ────────────────────────────────────────────────────────────
# Central list of all 5 HDFC funds to be scraped.

FUND_REGISTRY = [
    {
        "fund_id": "hdfc-small-cap-3580",
        "display_name": "HDFC Small Cap Fund",
        "url": "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
    },
    {
        "fund_id": "hdfc-flexi-cap-3184",
        "display_name": "HDFC Flexi Cap Fund",
        "url": "https://www.indmoney.com/mutual-funds/hdfc-flexi-cap-fund-direct-plan-growth-option-3184",
    },
    {
        "fund_id": "hdfc-elss-taxsaver-2685",
        "display_name": "HDFC ELSS Taxsaver",
        "url": "https://www.indmoney.com/mutual-funds/hdfc-elss-taxsaver-direct-plan-growth-option-2685",
    },
    {
        "fund_id": "hdfc-mid-cap-3097",
        "display_name": "HDFC Mid Cap Opportunities Fund",
        "url": "https://www.indmoney.com/mutual-funds/hdfc-mid-cap-fund-direct-plan-growth-option-3097",
    },
    {
        "fund_id": "hdfc-large-cap-2989",
        "display_name": "HDFC Top 100 Fund (Large Cap)",
        "url": "https://www.indmoney.com/mutual-funds/hdfc-large-cap-fund-direct-plan-growth-option-2989",
    },
]
