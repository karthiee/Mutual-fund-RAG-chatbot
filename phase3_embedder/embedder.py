"""
Phase 3 — Embedding & Vector Store.

Reads the JSONL chunks produced by Phase 2 (processed_data/chunks.jsonl),
generates sentence embeddings for each chunk, and stores them in a persistent
SimpleVectorStore (JSON + NumPy) for semantic retrieval in Phase 4.

Usage:
    python embedder.py                   # Embed all chunks (upsert mode)
    python embedder.py --reset           # Drop existing collection and re-embed
    python embedder.py --query "What is the NAV of HDFC Small Cap?"   # Test query

Architecture:
    Embedding model : sentence-transformers/all-MiniLM-L6-v2 (local, 384-dim)
    Vector store    : SimpleVectorStore (JSON + NumPy, no ChromaDB dependency)
    Store directory : vector_store/
    Document IDs    : chunk_id from Phase 2 (e.g. "hdfc-small-cap-3580__pricing")
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Default paths ─────────────────────────────────────────────────────────────
ROOT_DIR         = Path(__file__).parent
DEFAULT_CHUNKS   = ROOT_DIR.parent / "phase2_processor" / "processed_data" / "chunks.jsonl"
VECTOR_STORE_DIR = ROOT_DIR / "vector_store"

# ── Embedding model ────────────────────────────────────────────────────────────
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"

# ── Batch size ─────────────────────────────────────────────────────────────────
BATCH_SIZE       = 10

# ── Logging ───────────────────────────────────────────────────────────────────
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
logger.add(ROOT_DIR / "embedder.log", level="DEBUG", rotation="5 MB", retention="7 days")


# ─────────────────────────────────────────────────────────────────────────────
# Lazy imports
# ─────────────────────────────────────────────────────────────────────────────

def _get_embedding_model():
    from sentence_transformers import SentenceTransformer  # noqa
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    logger.success(f"Embedding model loaded (dim={model.get_sentence_embedding_dimension()})")
    return model


def _get_vector_store(reset: bool = False):
    sys.path.insert(0, str(ROOT_DIR))
    from vector_store_lib import SimpleVectorStore  # noqa
    store = SimpleVectorStore(VECTOR_STORE_DIR)
    if reset:
        store.delete_all()
        logger.warning("Vector store reset — all embeddings cleared.")
    logger.info(f"Vector store loaded ({store.count()} existing documents).")
    return store


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Load chunks
# ─────────────────────────────────────────────────────────────────────────────

def load_chunks(jsonl_path: Path) -> list[dict]:
    if not jsonl_path.exists():
        logger.error(
            f"Chunks file not found: {jsonl_path}\n"
            "Run phase2_processor/processor.py first."
        )
        return []
    chunks = []
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(f"Skipping malformed line {line_no}: {exc}")
    logger.info(f"Loaded {len(chunks)} chunks from {jsonl_path.name}")
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Embed and upsert
# ─────────────────────────────────────────────────────────────────────────────

def embed_and_store(chunks: list[dict], store, model, batch_size: int = BATCH_SIZE) -> int:
    total = len(chunks)
    upserted = 0
    failed = 0

    for batch_start in range(0, total, batch_size):
        batch    = chunks[batch_start : batch_start + batch_size]
        batch_end = min(batch_start + batch_size, total)
        logger.info(f"Embedding batch {batch_start + 1}-{batch_end} of {total}...")

        ids, documents, metadatas, texts_to_embed = [], [], [], []

        for chunk in batch:
            try:
                meta = chunk["metadata"]
                flat_meta = {
                    "fund_id":      meta["fund_id"],
                    "fund_name":    meta["fund_name"],
                    "category":     meta["category"],
                    "chunk_type":   meta["chunk_type"],
                    "source_url":   meta["source_url"],
                    "scraped_at":   meta["scraped_at"],
                    "processed_at": meta["processed_at"],
                }
                ids.append(chunk["chunk_id"])
                documents.append(chunk["text"])
                metadatas.append(flat_meta)
                texts_to_embed.append(chunk["text"])
            except KeyError as exc:
                logger.warning(f"Malformed chunk (missing key {exc}) -- skipped")
                failed += 1
                continue

        if not ids:
            continue

        embeddings = model.encode(texts_to_embed, show_progress_bar=False).tolist()
        store.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        upserted += len(ids)

    logger.success(f"Embedding complete: {upserted} upserted, {failed} failed.")
    return upserted


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Optional test query
# ─────────────────────────────────────────────────────────────────────────────

def query_store(store, model, query_text: str, n_results: int = 3) -> None:
    logger.info(f"\nTest query: '{query_text}'")
    q_embed = model.encode([query_text]).tolist()
    results = store.query(query_embedding=q_embed, n_results=n_results)

    logger.info(f"Top {n_results} results:")
    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        sim = 1 - dist
        logger.info(
            f"  [{i+1}] {meta['chunk_type']} | {meta['fund_name']} | similarity={sim:.3f}"
        )
        logger.info(f"       {doc[:200].replace(chr(10), ' ')}...")


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run(
    chunks_path: Path = DEFAULT_CHUNKS,
    reset: bool = False,
    test_query: Optional[str] = None,
) -> int:
    logger.info("=" * 60)
    logger.info("Phase 3 -- Embedding & Vector Store")
    logger.info(f"Chunks file  : {chunks_path}")
    logger.info(f"Vector store : {VECTOR_STORE_DIR}")
    logger.info(f"Model        : {EMBEDDING_MODEL}")
    logger.info(f"Reset mode   : {reset}")
    logger.info("=" * 60)

    chunks = load_chunks(chunks_path)
    if not chunks:
        logger.error("No chunks to embed. Aborting.")
        return 0

    model  = _get_embedding_model()
    store  = _get_vector_store(reset=reset)
    n      = embed_and_store(chunks, store, model)

    logger.info("=" * 60)
    logger.success(f"Phase 3 complete: {n} chunks indexed. Total in store: {store.count()}")
    logger.info("=" * 60)

    if test_query:
        query_store(store, model, test_query)

    return n


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 3: Embed chunks into vector store.")
    parser.add_argument("--input", "-i", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument("--reset", action="store_true", default=False)
    parser.add_argument("--query", "-q", type=str, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    n = run(chunks_path=args.input, reset=args.reset, test_query=args.query)
    sys.exit(0 if n > 0 else 1)
