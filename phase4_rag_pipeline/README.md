# Phase 4 — RAG Pipeline & Groq LLM Integration

Implements the full Retrieval-Augmented Generation pipeline connecting ChromaDB (Phase 3) to Groq's `llama3-70b-8192` to answer user questions about HDFC Mutual Funds.

## Folder Structure

```
phase4_rag_pipeline/
├── rag_pipeline.py       ← Main RAG class (MutualFundRAG)
├── guardrails.py         ← PII detection + buy/sell refusal
├── prompt_templates.py   ← System prompt + context formatter
├── requirements.txt      ← Python dependencies
├── README.md
└── rag_pipeline.log      ← Rotating log (auto-created)
```

## Setup

```bash
cd phase4_rag_pipeline
pip install -r requirements.txt
```

Ensure `../.env` contains your Groq API key:
```
GROQ_API_KEY=gsk_your_key_here
```

> **Note:** Phases 1, 2, and 3 must have run first so the ChromaDB vector store is populated.

## Usage

### Interactive REPL (for testing)

```bash
python rag_pipeline.py
```

### Single query

```bash
python rag_pipeline.py --query "What is the NAV of HDFC Small Cap Fund?"
```

### Import in Phase 5 (Streamlit)

```python
from rag_pipeline import MutualFundRAG

rag = MutualFundRAG()
response = rag.answer("What is the expense ratio of HDFC ELSS?")
print(response.answer)
print(response.sources)   # list of {fund_name, url, scraped_at}
```

## Safety Guardrails

### 🚫 PII Detection (rejects query before LLM)
Blocks queries containing:
- PAN numbers (e.g. ABCDE1234F)
- Aadhaar numbers (12-digit groups)
- Bank/demat account numbers
- OTPs or verification codes
- Credit/debit card numbers
- IFSC codes
- Keywords like "my account", "my bank", "my OTP"

### 🚫 Buy/Sell Refusal (hardcoded in system prompt + guardrail)
Refuses any query asking to:
- Buy, purchase, invest, recommend funds
- Sell, redeem, exit, withdraw, switch
- "Which fund should I invest in?"
- "Is XYZ a good investment?"

### ✅ What it CAN answer
- NAV price and date
- Expense ratio
- Exit load
- Minimum SIP
- Lock-in period
- Riskometer level
- Top 3 holdings

## Response Format

Every response includes:
- **Answer** — direct factual answer
- **Source URL** — INDmoney link for the fund (cited in answer + returned as metadata)
- **Data last updated** — `scraped_at` timestamp from Phase 1

## Architecture

```
User Query
    │
    ▼  [guardrails.py]  — PII check → blocked? return refusal
    │                   — buy/sell check → blocked? return refusal
    │
    ▼  [rag_pipeline.py]  _detect_filters()  — intent-based metadata filter
    │
    ▼  ChromaDB query (Phase 3 vector store)  — top-5 semantic results
    │
    ▼  [prompt_templates.py]  — format_context() + system prompt
    │
    ▼  Groq llama3-70b-8192  — LLM inference (temp=0, factual)
    │
    ▼  RAGResponse(answer, sources, blocked)
```

## ChromaDB Metadata Filters (auto-detected from query)

| Query keyword       | Filter applied             |
|---------------------|----------------------------|
| "small cap"         | `category = small_cap`     |
| "mid cap"           | `category = mid_cap`       |
| "large cap"         | `category = large_cap`     |
| "flexi cap"         | `category = flexi_cap`     |
| "elss" / "tax saver"| `category = elss`          |
| "nav" / "price"     | `chunk_type = pricing`     |
| "expense ratio"     | `chunk_type = cost_fees`   |
| "sip" / "lock-in"   | `chunk_type = investment`  |
| "holding" / "stock" | `chunk_type = holdings`    |
| "risk"              | `chunk_type = overview`    |
