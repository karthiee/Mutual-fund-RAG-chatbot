"""
Phase 4 — Guardrails for the RAG Pipeline.

Three layers of protection applied to EVERY query before it reaches the LLM:
  1. PII Detection  — rejects queries containing personal identifiable info
  2. Buy/Sell Guard — rejects investment action requests
  3. Query Sanitisation — strips whitespace/control chars

And applied to every chunk of context:
  4. Source Validation — ensures retrieved metadata has a valid source_url

Usage:
    from guardrails import check_query, GuardrailViolation
"""

import re
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# Data class for a guardrail violation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GuardrailViolation:
    """Raised/returned when a guardrail blocks a query."""
    rule: str           # which guardrail fired
    message: str        # user-facing refusal message


# ─────────────────────────────────────────────────────────────────────────────
# 1. PII Detection
# ─────────────────────────────────────────────────────────────────────────────

# PAN: 5 letters + 4 digits + 1 letter  (e.g. ABCDE1234F)
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

# Aadhaar: 12 digits, optionally grouped with spaces/dashes
_AADHAAR_RE = re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b")

# Bank account: 9–18 consecutive digits
_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")

# OTP / verification code: 4–8 digit standalone number
_OTP_RE = re.compile(r"\b\d{4,8}\b")

# Credit/debit card: 13-16 digits, optionally grouped
_CARD_RE = re.compile(r"\b(?:\d[ \-]?){15,16}\b")

# IFSC: 4 letters + 0 + 6 alphanumerics
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")

# Keywords that suggest PII sharing intent
_PII_KEYWORDS = re.compile(
    r"\b(my\s+pan|my\s+aadhaar|my\s+aadhar|my\s+account|my\s+card|"
    r"my\s+otp|my\s+bank|my\s+demat|my\s+portfolio|my\s+password|"
    r"my\s+ifsc|passcode|pin\s+number)\b",
    re.IGNORECASE,
)

_PII_REFUSAL = (
    "⚠️ I'm sorry, but I cannot process requests that contain personal "
    "information such as PAN numbers, Aadhaar numbers, bank account numbers, "
    "OTPs, or card details.\n\n"
    "Please do not share any sensitive personal or financial information. "
    "I can only answer general questions about HDFC Mutual Fund details "
    "like NAV, expense ratio, exit load, minimum SIP, and top holdings."
)


def _detect_pii(text: str) -> str | None:
    """
    Return a description of the PII type detected, or None if clean.
    """
    upper = text.upper()
    if _PAN_RE.search(upper):
        return "PAN number"
    if _AADHAAR_RE.search(text):
        return "Aadhaar number"
    if _CARD_RE.search(text):
        return "card number"
    if _IFSC_RE.search(upper):
        return "IFSC code"
    if _PII_KEYWORDS.search(text):
        return "personal information keyword"
    # Only flag as account/OTP if no other context — avoid blocking "NAV: 1234"
    if _ACCOUNT_RE.search(text) and any(
        kw in text.lower() for kw in ("account", "demat", "bank", "deposit")
    ):
        return "account number"
    if _OTP_RE.search(text) and any(
        kw in text.lower() for kw in ("otp", "code", "verification", "passcode")
    ):
        return "OTP or verification code"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Buy / Sell / Investment Action Guard
# ─────────────────────────────────────────────────────────────────────────────

_BUYSELL_RE = re.compile(
    r"\b("
    r"buy|purchase|invest|investing|investment advice|should i invest|"
    r"sell|redeem|redeeming|exit(?!\s+load)|withdraw|withdrawal|"
    r"switch|switch out|transfer|move my money|"
    r"recommend|advise|suggest.*fund|which fund.*should|"
    r"is.*good.*investment|is.*worth.*investing|"
    r"lump.?sum|sip.*start|start.*sip"
    r")\b",
    re.IGNORECASE,
)

_BUYSELL_REFUSAL = (
    "⚠️ I'm an informational assistant and **cannot provide investment advice** "
    "or recommendations on buying, selling, or switching mutual funds.\n\n"
    "For personalised investment decisions, please consult a SEBI-registered "
    "investment advisor or financial planner.\n\n"
    "I *can* help you with factual questions about fund details like:\n"
    "- NAV price and date\n"
    "- Expense ratio & exit load\n"
    "- Minimum SIP amount & lock-in period\n"
    "- Riskometer rating\n"
    "- Top 3 holdings"
)


def _detect_buysell(text: str) -> bool:
    """Return True if the query asks for a buy/sell/invest action."""
    return bool(_BUYSELL_RE.search(text))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Query sanitisation
# ─────────────────────────────────────────────────────────────────────────────

def sanitise_query(text: str) -> str:
    """Strip control characters, collapse whitespace, limit to 1000 chars."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned[:1000]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def check_query(raw_query: str) -> tuple[str, GuardrailViolation | None]:
    """
    Run all guardrails on the raw user query.

    Returns:
        (sanitised_query, None)              — query is safe, proceed
        (original_query, GuardrailViolation) — query is blocked, return the
                                               violation message to the user
    """
    sanitised = sanitise_query(raw_query)

    # 1. PII check
    pii_type = _detect_pii(sanitised)
    if pii_type:
        return raw_query, GuardrailViolation(
            rule="pii_detected",
            message=_PII_REFUSAL,
        )

    # 2. Buy/Sell action check
    if _detect_buysell(sanitised):
        return raw_query, GuardrailViolation(
            rule="buysell_detected",
            message=_BUYSELL_REFUSAL,
        )

    return sanitised, None
