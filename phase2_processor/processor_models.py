"""
Pydantic data models for Phase 2 — Data Processing & Structuring.

Defines:
  - ChunkType enum   — the 5 semantic chunk categories per fund
  - RawFundData      — mirrors the Phase 1 FundModel for loading JSON
  - DocumentChunk    — a single processed chunk ready for embedding
"""

from datetime import datetime, date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ── Chunk types ───────────────────────────────────────────────────────────────

class ChunkType(str, Enum):
    """
    The 5 semantic sections each fund is split into.
    These map directly to what a user might ask about.
    """
    OVERVIEW    = "overview"      # Fund name, category, riskometer
    PRICING     = "pricing"       # NAV price + date
    COST_FEES   = "cost_fees"     # Expense ratio + exit load
    INVESTMENT  = "investment"    # Minimum SIP + lock-in period
    HOLDINGS    = "holdings"      # Top 3 stock holdings


# ── Raw fund data (mirrors Phase 1 FundModel) ─────────────────────────────────

class RawHolding(BaseModel):
    rank: int
    name: str
    percentage: float


class RawNAV(BaseModel):
    price: float
    currency: str = "INR"
    nav_date: date


class RawFundData(BaseModel):
    """
    Schema used to load and validate a Phase 1 raw JSON file.
    Mirrors phase1_scraper/models.py FundModel.
    """
    fund_id: str
    fund_name: str
    category: str
    source_url: str
    scraped_at: datetime
    nav: RawNAV
    expense_ratio: Optional[str] = None
    exit_load: Optional[str] = None
    minimum_sip: Optional[str] = None
    lock_in_period: Optional[str] = None
    riskometer: Optional[str] = None
    top_holdings: list[RawHolding] = Field(default_factory=list)


# ── Processed document chunk ──────────────────────────────────────────────────

class ChunkMetadata(BaseModel):
    """Metadata stored alongside every document chunk in the vector store."""
    fund_id: str                    # e.g. "hdfc-small-cap-3580"
    fund_name: str                  # Full fund name
    category: str                   # e.g. "Small Cap Fund"
    chunk_type: ChunkType           # Which of the 5 sections this is
    source_url: str                 # INDmoney page URL
    scraped_at: str                 # ISO datetime string from Phase 1
    processed_at: str               # ISO datetime when chunk was created


class DocumentChunk(BaseModel):
    """
    A single processed, embeddable text chunk with metadata.
    This is the unit that gets stored in the JSONL output and
    later embedded into ChromaDB in Phase 3.
    """
    chunk_id: str = Field(
        ...,
        description="Unique ID: <fund_id>__<chunk_type>  e.g. 'hdfc-small-cap-3580__overview'"
    )
    text: str = Field(
        ...,
        description="Natural-language text ready for embedding"
    )
    metadata: ChunkMetadata

    class Config:
        use_enum_values = True  # store enum as string in JSON
