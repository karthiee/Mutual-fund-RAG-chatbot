# 📊 Mutual Fund RAG Chatbot — Phase-wise Architecture

> **Scope:** Architecture planning document only. Implementation and deployment are out of scope for this document and will be addressed in future phases.  
> **Last Updated:** March 2026  
> **Data Source:** [INDmoney — Mutual Funds](https://www.indmoney.com/mutual-funds)

---

## 🗂️ Table of Contents

1. [Project Overview](#project-overview)
2. [Target Mutual Funds & Reference Data](#target-mutual-funds--reference-data)
3. [High-Level Architecture Diagram](#high-level-architecture-diagram)
4. [Phase 1 — Data Ingestion (Web Scraping)](#phase-1--data-ingestion-web-scraping)
5. [Phase 2 — Data Processing & Structuring](#phase-2--data-processing--structuring)
6. [Phase 3 — Embedding & Vector Store](#phase-3--embedding--vector-store)
7. [Phase 4 — RAG Pipeline & LLM Integration](#phase-4--rag-pipeline--llm-integration)
8. [Phase 5 — Chatbot Interface & Query Handling](#phase-5--chatbot-interface--query-handling)
9. [Phase 6 — Scheduler & Automated Data Refresh](#phase-6--scheduler--automated-data-refresh)
10. [Phase 7 — Deployment (Future)](#phase-7--deployment-future)
11. [Technology Stack Summary](#technology-stack-summary)
12. [Data Flow Diagram](#data-flow-diagram)

---

## Project Overview

This document describes the phased architecture for building a **Retrieval-Augmented Generation (RAG) chatbot** that enables users to query detailed information about **HDFC Mutual Funds** listed on INDmoney. The chatbot will provide accurate, real-time, context-aware answers about fund metrics without hallucination, grounded by structured fund data and semantic search.

### Goals
- Allow users to ask natural language questions about specific HDFC Mutual Funds
- Serve information about: NAV price, Expense Ratio, Exit Load, Minimum SIP, Lock-in Period, Riskometer, and Top 3 Holdings
- Support 5 HDFC fund categories: Small Cap, Mid Cap, Large Cap, ELSS (Tax Saver), and Flexi Cap

### Non-Goals (Current Scope)
- No live/real-time NAV refresh (Phase 1 uses scraped point-in-time data)
- No purchase/investment transaction capabilities
- No user authentication or personalization
- No deployment (covered in Phase 6)

---

## Target Mutual Funds & Reference Data

The following 5 HDFC Mutual Funds are in scope. Data was sourced from INDmoney on **March 2, 2026** as a baseline reference.

> ⚠️ **Note:** NAV, expense ratios, and holdings are subject to change. The scraper in Phase 1 will always fetch current data.

### 1. HDFC Small Cap Fund — Direct Growth

| Field              | Value                                        |
|--------------------|----------------------------------------------|
| **Source URL**     | [indmoney.com — HDFC Small Cap](https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580) |
| **Category**       | Small Cap Fund                               |
| **NAV**            | ₹150.04 (as of Mar 02, 2026)                |
| **Expense Ratio**  | 0.67%                                        |
| **Exit Load**      | 1.00% (if redeemed within 1 year)            |
| **Minimum SIP**    | ₹100                                         |
| **Lock-in Period** | None                                         |
| **Riskometer**     | Very High Risk                               |
| **Top Holdings**   | 1. Firstsource Solutions Ltd (4.79%) · 2. Bank of Baroda (3.8%) · 3. eClerx Services Ltd (3.78%) |

---

### 2. HDFC Flexi Cap Fund — Direct Plan Growth

| Field              | Value                                        |
|--------------------|----------------------------------------------|
| **Source URL**     | [indmoney.com — HDFC Flexi Cap](https://www.indmoney.com/mutual-funds/hdfc-flexi-cap-fund-direct-plan-growth-option-3184) |
| **Category**       | Flexi Cap Fund                               |
| **NAV**            | ₹2,234.64 (as of Mar 02, 2026)             |
| **Expense Ratio**  | 0.67%                                        |
| **Exit Load**      | 1.00% (if redeemed within 1 year)            |
| **Minimum SIP**    | ₹100                                         |
| **Lock-in Period** | None                                         |
| **Riskometer**     | Very High Risk                               |
| **Top Holdings**   | 1. ICICI Bank Ltd (8.9%) · 2. HDFC Bank Ltd (7.82%) · 3. Axis Bank Ltd (7.59%) |

---

### 3. HDFC ELSS Taxsaver — Direct Plan Growth

| Field              | Value                                        |
|--------------------|----------------------------------------------|
| **Source URL**     | [indmoney.com — HDFC ELSS Taxsaver](https://www.indmoney.com/mutual-funds/hdfc-elss-taxsaver-direct-plan-growth-option-2685) |
| **Category**       | ELSS (Tax Savings)                           |
| **NAV**            | ₹1,525.60 (as of Mar 02, 2026)             |
| **Expense Ratio**  | 1.08%                                        |
| **Exit Load**      | 0% (No Exit Load)                            |
| **Minimum SIP**    | ₹500                                         |
| **Lock-in Period** | **3 Years** (statutory ELSS lock-in)         |
| **Riskometer**     | Very High Risk                               |
| **Top Holdings**   | 1. HDFC Bank Ltd (9.21%) · 2. Axis Bank Ltd (8.63%) · 3. Maruti Suzuki India Ltd (4.79%) |

---

### 4. HDFC Mid Cap Opportunities Fund — Direct Plan Growth

| Field              | Value                                        |
|--------------------|----------------------------------------------|
| **Source URL**     | [indmoney.com — HDFC Mid Cap](https://www.indmoney.com/mutual-funds/hdfc-mid-cap-fund-direct-plan-growth-option-3097) |
| **Category**       | Mid Cap Fund                                 |
| **NAV**            | ₹220.18 (as of Mar 02, 2026)               |
| **Expense Ratio**  | 0.74%                                        |
| **Exit Load**      | 1.00% (if redeemed within 1 year)            |
| **Minimum SIP**    | ₹100                                         |
| **Lock-in Period** | None                                         |
| **Riskometer**     | Very High Risk                               |
| **Top Holdings**   | 1. Max Financial Services Ltd (4.51%) · 2. AU Small Finance Bank Ltd (4.19%) · 3. The Federal Bank Ltd (3.99%) |

---

### 5. HDFC Top 100 Fund (Large Cap) — Direct Plan Growth

| Field              | Value                                        |
|--------------------|----------------------------------------------|
| **Source URL**     | [indmoney.com — HDFC Large Cap](https://www.indmoney.com/mutual-funds/hdfc-large-cap-fund-direct-plan-growth-option-2989) |
| **Category**       | Large Cap Fund                               |
| **NAV**            | ₹1,242.13 (as of Mar 02, 2026)             |
| **Expense Ratio**  | 0.98%                                        |
| **Exit Load**      | 1.00% (if redeemed within 1 year)            |
| **Minimum SIP**    | ₹100                                         |
| **Lock-in Period** | None                                         |
| **Riskometer**     | Very High Risk                               |
| **Top Holdings**   | 1. ICICI Bank Ltd (9.31%) · 2. HDFC Bank Ltd (8.97%) · 3. Bharti Airtel Ltd (5.92%) |

---

## High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        MUTUAL FUND RAG CHATBOT                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐                                                           │
│   │  Phase 6     │  ← Scheduler (APScheduler / Cron)                        │
│   │  Scheduler   │    Triggers Phase 1 → 2 → 3 on a schedule                │
│   └──────┬───────┘                                                           │
│          │  triggers                                                         │
│          ▼                                                                   │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│   │  Phase 1     │    │  Phase 2     │    │  Phase 3     │                  │
│   │  Data        │───▶│  Data        │───▶│  Embedding   │                  │
│   │  Ingestion   │    │  Processing  │    │  & Vector    │                  │
│   │  (Scraper)   │    │  (Chunking)  │    │  Store       │                  │
│   └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                    │                         │
│                                                    ▼                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│   │  Phase 5     │    │  Phase 4     │    │  Vector DB   │                  │
│   │  Chatbot     │◀───│  RAG Pipeline│◀───│  (ChromaDB)  │                  │
│   │  Interface   │    │  + Groq LLM  │    │              │                  │
│   └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 — Data Ingestion (Web Scraping)

### Objective
Scrape structured mutual fund data from the 5 INDmoney fund pages and store it in a raw structured format for downstream processing.

### Input
- 5 INDmoney.com mutual fund URLs (JavaScript-rendered pages requiring browser-level scraping)

### Challenges
- INDmoney pages are **JavaScript-rendered (SPA)** — standard HTTP-based scraping returns 403. A headless browser tool (Playwright or Selenium) is required.
- Data is spread across multiple tabs on each page: **Holdings**, **Overview**, **Fund Price**, and **About** sections.
- Fields like lock-in periods appear only for ELSS funds.
- Top holdings require navigating to the "Holdings" tab explicitly.

### Data Fields to Extract (per Fund)

| Field              | Tab / Section on Page | Data Type  |
|--------------------|-----------------------|------------|
| Fund Name          | Page Header           | String     |
| Fund Category      | Page Header / About   | String     |
| NAV (Price)        | Fund Price            | Float (₹)  |
| NAV Date           | Fund Price            | Date       |
| Expense Ratio      | Overview              | Float (%)  |
| Exit Load          | Overview              | String     |
| Minimum SIP        | Overview              | Float (₹)  |
| Lock-in Period     | Overview              | String     |
| Riskometer         | Overview / About      | String     |
| Top 3 Holdings     | Holdings Tab          | List[Dict] |
| Source URL         | —                     | String     |
| Scrape Timestamp   | —                     | DateTime   |

### Scraping Strategy

```
┌─────────────────────────────────────────────────────────┐
│  For each fund URL:                                      │
│  1. Launch headless browser (Playwright)                 │
│  2. Navigate to fund URL, wait for JS to render          │
│  3. Extract header data (Fund Name, Category, NAV)       │
│  4. Click "Overview" tab → extract Expense Ratio,        │
│     Exit Load, Min SIP, Lock-in, Riskometer              │
│  5. Click "Holdings" tab → extract Top 3 holdings        │
│     (name + percentage)                                  │
│  6. Store result as structured JSON per fund             │
└─────────────────────────────────────────────────────────┘
```

### Output Format (Raw JSON Schema)

```json
{
  "fund_id": "hdfc-small-cap-3580",
  "fund_name": "HDFC Small Cap Fund Direct Growth",
  "category": "Small Cap Fund",
  "source_url": "https://www.indmoney.com/mutual-funds/hdfc-small-cap-fund-direct-growth-option-3580",
  "scraped_at": "2026-03-02T10:00:00Z",
  "nav": {
    "price": 150.04,
    "currency": "INR",
    "date": "2026-03-02"
  },
  "expense_ratio": "0.67%",
  "exit_load": "1.00% (if redeemed within 1 year)",
  "minimum_sip": "₹100",
  "lock_in_period": "None",
  "riskometer": "Very High Risk",
  "top_holdings": [
    { "rank": 1, "name": "Firstsource Solutions Ltd", "percentage": 4.79 },
    { "rank": 2, "name": "Bank of Baroda", "percentage": 3.80 },
    { "rank": 3, "name": "eClerx Services Ltd", "percentage": 3.78 }
  ]
}
```

### Tools & Libraries (Phase 1)

| Purpose              | Tool / Library         |
|----------------------|------------------------|
| Headless Browser     | `Playwright` (Python)  |
| HTML Parsing         | `BeautifulSoup4`       |
| Data Validation      | `Pydantic`             |
| Raw Storage          | JSON files / SQLite    |
| Scheduling (future)  | `APScheduler` / Cron   |

### Scraping Schedule (Future Consideration)
- NAV changes daily → scraper should run **once daily** (post market close ~3:30 PM IST)
- Holdings change monthly → monthly refresh
- Expense ratio changes quarterly

---

## Phase 2 — Data Processing & Structuring

### Objective
Transform the raw scraped JSON data into **clean, structured text documents** optimized for embedding and semantic retrieval.

### Input
- Raw JSON files from Phase 1 (one per fund)

### Processing Steps

#### 2.1 — Data Validation & Cleaning
- Validate all required fields exist (using Pydantic models)
- Normalize numeric fields (remove `₹`, `%` symbols into typed values)
- Handle missing or null fields gracefully (e.g., no lock-in → `"None"`)
- Deduplicate data if re-scraped on the same day

#### 2.2 — Document Chunking Strategy

Each mutual fund will be split into **multiple semantic chunks** for optimal RAG retrieval. This allows the chatbot to retrieve only the relevant section for a given query.

```
Fund → Multiple Document Chunks:
  ├── Chunk A: Fund Overview (name, category, riskometer)
  ├── Chunk B: Pricing Info (NAV, date)
  ├── Chunk C: Cost & Fees (expense ratio, exit load)
  ├── Chunk D: Investment Details (min SIP, lock-in period)
  └── Chunk E: Top Holdings (top 3 stocks + percentages)
```

#### 2.3 — Text Document Template

Each chunk is formatted as a natural language paragraph for embedding quality:

**Example — Cost & Fees Chunk:**
```
Fund: HDFC Small Cap Fund Direct Growth
Category: Small Cap Fund
Expense Ratio: 0.67%
Exit Load: 1.00% if redeemed within 1 year.
This is the cost associated with investing and exiting the fund.
```

**Example — Holdings Chunk:**
```
Fund: HDFC Small Cap Fund Direct Growth
Category: Small Cap Fund
Top 3 Holdings as of March 2026:
1. Firstsource Solutions Ltd — 4.79%
2. Bank of Baroda — 3.80%
3. eClerx Services Ltd — 3.78%
```

#### 2.4 — Metadata Tagging

Each chunk is tagged with metadata for filtered retrieval:

```json
{
  "fund_id": "hdfc-small-cap-3580",
  "fund_name": "HDFC Small Cap Fund Direct Growth",
  "category": "small_cap",
  "chunk_type": "cost_fees",
  "scraped_at": "2026-03-02T10:00:00Z"
}
```

### Output
- Processed document chunks (list of `{text, metadata}` pairs) stored as JSONL or in database
- One JSONL file per fund, or a combined corpus file

### Tools & Libraries (Phase 2)

| Purpose              | Tool / Library              |
|----------------------|-----------------------------|
| Data Validation      | `Pydantic`                  |
| Text Processing      | `Python` (string templates) |
| Chunk Storage        | JSONL files                 |

---

## Phase 3 — Embedding & Vector Store

### Objective
Convert processed text chunks into **vector embeddings** and store them in a **vector database** for semantic similarity search during query time.

### Input
- Processed JSONL document chunks from Phase 2

### Embedding Model Selection

| Option                         | Type           | Notes                                  |
|--------------------------------|----------------|----------------------------------------|
| `text-embedding-3-small`       | OpenAI API     | High quality; API cost per call        |
| `sentence-transformers/all-MiniLM-L6-v2` | Open Source | Fast; runs locally; good for financial text |
| `text-embedding-ada-002`       | OpenAI API     | Legacy; still widely used              |

**Recommended:** `all-MiniLM-L6-v2` for local/cost-free setup, or `text-embedding-3-small` for production quality.

### Vector Store Options

| Vector DB    | Type           | Use Case                              |
|--------------|----------------|---------------------------------------|
| **ChromaDB** | Local / Cloud  | Easy setup, good for small-medium datasets |
| **FAISS**    | Local          | High performance; no persistence by default |
| **Pinecone** | Cloud (SaaS)   | Managed; good for production          |
| **Weaviate** | Self-hosted    | Rich filtering + semantic search      |

**Recommended for Phase 1:** **ChromaDB** (local) — lightweight, easy Python integration, supports metadata filtering.

### Embedding Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  For each document chunk:                                │
│  1. Pass chunk text through embedding model             │
│  2. Receive dense vector (e.g., 384-dim or 1536-dim)    │
│  3. Store in vector DB with:                            │
│     - vector (embedding)                                │
│     - document text                                     │
│     - metadata (fund_id, category, chunk_type)          │
└─────────────────────────────────────────────────────────┘
```

### Collection Design (ChromaDB)

```
Collection: "mutual_funds"
  Documents: ~25 chunks (5 funds × 5 chunk types)
  Metadata filters:
    - fund_id
    - category (small_cap, mid_cap, large_cap, elss, flexi_cap)
    - chunk_type (overview, pricing, cost_fees, investment, holdings)
```

### Tools & Libraries (Phase 3)

| Purpose            | Tool / Library                                |
|--------------------|-----------------------------------------------|
| Embedding Model    | `sentence-transformers` or `openai`           |
| Vector Store       | `chromadb`                                    |
| Batch Processing   | `Python` (loop with batching)                 |
| Persistence        | ChromaDB local persistent directory           |

---

## Phase 4 — RAG Pipeline & LLM Integration

### Objective
Build the **Retrieval-Augmented Generation (RAG)** pipeline that takes a user query, retrieves relevant document chunks from the vector store, and passes them as context to an LLM to generate a grounded, accurate response.

### RAG Pipeline Flow

```
User Query
    │
    ▼
┌─────────────────────────────┐
│  1. Query Preprocessing     │  ← Normalize, extract fund intent
│     (intent detection)      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  2. Query Embedding         │  ← Same embedding model as Phase 3
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  3. Semantic Search         │  ← Top-K similarity search in vector DB
│     (ChromaDB retrieval)    │     with optional metadata filters
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  4. Context Assembly        │  ← Concatenate retrieved chunks
│     (Prompt Construction)   │     into structured context
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  5. LLM Generation          │  ← Send prompt + context to LLM
│     (Groq — llama3-70b)     │     ultra-fast inference via Groq API
└──────────────┬──────────────┘
               │
               ▼
         Final Answer
```

### Intent Detection & Metadata Filtering

To improve retrieval precision, user queries are pre-screened for:

| User Query Signal              | Detected Intent          | Metadata Filter Applied         |
|-------------------------------|--------------------------|----------------------------------|
| "small cap", "HDFC Small Cap" | Fund Category            | `category = small_cap`           |
| "expense ratio", "charges"    | Cost Info                | `chunk_type = cost_fees`         |
| "NAV", "price", "value"       | Pricing Info             | `chunk_type = pricing`           |
| "SIP", "minimum investment"   | Investment Details       | `chunk_type = investment`        |
| "lock-in", "ELSS"             | ELSS / Lock-in           | `category = elss`                |
| "holdings", "top stocks"      | Portfolio Holdings       | `chunk_type = holdings`          |
| "risk", "riskometer"          | Risk Profile             | `chunk_type = overview`          |

### Prompt Template

```
You are a helpful financial assistant specializing in HDFC Mutual Funds.
Use ONLY the information provided in the context below to answer the user's question.
If the information is not in the context, say "I don't have that information."
Do not make up any financial data.

Context:
---
{retrieved_chunks}
---

User Question: {user_query}

Answer:
```

### LLM — Groq

This project uses **[Groq](https://groq.com/)** as the LLM provider. Groq offers extremely low-latency inference (typically < 1s) via its Language Processing Unit (LPU) hardware, making it ideal for a responsive chatbot experience.

| Model                      | Type       | Notes                                              |
|----------------------------|------------|----------------------------------------------------|
| `llama3-70b-8192`          | Groq API   | **Primary choice** — high quality, 8K context      |
| `llama3-8b-8192`           | Groq API   | Faster / cheaper; good for dev/testing             |
| `mixtral-8x7b-32768`       | Groq API   | 32K context window; useful for long conversations  |
| `gemma-7b-it`              | Groq API   | Lightweight alternative on Groq                    |

**Selected Model:** `llama3-70b-8192` via Groq API  
**Why Groq:** Free tier available, sub-second response times, no GPU required locally, and integrates natively with LangChain via `langchain-groq`.

### Retrieval Configuration

| Parameter          | Recommended Value | Description                       |
|--------------------|------------------|-----------------------------------|
| `top_k`            | 3–5              | Number of chunks to retrieve      |
| `similarity_metric`| Cosine           | Standard for semantic search      |
| `score_threshold`  | 0.6              | Minimum similarity score          |

### Framework Options

| Framework         | Notes                                               |
|-------------------|-----------------------------------------------------|
| **LangChain**     | Mature; large ecosystem; RAG chains built-in        |
| **LlamaIndex**    | Optimized for document indexing and RAG             |
| **Custom Python** | Full control; simpler for small datasets like this  |

**Recommended:** **LangChain** with ChromaDB retriever for simplicity and readability.

### Tools & Libraries (Phase 4)

| Purpose             | Tool / Library                     |
|---------------------|------------------------------------|
| RAG Orchestration   | `LangChain`                        |
| LLM Provider        | `groq` + `langchain-groq`          |
| LLM Model           | `llama3-70b-8192` (via Groq API)   |
| Retriever           | ChromaDB via LangChain             |
| Prompt Templates    | LangChain `PromptTemplate`         |

---

## Phase 5 — Chatbot Interface & Query Handling

### Objective
Build a user-facing chat interface where users can ask natural language questions about the 5 HDFC Mutual Funds and receive grounded, accurate answers.

### Interface Options

| Option            | Framework         | Notes                                       |
|-------------------|-------------------|---------------------------------------------|
| **Web Chat UI**   | Streamlit         | Fast to build; Python-native; easy to deploy |
| **Web App**       | FastAPI + React   | Production-grade; separate front/back end   |
| **CLI**           | Python CLI        | For development/testing only                |
| **Telegram Bot**  | `python-telegram-bot` | Mobile-friendly; no hosting needed     |

**Recommended for Phase 5:** **Streamlit** — aligns with the project's existing Streamlit pattern (see prior migration work).

### Supported User Queries (Sample)

| Query Type             | Example User Question                                      |
|------------------------|------------------------------------------------------------|
| NAV Query              | "What is the current NAV of HDFC Small Cap Fund?"          |
| Expense Ratio          | "What is the expense ratio of HDFC Flexi Cap Fund?"        |
| Exit Load              | "Is there an exit load on HDFC Mid Cap Fund?"              |
| Minimum SIP            | "What is the minimum SIP for HDFC ELSS Taxsaver?"          |
| Lock-in Period         | "Does HDFC ELSS have a lock-in period? How long?"          |
| Riskometer             | "What is the risk level of HDFC Large Cap Fund?"           |
| Top Holdings           | "What are the top 3 holdings of HDFC Flexi Cap Fund?"      |
| Comparative Query      | "Which HDFC fund has the lowest expense ratio?"            |
| Category Query         | "Tell me about the HDFC Mid Cap Fund"                      |

### Chatbot UI Components (Streamlit)

```
┌───────────────────────────────────────────────────────┐
│  HDFC Mutual Fund Chatbot                             │
│  ─────────────────────────────────────────────────    │
│  [Sidebar]                                            │
│    • Select Fund (dropdown): All / Specific Fund      │
│    • Fund comparison toggle                           │
│    • Last updated: March 2, 2026                      │
│                                                       │
│  [Chat Area]                                          │
│    👤 User: What is the expense ratio of HDFC         │
│            Small Cap Fund?                            │
│                                                       │
│    🤖 Bot: The expense ratio of HDFC Small Cap        │
│           Fund (Direct Growth) is 0.67%.              │
│                                                       │
│  [Input Box]                                          │
│    Ask about any HDFC mutual fund... [Send]           │
└───────────────────────────────────────────────────────┘
```

### Query Handling Logic

```
User submits query
    │
    ├─ If query is empty → show prompt to enter question
    │
    ├─ Detect fund mention (small cap / flexi cap / ELSS / mid cap / large cap)
    │       └─ Apply fund-level metadata filter in retrieval
    │
    ├─ Detect field mention (NAV / expense / exit load / SIP / lock-in / risk / holdings)
    │       └─ Apply chunk_type metadata filter in retrieval
    │
    ├─ Run RAG pipeline (Phase 4)
    │       └─ Retrieve top-3 chunks → assemble prompt → query LLM
    │
    └─ Return answer + source context (optional "Show sources" toggle)
```

### Session State Management (Streamlit)
- Maintain `st.session_state.messages` for full conversation history
- Allow users to clear chat history
- Display fund reference card on sidebar for quick context

### Tools & Libraries (Phase 5)

| Purpose             | Tool / Library         |
|---------------------|------------------------|
| Web UI              | `Streamlit`            |
| State Management    | `st.session_state`     |
| API Backend         | Streamlit inline or FastAPI |

---

## Phase 6 — Scheduler & Automated Data Refresh

### Objective
Run an automated scheduler that periodically triggers **Phase 1 → Phase 2 → Phase 3** in sequence to ensure the chatbot always has the most up-to-date mutual fund data (NAV, holdings, expense ratios) without manual intervention.

### Why a Scheduler?
- NAV prices update **daily** (post market close ~3:30 PM IST)
- Top holdings update **monthly** (post month-end portfolio disclosure)
- Expense ratios change **quarterly**
- Without a scheduler, the chatbot serves stale data

### Scheduler Pipeline

```
┌──────────────────────────────────────────────────────────┐
│                   SCHEDULER (Phase 6)                    │
│                                                          │
│  Trigger: Time-based (APScheduler / Cron)                │
│                                                          │
│  Daily Job (3:45 PM IST — post market close):            │
│    Step 1 → Run Phase 1 (Scraper)                        │
│             └─ Fetch fresh NAV + data from INDmoney      │
│    Step 2 → Run Phase 2 (Processor)                      │
│             └─ Re-chunk and re-tag updated documents     │
│    Step 3 → Run Phase 3 (Embedder)                       │
│             └─ Re-embed changed chunks into ChromaDB     │
│    Step 4 → Log refresh result (success / failure)       │
│    Step 5 → Notify (optional) via email / Slack          │
│                                                          │
│  Monthly Job (1st of each month):                        │
│    → Full re-scrape (holdings + expense ratio refresh)   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Smart Refresh Strategy

To avoid unnecessary re-embedding (which wastes compute and time), the scheduler uses a **change-detection** step:

| Step | Action | Tool |
|------|--------|------|
| 1 | Scrape latest data | Playwright |
| 2 | Compare new JSON vs. stored JSON (diff) | Python `deepdiff` |
| 3 | If changed → re-process & re-embed | Phase 2 + Phase 3 |
| 4 | If unchanged → skip (no re-embedding needed) | — |
| 5 | Log outcome with timestamp | Python `logging` |

### Schedule Configuration

```python
# Example APScheduler configuration
scheduler.add_job(
    run_full_pipeline,           # triggers Phase 1 → 2 → 3
    trigger='cron',
    hour=15,
    minute=45,
    timezone='Asia/Kolkata',     # IST (post NSE market close)
    id='daily_nav_refresh'
)

scheduler.add_job(
    run_full_pipeline,
    trigger='cron',
    day=1,                       # 1st of every month
    hour=6,
    minute=0,
    timezone='Asia/Kolkata',
    id='monthly_holdings_refresh'
)
```

### Error Handling & Alerting

| Failure Scenario            | Handling Strategy                              |
|-----------------------------|------------------------------------------------|
| Scraper fails (site down)   | Retry 3x with exponential backoff; log error   |
| Embedding model error       | Skip re-embed; keep existing vectors           |
| ChromaDB write error        | Rollback to previous snapshot                  |
| Groq API timeout            | Not in refresh pipeline (only at query time)   |
| All retries exhausted       | Send alert (email / Slack / log file)          |

### Tools & Libraries (Phase 6)

| Purpose             | Tool / Library             |
|---------------------|----------------------------|
| Scheduling          | `APScheduler` (Python)     |
| Change Detection    | `deepdiff`                 |
| Logging             | Python `logging` module    |
| Alerting (optional) | `smtplib` / Slack webhook  |
| Orchestration       | Python script / subprocess |

---

## Phase 7 — Deployment (Future)

> ⚠️ **This phase is explicitly out of scope for the current document. Architecture to be defined in a separate deployment plan.**

### Anticipated Deployment Targets

| Option              | Platform              | Notes                                  |
|---------------------|-----------------------|----------------------------------------|
| Streamlit Cloud     | Streamlit Community Cloud | Free; easy for Streamlit apps       |
| Docker Container    | Any cloud provider    | Portable; reproducible                 |
| Google Cloud Run    | GCP                   | Serverless containers; auto-scaling    |
| AWS Lambda + API GW | AWS                   | For API-only backend                   |

### Anticipated Concerns
- Securing API keys (Groq API key, etc.)
- Rate limiting scraper to avoid IP bans from INDmoney
- Scheduler persistence across container restarts
- Cold start times for embedding models

---

## Technology Stack Summary

| Component            | Recommended Tool                    | Alternative                     |
|----------------------|-------------------------------------|---------------------------------|
| **Web Scraping**     | Playwright (Python)                 | Selenium                        |
| **HTML Parsing**     | BeautifulSoup4                      | lxml                            |
| **Data Validation**  | Pydantic                            | marshmallow                     |
| **Embedding Model**  | `all-MiniLM-L6-v2`                  | OpenAI `text-embedding-3-small` |
| **Vector Store**     | ChromaDB (local)                    | FAISS, Pinecone                 |
| **RAG Framework**    | LangChain + `langchain-groq`        | LlamaIndex                      |
| **LLM**              | Groq (`llama3-70b-8192`)            | Groq (`mixtral-8x7b-32768`)     |
| **Scheduler**        | APScheduler                         | Cron (Linux) / Task Scheduler   |
| **Change Detection** | `deepdiff`                          | Custom JSON diff                |
| **Chat Interface**   | Streamlit                           | FastAPI + React                 |
| **Storage**          | JSON/JSONL → SQLite                 | PostgreSQL                      |
| **Language**         | Python 3.11+                        | —                               |

---

## Data Flow Diagram

```
  ┌──────────────────────────────────────────────────┐
  │  Phase 6 — Scheduler                             │
  │  (APScheduler: daily @ 3:45 PM IST)              │
  │  Triggers Phase 1 → 2 → 3 automatically          │
  └───────────────────────┬──────────────────────────┘
                          │  scheduled trigger
                          ▼
INDmoney URLs (5 Funds)
        │
        ▼
  ┌─────────────┐
  │  Phase 1    │  Playwright scraper → raw JSON per fund
  │  Scraper    │
  └──────┬──────┘
         │  raw JSON files
         ▼
  ┌─────────────┐
  │  Phase 2    │  Change detection (deepdiff)
  │  Processor  │  Clean + chunk → JSONL with metadata
  └──────┬──────┘
         │  JSONL chunks (only changed)
         ▼
  ┌─────────────┐
  │  Phase 3    │  Re-embed changed chunks → ChromaDB
  │  Embedder   │  (vector + text + metadata)
  └──────┬──────┘
         │  Vector DB up-to-date
         ▼
  ┌─────────────┐          ┌──────────────┐
  │  Phase 4    │◀─────────│  User Query  │
  │  RAG Engine │          │  (Streamlit) │
  │  + Groq LLM │          └──────────────┘
  │             │
  │  1. Embed query
  │  2. Retrieve top-K chunks (ChromaDB)
  │  3. Build prompt
  │  4. Groq llama3-70b generates answer  ┌──────────┐
  └────────────────────────────────────▶ │ Phase 5  │
                                          │ Chatbot  │
                                          │ UI       │
                                          └──────────┘
```

---

## Directory Structure (Proposed)

```
mutual-fund-chatbot/
├── architecture.md              ← This file
│
├── phase1_scraper/
│   ├── scraper.py               ← Playwright-based scraper
│   ├── models.py                ← Pydantic data models
│   └── raw_data/
│       ├── hdfc_small_cap.json
│       ├── hdfc_flexi_cap.json
│       ├── hdfc_elss_taxsaver.json
│       ├── hdfc_mid_cap.json
│       └── hdfc_large_cap.json
│
├── phase2_processor/
│   ├── processor.py             ← Cleaning, chunking, tagging
│   └── processed_data/
│       └── chunks.jsonl
│
├── phase3_embedder/
│   ├── embedder.py              ← Generate and store embeddings
│   └── vector_store/            ← ChromaDB persistent directory
│
├── phase4_rag/
│   ├── rag_pipeline.py          ← LangChain RAG chain (Groq)
│   ├── retriever.py             ← ChromaDB retriever
│   └── prompts.py               ← Prompt templates
│
├── phase5_chatbot/
│   ├── app.py                   ← Streamlit chatbot app
│   └── utils.py                 ← Helper functions
│
├── phase6_scheduler/
│   ├── scheduler.py             ← APScheduler jobs (daily + monthly)
│   ├── pipeline_runner.py       ← Orchestrates Phase 1 → 2 → 3
│   ├── change_detector.py       ← deepdiff-based change detection
│   └── scheduler.log            ← Refresh history & error log
│
├── requirements.txt
└── .env                         ← API keys (GROQ_API_KEY, etc. — not committed to Git)
```

---

*End of Architecture Document — v1.1*  
*Changes in v1.1: Added Phase 6 (Scheduler & Automated Data Refresh); updated LLM to Groq (`llama3-70b-8192`); Deployment moved to Phase 7.*  
*Next step: Implement Phase 1 (Data Ingestion) when ready to begin development.*
