"""
SimpleVectorStore — lightweight JSON + NumPy vector store.

Replaces ChromaDB for Python 3.14 compatibility.
Stores embeddings as a JSON file + numpy .npy array.
Supports cosine similarity search with optional metadata filtering.

Usage:
    from vector_store import SimpleVectorStore
    store = SimpleVectorStore("vector_store")
    store.upsert(ids, embeddings, documents, metadatas)
    results = store.query(query_embedding, n_results=5)
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np

STORE_DIR_DEFAULT = Path(__file__).parent / "vector_store"


class SimpleVectorStore:
    """
    A simple persistent vector store backed by:
      - metadata.json  : list of {id, document, metadata} dicts
      - embeddings.npy : float32 numpy array, shape (N, D)
    """

    def __init__(self, store_dir: str | Path = STORE_DIR_DEFAULT):
        self.store_dir    = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path   = self.store_dir / "metadata.json"
        self._embed_path  = self.store_dir / "embeddings.npy"
        self._records: list[dict] = []       # [{id, document, metadata}]
        self._embeddings: Optional[np.ndarray] = None  # shape (N, D)
        self._load()

    # ── Persistence ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._meta_path.exists():
            with self._meta_path.open("r", encoding="utf-8") as f:
                self._records = json.load(f)
        if self._embed_path.exists() and self._records:
            self._embeddings = np.load(str(self._embed_path))
        else:
            self._embeddings = np.empty((0, 0), dtype=np.float32)

    def _save(self) -> None:
        with self._meta_path.open("w", encoding="utf-8") as f:
            json.dump(self._records, f, ensure_ascii=False, indent=2)
        if self._embeddings is not None and self._embeddings.size > 0:
            np.save(str(self._embed_path), self._embeddings)

    # ── Mutation ────────────────────────────────────────────────────────────

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Insert or update records by ID."""
        embed_arr = np.array(embeddings, dtype=np.float32)

        # Build index {id -> position}
        id_to_idx: dict[str, int] = {r["id"]: i for i, r in enumerate(self._records)}

        new_records = []
        new_embeds  = []
        update_ids: dict[int, tuple] = {}  # idx -> (record, embed_row)

        for i, doc_id in enumerate(ids):
            record = {"id": doc_id, "document": documents[i], "metadata": metadatas[i]}
            if doc_id in id_to_idx:
                update_ids[id_to_idx[doc_id]] = (record, embed_arr[i])
            else:
                new_records.append(record)
                new_embeds.append(embed_arr[i])

        # Apply updates in-place
        for idx, (rec, emb) in update_ids.items():
            self._records[idx] = rec
            self._embeddings[idx] = emb  # type: ignore[index]

        # Append new records
        if new_records:
            self._records.extend(new_records)
            new_embed_arr = np.array(new_embeds, dtype=np.float32)
            if self._embeddings is None or self._embeddings.size == 0:
                self._embeddings = new_embed_arr
            else:
                self._embeddings = np.vstack([self._embeddings, new_embed_arr])

        self._save()

    def delete_all(self) -> None:
        """Drop all records and embeddings."""
        self._records = []
        self._embeddings = np.empty((0, 0), dtype=np.float32)
        if self._meta_path.exists():
            self._meta_path.unlink()
        if self._embed_path.exists():
            self._embed_path.unlink()

    # ── Query ───────────────────────────────────────────────────────────────

    def count(self) -> int:
        return len(self._records)

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> dict:
        """
        Return top-N most similar records by cosine similarity.

        Args:
            query_embedding: 1D list of floats.
            n_results:       Number of results to return.
            where:           Optional simple equality filter, e.g.
                             {"category": "mid_cap"} or
                             {"$and": [{"category": "mid_cap"}, {"chunk_type": "pricing"}]}

        Returns:
            dict with keys: documents, metadatas, distances
            Each is a list-of-lists (outer = per query, inner = per result).
        """
        if not self._records or self._embeddings is None or self._embeddings.size == 0:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        # Apply metadata filter
        candidate_indices = self._apply_filter(where)
        if not candidate_indices:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

        cand_embeds = self._embeddings[candidate_indices]

        # Cosine similarity
        q = np.array(query_embedding, dtype=np.float32).flatten()  # ensure 1D
        q_norm = q / (np.linalg.norm(q) + 1e-10)
        norms  = np.linalg.norm(cand_embeds, axis=1, keepdims=True) + 1e-10
        c_norm = cand_embeds / norms
        sims   = c_norm @ q_norm           # shape (N,)
        distances = (1 - sims).tolist()    # cosine distance (0=identical)

        # Sort by distance ascending (most similar first)
        k = min(n_results, len(candidate_indices))
        top_local = sorted(range(len(candidate_indices)), key=lambda i: distances[i])[:k]
        top_global = [candidate_indices[i] for i in top_local]

        return {
            "documents": [[self._records[i]["document"] for i in top_global]],
            "metadatas": [[self._records[i]["metadata"] for i in top_global]],
            "distances": [[distances[j] for j in top_local]],
        }

    # ── Filter helpers ───────────────────────────────────────────────────────

    def _apply_filter(self, where: Optional[dict]) -> list[int]:
        """Return indices of records matching the where clause."""
        if where is None:
            return list(range(len(self._records)))

        # Handle $and
        if "$and" in where:
            conditions = where["$and"]
            result = set(range(len(self._records)))
            for condition in conditions:
                result &= set(self._apply_filter(condition))
            return sorted(result)

        # Handle simple equality {"field": "value"} or {"field": {"$eq": "value"}}
        indices = []
        for i, record in enumerate(self._records):
            meta = record["metadata"]
            match = True
            for key, val in where.items():
                if key.startswith("$"):
                    continue
                meta_val = meta.get(key)
                if isinstance(val, dict):
                    if "$eq" in val and meta_val != val["$eq"]:
                        match = False
                        break
                elif meta_val != val:
                    match = False
                    break
            if match:
                indices.append(i)
        return indices
