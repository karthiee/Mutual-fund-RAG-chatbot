"""
Phase 4 — RAG Pipeline with Groq LLM.

Orchestrates the full Retrieval-Augmented Generation pipeline:
  1. Guardrails     — PII + buy/sell check on user query
  2. Retrieval      — semantic search in ChromaDB (Phase 3)
  3. Prompt build   — inject retrieved context + safety rules
  4. LLM inference  — Groq llama3-70b-8192 via LangChain
  5. Response post  — append source URLs + timestamps

Usage (standalone test):
    python rag_pipeline.py
    python rag_pipeline.py --query "What is the NAV of HDFC Small Cap Fund?"

Usage (imported by Phase 5 Streamlit app):
    from rag_pipeline import MutualFundRAG
    rag = MutualFundRAG()
    response = rag.answer("What is the expense ratio of HDFC ELSS?")
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

# Project-relative paths
ROOT_DIR         = Path(__file__).parent
VECTOR_STORE_DIR = ROOT_DIR.parent / "phase3_embedder" / "vector_store"
VECTOR_STORE_LIB = ROOT_DIR.parent / "phase3_embedder"
ENV_PATH         = ROOT_DIR.parent / ".env"

# Load .env (GROQ_API_KEY)
load_dotenv(ENV_PATH)

# ── Logging ───────────────────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
logger.add(ROOT_DIR / "rag_pipeline.log", level="DEBUG", rotation="5 MB", retention="7 days")

# ── Constants ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL   = "all-MiniLM-L6-v2"
GROQ_MODEL        = "llama-3.3-70b-versatile"
TOP_K_RESULTS     = 5
MAX_HISTORY_TURNS = 10


# ─────────────────────────────────────────────────────────────────────────────
# Response dataclass
# ─────────────────────────────────────────────────────────────────────────────

class RAGResponse:
    """Structured response object returned by MutualFundRAG.answer()."""

    def __init__(
        self,
        answer: str,
        sources: list[dict],
        blocked: bool = False,
        block_reason: Optional[str] = None,
    ):
        self.answer       = answer            # LLM answer text
        self.sources      = sources           # list of {fund_name, url, scraped_at, chunk_type}
        self.blocked      = blocked           # True if a guardrail blocked the query
        self.block_reason = block_reason      # Rule name if blocked

    def __str__(self) -> str:
        return self.answer


# ─────────────────────────────────────────────────────────────────────────────
# Main RAG class
# ─────────────────────────────────────────────────────────────────────────────

class MutualFundRAG:
    """
    End-to-end RAG pipeline for HDFC Mutual Fund queries.

    Initialise once (model loading takes a few seconds), then call answer()
    for each user query.

    Args:
        top_k: Number of ChromaDB results to retrieve per query.
    """

    def __init__(self, top_k: int = TOP_K_RESULTS):
        self._top_k = top_k
        self._model = None        # SentenceTransformer — lazy loaded
        self._store = None        # SimpleVectorStore — lazy loaded
        self._llm = None          # Groq ChatLLM — lazy loaded
        self._history: list[dict] = []  # conversation history

    # ── Lazy loaders ──────────────────────────────────────────────────────────

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            self._model = SentenceTransformer(EMBEDDING_MODEL)
        return self._model

    def _get_store(self):
        if self._store is None:
            import sys
            sys.path.insert(0, str(VECTOR_STORE_LIB))
            from vector_store_lib import SimpleVectorStore  # noqa
            if not VECTOR_STORE_DIR.exists():
                raise FileNotFoundError(
                    f"Vector store not found at {VECTOR_STORE_DIR}. "
                    "Run phase3_embedder/embedder.py first."
                )
            self._store = SimpleVectorStore(VECTOR_STORE_DIR)
            logger.info(
                f"SimpleVectorStore loaded ({self._store.count()} documents)"
            )
        return self._store

    def _get_llm(self):
        if self._llm is None:
            from langchain_groq import ChatGroq  # noqa: PLC0415
            api_key = (
                os.environ.get("GROQ_API_KEY")
                or os.environ.get("groq_API_KEY")   # match .env casing
            )
            if not api_key:
                raise ValueError(
                    "GROQ_API_KEY not found. "
                    "Add it to the .env file as: GROQ_API_KEY=your_key"
                )
            self._llm = ChatGroq(
                model=GROQ_MODEL,
                api_key=api_key,
                temperature=0,          # deterministic factual answers
                max_tokens=1024,
            )
            logger.info(f"Groq LLM initialised: {GROQ_MODEL}")
        return self._llm

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def _retrieve(self, query: str, filters: Optional[dict] = None) -> list[dict]:
        """
        Embed the query and retrieve the top-K most similar chunks.
        """
        model = self._get_model()
        store = self._get_store()

        embedding = model.encode([query]).tolist()

        results = store.query(
            query_embedding=embedding,
            n_results=min(self._top_k, store.count()),
            where=filters,
        )

        docs = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = round(1 - dist, 4)
            docs.append({
                "text": doc,
                "metadata": meta,
                "similarity": similarity,
            })
            logger.debug(
                f"  Retrieved: {meta.get('fund_name')} [{meta.get('chunk_type')}] "
                f"sim={similarity}"
            )

        return docs

    # ── Intent-based metadata filter ──────────────────────────────────────────

    @staticmethod
    def _detect_filters(query: str) -> Optional[dict]:
        """
        Detect fund category and chunk type from the query for metadata filtering.
        Returns a ChromaDB $and filter or None.
        """
        query_lower = query.lower()

        category_map = {
            "small cap":  "small_cap",
            "mid cap":    "mid_cap",
            "large cap":  "large_cap",
            "flexi cap":  "flexi_cap",
            "elss":       "elss",
            "tax saver":  "elss",
            "top 100":    "large_cap",
        }
        chunk_map = {
            ("nav", "price", "current value", "net asset"):     "pricing",
            ("expense ratio", "ter", "charges", "fee"):         "cost_fees",
            ("exit load",):                                      "cost_fees",
            ("sip", "minimum", "lock-in", "lock in"):           "investment",
            ("holding", "stock", "portfolio", "top 3"):         "holdings",
            ("risk", "riskometer",):                            "overview",
        }

        detected_category = None
        for keyword, slug in category_map.items():
            if keyword in query_lower:
                detected_category = slug
                break

        detected_chunk = None
        for keywords, chunk_type in chunk_map.items():
            if any(kw in query_lower for kw in keywords):
                detected_chunk = chunk_type
                break

        conditions = []
        if detected_category:
            conditions.append({"category": {"$eq": detected_category}})
        if detected_chunk:
            conditions.append({"chunk_type": {"$eq": detected_chunk}})

        if len(conditions) == 2:
            return {"$and": conditions}
        elif len(conditions) == 1:
            return conditions[0]
        return None

    # ── Context formatting ────────────────────────────────────────────────────

    @staticmethod
    def _build_context(docs: list[dict]) -> str:
        """Format retrieved docs into a context string for the prompt."""
        from prompt_templates import format_context  # noqa: PLC0415
        return format_context(docs)

    # ── Source metadata extraction ────────────────────────────────────────────

    @staticmethod
    def _extract_sources(docs: list[dict]) -> list[dict]:
        """
        Deduplicate and extract source references from retrieved docs.
        Returns a list of {fund_name, url, scraped_at, chunk_type}.
        """
        seen = set()
        sources = []
        for doc in docs:
            meta = doc.get("metadata", {})
            url = meta.get("source_url", "")
            if url and url not in seen:
                seen.add(url)
                sources.append({
                    "fund_name":  meta.get("fund_name", "Unknown"),
                    "url":        url,
                    "scraped_at": meta.get("scraped_at", "N/A"),
                    "chunk_type": meta.get("chunk_type", "N/A"),
                })
        return sources

    # ── History management ────────────────────────────────────────────────────

    def _build_messages(self, context: str, question: str) -> list:
        """
        Build the message list for the LLM:
          [system_prompt, ...history, human_with_context]
        """
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage  # noqa: PLC0415
        from prompt_templates import SYSTEM_PROMPT  # noqa: PLC0415

        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        # Inject previous conversation turns (trimmed)
        for turn in self._history[-MAX_HISTORY_TURNS:]:
            if turn["role"] == "user":
                messages.append(HumanMessage(content=turn["content"]))
            else:
                messages.append(AIMessage(content=turn["content"]))

        # Current user message with context
        human_msg = (
            f"Here is the relevant context retrieved from the HDFC Mutual Fund database:\n\n"
            f"---\n{context}\n---\n\n"
            f"Based strictly on the context above, please answer the following question:\n\n"
            f"{question}"
        )
        messages.append(HumanMessage(content=human_msg))
        return messages

    # ── Public: answer a single query ─────────────────────────────────────────

    def answer(self, raw_query: str) -> "RAGResponse":
        """
        Process a user query end-to-end through the RAG pipeline.

        Steps:
          1. Guardrails check (PII + buy/sell)
          2. Retrieve relevant chunks from ChromaDB
          3. Build LLM messages with context
          4. Call Groq LLM
          5. Update conversation history
          6. Return structured RAGResponse

        Args:
            raw_query: Raw user input string.

        Returns:
            RAGResponse with answer, sources, and optional block info.
        """
        from guardrails import check_query  # noqa: PLC0415
        from langchain_core.messages import AIMessage  # noqa: PLC0415

        logger.info(f"Query: {raw_query[:120]}")

        # ── Step 1: Guardrails ────────────────────────────────────────────────
        sanitised_query, violation = check_query(raw_query)
        if violation:
            logger.warning(f"Guardrail triggered: {violation.rule}")
            return RAGResponse(
                answer=violation.message,
                sources=[],
                blocked=True,
                block_reason=violation.rule,
            )

        # ── Step 2: Retrieve ──────────────────────────────────────────────────
        filters = self._detect_filters(sanitised_query)
        logger.debug(f"Metadata filters: {filters}")
        docs = self._retrieve(sanitised_query, filters=filters)

        if not docs:
            no_data_msg = (
                "I'm sorry, I couldn't find relevant information for your query "
                "in the HDFC Mutual Fund database. Please try rephrasing your "
                "question or visit https://www.indmoney.com/mutual-funds for "
                "up-to-date fund details."
            )
            return RAGResponse(answer=no_data_msg, sources=[])

        # ── Step 3: Build context + messages ──────────────────────────────────
        context  = self._build_context(docs)
        messages = self._build_messages(context, sanitised_query)

        # ── Step 4: LLM call ──────────────────────────────────────────────────
        llm = self._get_llm()
        logger.info("Calling Groq LLM…")
        response = llm.invoke(messages)
        answer_text = response.content if hasattr(response, "content") else str(response)
        logger.info(f"LLM response received ({len(answer_text)} chars)")

        # ── Step 5: Update history ────────────────────────────────────────────
        self._history.append({"role": "user",      "content": sanitised_query})
        self._history.append({"role": "assistant",  "content": answer_text})

        # ── Step 6: Build and return response ─────────────────────────────────
        sources = self._extract_sources(docs)
        return RAGResponse(answer=answer_text, sources=sources)

    def clear_history(self) -> None:
        """Reset the conversation history."""
        self._history = []
        logger.debug("Conversation history cleared.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI — quick test without Streamlit
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 4: Test the RAG pipeline from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rag_pipeline.py
  python rag_pipeline.py --query "What is the NAV of HDFC Mid Cap Fund?"
  python rag_pipeline.py --query "Tell me the expense ratio and exit load for HDFC ELSS"
        """,
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        default=None,
        help="Single query to run. If omitted, starts an interactive REPL.",
    )
    return parser.parse_args()


def _interactive_repl(rag: MutualFundRAG) -> None:
    """Simple interactive loop for testing."""
    print("\n🤖 HDFC Mutual Fund RAG Chatbot (Phase 4 Test)")
    print("=" * 55)
    print("Type 'quit' or 'exit' to stop | 'clear' to reset history")
    print("=" * 55)

    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        if query.lower() == "clear":
            rag.clear_history()
            print("Conversation history cleared.")
            continue

        response = rag.answer(query)
        print(f"\n🤖 Bot: {response.answer}")
        if response.sources and not response.blocked:
            print("\n📎 Sources:")
            for s in response.sources:
                print(f"   • {s['fund_name']}: {s['url']}")
                print(f"     Data last updated: {s['scraped_at']}")


if __name__ == "__main__":
    # Add current dir to path so local imports work when run directly
    sys.path.insert(0, str(ROOT_DIR))
    args = _parse_args()
    rag = MutualFundRAG()

    if args.query:
        response = rag.answer(args.query)
        print(f"\nAnswer:\n{response.answer}")
        if response.sources:
            print("\nSources:")
            for s in response.sources:
                print(f"  • {s['fund_name']}: {s['url']}  (updated: {s['scraped_at']})")
    else:
        _interactive_repl(rag)
