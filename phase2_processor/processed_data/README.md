# phase2_processor — Processed output directory
#
# This folder contains the JSONL corpus produced by processor.py.
# Each line in chunks.jsonl is one JSON object representing a
# single document chunk ready for embedding in Phase 3.
#
# Files:
#   chunks.jsonl    — one DocumentChunk JSON object per line
#                     (25 lines total: 5 funds × 5 chunk types)
#
# Format of each line:
#   {
#     "chunk_id": "hdfc-small-cap-3580__overview",
#     "text": "Fund: HDFC Small Cap Fund Direct Growth\n...",
#     "metadata": {
#       "fund_id": "hdfc-small-cap-3580",
#       "fund_name": "HDFC Small Cap Fund Direct Growth",
#       "category": "small_cap",
#       "chunk_type": "overview",
#       "source_url": "https://...",
#       "scraped_at": "2026-03-02T10:00:00",
#       "processed_at": "2026-03-02T11:00:00"
#     }
#   }
#
# DO NOT manually edit chunks.jsonl — re-run processor.py to regenerate.
