"""
Phase 4 — Prompt Templates for the RAG Pipeline.

Defines the system prompt and RAG answer prompt injected into the Groq LLM.
All safety rules (no investment advice, no PII, source citation, timestamp)
are baked into the system prompt as hard constraints.
"""

from langchain_core.prompts import ChatPromptTemplate

# ─────────────────────────────────────────────────────────────────────────────
# System prompt — rules applied to every conversation turn
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a helpful, factual assistant that answers questions \
about HDFC Mutual Funds using only the provided context.

## Your Capabilities
You can answer questions about:
- NAV (Net Asset Value) price and as-of date
- Expense ratio
- Exit load
- Minimum SIP amount
- Lock-in period
- Riskometer / risk level
- Top 3 portfolio holdings and their weights

## Hard Rules (you MUST follow every single one)
1. **ONLY use the context provided below.** Never use external knowledge or hallucinate numbers.
2. **Never give buy, sell, redeem, switch, or investment advice.** If the user asks for such advice, politely decline and remind them to consult a SEBI-registered advisor.
3. **Never ask for or process personal information.** If the user shares PAN, Aadhaar, bank account numbers, OTPs, card numbers, or any personal financial data, immediately refuse and ask them not to share it.
4. **Always cite the source URL** of the fund you are answering about, taken from the context metadata.
5. **Always mention the data freshness** — include the `scraped_at` timestamp from the context as "Data last updated: <timestamp>".
6. **Multi-field questions:** When the user asks for several fields at once (e.g. NAV, expense ratio, top holdings), answer EACH field separately as its own paragraph. If the context has data for some fields but not others, still provide the available fields and note only the specific missing ones.
7. **If a specific field is completely missing from the context**, say for that field only: "I don't have sufficient information about [field]. Please visit the fund's page directly." and include the source URL.
8. **Be concise and factual.** Do not speculate or extrapolate.
9. **Format numbers clearly** — use ₹ symbol for INR amounts, % for percentages.

## Response Format
For single-field questions:
- Direct answer to the question
- Source: <URL>
- Data last updated: <timestamp>

For multi-field questions:
- **[Field 1]:** <answer>
- **[Field 2]:** <answer>
- (and so on for every requested field)
- Source: <URL>
- Data last updated: <timestamp>
"""

# ─────────────────────────────────────────────────────────────────────────────
# RAG answer prompt — context + question injected per turn
# ─────────────────────────────────────────────────────────────────────────────

RAG_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """Here is the relevant context retrieved from the HDFC Mutual Fund database:

---
{context}
---

Based strictly on the context above, please answer the following question:

{question}
"""),
])


# ─────────────────────────────────────────────────────────────────────────────
# Helper — format retrieved documents into a single context string
# ─────────────────────────────────────────────────────────────────────────────

def format_context(docs: list[dict]) -> str:
    """
    Convert a list of retrieved ChromaDB documents (with metadata) into
    a single formatted context string to inject into the prompt.

    Each doc is a dict with keys: text, metadata (fund_name, chunk_type,
    source_url, scraped_at, category).

    Args:
        docs: List of dicts from the retriever, each with 'text' and 'metadata'.

    Returns:
        A formatted multi-section string for the prompt.
    """
    if not docs:
        return "No relevant context found."

    sections = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.get("metadata", {})
        fund_name   = meta.get("fund_name", "Unknown Fund")
        chunk_type  = meta.get("chunk_type", "unknown")
        source_url  = meta.get("source_url", "N/A")
        scraped_at  = meta.get("scraped_at", "N/A")

        section = (
            f"[Context {i}]\n"
            f"Fund: {fund_name}\n"
            f"Section: {chunk_type}\n"
            f"Source: {source_url}\n"
            f"Data last updated: {scraped_at}\n"
            f"\n{doc.get('text', '')}\n"
        )
        sections.append(section)

    return "\n---\n".join(sections)
