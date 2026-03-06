# phase3_embedder — ChromaDB persistent vector store directory
#
# This folder is auto-created by embedder.py when it first runs.
# It contains the ChromaDB SQLite database and segment files.
#
# Contents after first run:
#   chroma.sqlite3          ← ChromaDB metadata and index
#   <uuid>/                 ← Embedding segments (binary)
#
# Collection name : mutual_funds
# Documents       : ~25 (5 funds × 5 chunk types)
# Embedding model : all-MiniLM-L6-v2 (384-dimensional vectors)
# Distance metric : cosine
#
# DO NOT manually edit these files.
# To reset and re-index: run  python embedder.py --reset
