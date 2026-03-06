# Phase 5 — Streamlit Chatbot UI

Premium dark-purple chat interface for the HDFC Mutual Fund RAG Chatbot.

## Launch (from project root)

```bash
py -3 -m streamlit run phase5_ui/app.py
```

Then open **http://localhost:8501** in your browser.

## Features

| Feature | Details |
|---|---|
| 🔮 Glowing orb hero | Pulsing animated purple orb (matches reference design) |
| 💬 Chat bubbles | User (purple gradient) + Bot (glassmorphism) |
| ✨ Suggestion chips | 8 one-click quick questions |
| 📋 Sidebar fund cards | Click any fund card to auto-ask about it |
| 🔗 Source URLs | Every answer links back to INDmoney.com |
| 📅 Timestamps | Data freshness shown per answer |
| 🛡️ Guardrails | PII + buy/sell blocked before hitting LLM |
| 🗑️ Clear chat | Resets conversation history |

## Prerequisites

Phases 1–4 must have run:
```
phase3_embedder/vector_store/    ← must exist (run embedder.py)
.env                             ← must contain GROQ_API_KEY=...
```
