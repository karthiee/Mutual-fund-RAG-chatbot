# Phase 3 — Embedding & Vector Store

Reads the JSONL corpus from Phase 2, generates vector embeddings using `all-MiniLM-L6-v2`, and stores them in a persistent **ChromaDB** collection for semantic retrieval in Phase 4.

## Folder Structure

```
phase3_embedder/
├── embedder.py         ← Main entry point (run this)
├── requirements.txt    ← Python dependencies
├── embedder.log        ← Rotating log file (auto-created)
└── vector_store/
    ├── README.md
    ├── chroma.sqlite3  ← ChromaDB database (auto-created)
    └── <uuid>/         ← Embedding segments (auto-created)
```

## Setup

```bash
cd phase3_embedder
pip install -r requirements.txt
```

> **Note:** Phase 2 must have run first so that `phase2_processor/processed_data/chunks.jsonl` exists.

## Usage

### Embed all chunks (safe to re-run — upsert mode)

```bash
python embedder.py
```

### Full reset and re-index from scratch

```bash
python embedder.py --reset
```

### Embed + run a test query to verify

```bash
python embedder.py --query "What is the NAV of HDFC Small Cap Fund?"
```

### Custom input file

```bash
python embedder.py --input ../phase2_processor/processed_data/chunks.jsonl
```

## Architecture

| Component         | Choice                         | Reason                                              |
|-------------------|--------------------------------|-----------------------------------------------------|
| Embedding model   | `all-MiniLM-L6-v2`            | Fast, local, free, 384-dim, good for financial text |
| Vector dimension  | 384                            | Compact but high quality                            |
| Distance metric   | Cosine                         | Standard for semantic text similarity               |
| Vector store      | ChromaDB (persistent)         | Easy Python integration, metadata filtering         |
| Collection        | `mutual_funds`                | Single collection for all 5 funds                   |

## ChromaDB Collection Design

```
Collection: "mutual_funds"
  Documents : 25 (5 funds × 5 chunk types)
  
  Metadata filters available:
    fund_id     : "hdfc-small-cap-3580" etc.
    category    : "small_cap" | "mid_cap" | "large_cap" | "elss" | "flexi_cap"
    chunk_type  : "overview" | "pricing" | "cost_fees" | "investment" | "holdings"
    source_url  : full INDmoney URL
    scraped_at  : ISO timestamp
    processed_at: ISO timestamp
```

## Retrieval Example (Phase 4 preview)

```python
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="vector_store")
collection = client.get_collection("mutual_funds")

query = "What is the expense ratio of HDFC Small Cap Fund?"
embedding = model.encode([query]).tolist()

results = collection.query(
    query_embeddings=embedding,
    n_results=3,
    where={"category": "small_cap"},    # optional metadata filter
    include=["documents", "metadatas", "distances"],
)
```

## Notes

- **Upsert** is idempotent — re-running without `--reset` updates existing chunks without duplicating.
- Phase 6 (Scheduler) will call `embedder.py` automatically after Phase 2 runs.
- The embedding model downloads (~90 MB) from Hugging Face on first run and caches locally.
