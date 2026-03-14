"""
Phase 5 — HDFC Mutual Fund RAG Chatbot (Streamlit UI)

All UI fixes applied:
  ✅ st.chat_input() → sticky pinned bottom input
  ✅ Compact chat bubbles with correct spacing & constrained width
  ✅ Sidebar: fixed (no scroll), only brand + 3 quick prompts
  ✅ Home page: centered MF capabilities panel (no suggestion chips)
  ✅ White / light theme with pink-rose gradient palette

Run from project root:
    py -3 -m streamlit run phase5_ui/app.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "phase4_rag_pipeline"))
sys.path.insert(0, str(ROOT / "phase3_embedder"))

# ── Secret injection (Streamlit Cloud → st.secrets; local → .env) ──────────────
# Must happen BEFORE any downstream import that reads env vars
try:
    _groq_key = st.secrets.get("GROQ_API_KEY", "")
    if _groq_key:
        os.environ.setdefault("GROQ_API_KEY", _groq_key)
except Exception:
    pass  # running locally without secrets — dotenv handles it

# ── Page config ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HDFC MF Chatbot",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Globals ──────────────────────────────────────────────────── */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer { visibility: hidden; }

/* ── App background — clean white with subtle warm gradient ───── */
.stApp {
    background: linear-gradient(145deg, #ffffff 0%, #fff5f7 40%, #fce8ef 100%) !important;
}

/* ── Main container — give bottom room so content clears input bar ─── */
.block-container, [data-testid="stMainBlockContainer"] {
    padding-top: 0.5rem !important;
    padding-bottom: 6rem !important;   /* clears the fixed stBottom input bar */
    max-width: 900px !important;
}

/* ── Keep header transparent but visible (it holds the sidebar toggle) ── */
[data-testid="stHeader"] {
    background: transparent !important;
    background-color: transparent !important;
    border-bottom: none !important;
    box-shadow: none !important;
}
/* Hide only the Deploy button */
[data-testid="stDeployButton"],
.stDeployButton {
    display: none !important;
}
/* Sidebar toggle arrow — always pink and clickable */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarNavCollapseButton"] button,
[data-testid="stBaseButton-headerNoPadding"],
button[data-testid="baseButton-headerNoPadding"] {
    color: #c0185c !important;
    background: rgba(255,255,255,0.85) !important;
    border-radius: 0.5rem !important;
    pointer-events: auto !important;
    visibility: visible !important;
    opacity: 1 !important;
    z-index: 9999 !important;
}
/* Collapsed state tab — always shown on left edge */
[data-testid="stSidebarCollapsedControl"] {
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 9999 !important;
    display: flex !important;
}


/* ── Sidebar: white/light with rose accent ───────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #ffffff 0%, #fff0f5 100%) !important;
    border-right: 1px solid rgba(236, 72, 120, 0.15) !important;
    min-width: 240px !important;
    max-width: 240px !important;
    box-shadow: 2px 0 12px rgba(236,72,120,0.06);
    /* NO overflow:hidden here — it was clipping sidebar and breaking toggle */
}
[data-testid="stSidebar"] > div {
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
}
[data-testid="stSidebar"] * { color: #4a1030 !important; }

/* ── Sidebar heading ──────────────────────────────────────────── */
.sb-title {
    font-size: 1rem; font-weight: 700;
    background: linear-gradient(135deg, #e91e8c, #f43f6e, #ff6b9d);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    padding: 1rem 0.8rem 0.1rem 0.8rem;
}
.sb-sub   { font-size: 0.68rem; color: rgba(120,40,70,0.5) !important; padding: 0 0.8rem 0.6rem; }
.sb-hr    { border: none; border-top: 1px solid rgba(236,72,120,0.15); margin: 0.4rem 0; }
.sb-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1px;
            color: rgba(180,60,90,0.55) !important; padding: 0.4rem 0.8rem 0.5rem; }
.sb-disclaimer {
    font-size: 0.65rem; color: rgba(120,40,70,0.45) !important;
    padding: 0.6rem 0.8rem; line-height: 1.45; margin-top: auto;
}

/* ── Sidebar quick buttons ────────────────────────────────────── */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(236, 72, 120, 0.07) !important;
    border: 1px solid rgba(236, 72, 120, 0.25) !important;
    border-radius: 0.6rem !important;
    color: #c0185c !important;
    font-size: 0.75rem !important;
    text-align: left !important;
    padding: 0.5rem 0.75rem !important;
    width: 100% !important;
    transition: all 0.15s ease !important;
    white-space: normal !important;
    height: auto !important;
    min-height: unset !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(236, 72, 120, 0.15) !important;
    border-color: rgba(236, 72, 120, 0.5) !important;
    color: #a3134f !important;
    transform: none !important;
}

/* ── Home page ─────────────────────────────────────────────────── */
.home-center {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 0.55rem;
    max-height: calc(100vh - 120px);
    padding: 0.5rem 1rem;
    overflow: hidden;
}
/* ── 3D Ball Animation ──────────────────────────────────────────── */
.orb-wrap {
    position: relative;
    width: 100px; height: 100px;
    margin: 0 auto;
    perspective: 600px;
}

/* The actual sphere — assembles from nothing */
.orb {
    position: absolute;
    inset: 20px;
    border-radius: 50%;
    background: radial-gradient(circle at 32% 32%,
        #ffb8d9 0%, #f43f6e 35%, #c0185c 65%, #6b0028 100%);
    box-shadow:
        inset -8px -8px 20px rgba(0,0,0,0.35),
        inset  6px  6px 14px rgba(255,180,210,0.45),
        0 0 50px rgba(244,63,110,0.6),
        0 0 100px rgba(236,72,120,0.3);
    animation:
        orbForm  1.6s cubic-bezier(.34,1.56,.64,1) 0.3s both,
        orbPulse 3.5s ease-in-out 2.1s infinite;
    transform-style: preserve-3d;
}
@keyframes orbForm {
    0%   { opacity:0; transform: scale(0.05) rotateX(70deg) rotateY(-50deg); filter:blur(20px); }
    50%  { opacity:1; transform: scale(1.18) rotateX(-8deg) rotateY(6deg);   filter:blur(0);   }
    75%  { transform: scale(0.93) rotateX(3deg)  rotateY(-2deg); }
    90%  { transform: scale(1.06) rotateX(-1deg) rotateY(1deg); }
    100% { transform: scale(1)    rotateX(0)     rotateY(0); }
}
@keyframes orbPulse {
    0%,100% { box-shadow: inset -8px -8px 20px rgba(0,0,0,0.35), inset 6px 6px 14px rgba(255,180,210,0.45), 0 0 50px rgba(244,63,110,0.6),  0 0 100px rgba(236,72,120,0.3); }
    50%      { box-shadow: inset -8px -8px 20px rgba(0,0,0,0.35), inset 6px 6px 14px rgba(255,180,210,0.45), 0 0 80px rgba(244,63,110,0.85), 0 0 140px rgba(236,72,120,0.5); }
}

/* Fragment shards — explode outward from centre then disappear */
.orb-wrap .shard {
    position: absolute;
    top: 50%; left: 50%;
    border-radius: 40% 60% 55% 45% / 48% 52% 48% 52%;
    transform-style: preserve-3d;
    opacity: 0;
    animation: shardExplode 1.4s cubic-bezier(.25,.46,.45,.94) both;
}
/* 8 shards with varied shapes, sizes, 3-D directions */
.shard:nth-child(1){width:28px;height:28px;background:linear-gradient(135deg,#ff9ec6,#f43f6e);margin:-14px 0 0 -14px;animation-delay:0.00s;--rx:  45deg;--ry: -60deg;--tx:-65px;--ty:-55px;--tz: 30px;}
.shard:nth-child(2){width:22px;height:24px;background:linear-gradient(135deg,#c0185c,#e91e8c);margin:-12px 0 0 -11px;animation-delay:0.04s;--rx: -30deg;--ry:  80deg;--tx: 70px;--ty:-40px;--tz: 20px;}
.shard:nth-child(3){width:18px;height:26px;background:linear-gradient(135deg,#f43f6e,#7a0035);margin: -9px 0 0  -9px;animation-delay:0.06s;--rx:  60deg;--ry:  40deg;--tx:-50px;--ty: 65px;--tz:-25px;}
.shard:nth-child(4){width:24px;height:20px;background:linear-gradient(135deg,#ff6b9d,#c0185c);margin:-10px 0 0 -12px;animation-delay:0.02s;--rx: -50deg;--ry: -70deg;--tx: 60px;--ty: 58px;--tz: 15px;}
.shard:nth-child(5){width:20px;height:22px;background:linear-gradient(135deg,#e91e8c,#ff9ec6);margin:-11px 0 0 -10px;animation-delay:0.05s;--rx:  35deg;--ry: 110deg;--tx:  0px;--ty:-72px;--tz:-30px;}
.shard:nth-child(6){width:16px;height:20px;background:linear-gradient(135deg,#f43f6e,#ffc8de);margin: -8px 0 0  -8px;animation-delay:0.03s;--rx: -70deg;--ry: -30deg;--tx: 68px;--ty: -5px;--tz: 40px;}
.shard:nth-child(7){width:22px;height:18px;background:linear-gradient(135deg,#c0185c,#f43f6e);margin: -9px 0 0 -11px;animation-delay:0.07s;--rx:  55deg;--ry:-100deg;--tx:-60px;--ty:  8px;--tz:-20px;}
.shard:nth-child(8){width:18px;height:18px;background:linear-gradient(135deg,#ff6b9d,#7a0035);margin: -9px 0 0  -9px;animation-delay:0.01s;--rx: -40deg;--ry:  55deg;--tx: 12px;--ty: 70px;--tz: 35px;}

@keyframes shardExplode {
    /* Shards START at final position (imploded) and EXPLODE OUT, then fade */
    0%   { opacity:0.95; transform:translate3d(0,0,0) rotateX(0) rotateY(0) scale(1.2); }
    40%  { opacity:0.85; transform:translate3d(var(--tx),var(--ty),var(--tz)) rotateX(var(--rx)) rotateY(var(--ry)) scale(0.8); }
    100% { opacity:0;    transform:translate3d(calc(var(--tx)*1.6),calc(var(--ty)*1.6),calc(var(--tz)*1.5)) rotateX(calc(var(--rx)*2)) rotateY(calc(var(--ry)*2)) scale(0.2); }
}
.home-title {
    font-size: 1.6rem; font-weight: 700; margin: 0;
    background: linear-gradient(135deg, #c0185c 0%, #f43f6e 50%, #ff9ec6 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1.15;
}
/* ── Homepage info row — two-column: tagline left, fund list right ── */
.home-info-row {
    display: flex;
    align-items: stretch;
    gap: 1.5rem;
    max-width: 560px;
    margin: 0 auto;
    text-align: left;
}
.home-desc-col {
    flex: 1;
    font-size: 0.78rem;
    color: rgba(100, 30, 60, 0.65);
    line-height: 1.55;
    border-right: 1px solid rgba(192,24,92,0.15);
    padding-right: 1.2rem;
    display: flex;
    align-items: center;
}
.home-funds-col {
    flex: 1;
    padding-left: 0.1rem;
}
.home-funds-col p {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(192,24,92,0.5);
    margin: 0 0 0.3rem;
    font-weight: 600;
}
.home-funds-col ul {
    list-style: none;
    padding: 0; margin: 0;
}
.home-funds-col ul li {
    font-size: 0.78rem;
    color: rgba(80, 20, 50, 0.72);
    line-height: 1.45;
    padding-left: 0.75rem;
    position: relative;
    margin-bottom: 0.15rem;
}
.home-funds-col ul li::before {
    content: '•';
    color: #e91e8c;
    position: absolute;
    left: 0;
    font-size: 0.65rem;
    top: 0.2em;
}

/* ── MF capability cards grid ─────────────────────────────────── */
.caps-grid {
    display: flex; flex-wrap: wrap; gap: 0.65rem;
    justify-content: center; max-width: 520px; margin: 0.5rem auto 0;
}
.cap-card {
    background: linear-gradient(135deg, rgba(244,63,110,0.08) 0%, rgba(236,72,120,0.04) 100%);
    border: 1px solid rgba(236,72,120,0.25);
    border-radius: 1.2rem;
    padding: 0.35rem 0.85rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: #c0185c;
    cursor: default;
    transition: all 0.2s ease;
    white-space: nowrap;
    box-shadow: 0 2px 8px rgba(244,63,110,0.08);
}
.cap-card:hover {
    background: linear-gradient(135deg, rgba(244,63,110,0.18) 0%, rgba(236,72,120,0.1) 100%);
    border-color: rgba(236,72,120,0.55);
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(244,63,110,0.18);
}

/* ── Fund name tags (homepage) ─────────────────────────────────── */
.fund-list {
    display: flex; flex-wrap: wrap; gap: 0.5rem;
    justify-content: center; max-width: 600px;
    margin: 1rem auto 0.4rem;
}
.fund-tag {
    background: rgba(192, 24, 92, 0.06);
    border: 1px solid rgba(192, 24, 92, 0.2);
    border-radius: 2rem;
    padding: 0.35rem 0.95rem;
    font-size: 0.76rem;
    font-weight: 500;
    color: rgba(100, 20, 60, 0.75);
    white-space: nowrap;
}

/* ── Chat messages ─────────────────────────────────────────────── */
.chat-area {
    display: flex; flex-direction: column;
    gap: 3.5rem;
    padding: 2rem 0 8rem 0;   /* 8rem bottom = clears the fixed input bar */
    max-width: 780px;
    margin: 0 auto;
}
.msg-row-user {
    display: flex; justify-content: flex-end;
    align-items: flex-end; gap: 0.5rem;
    margin-top: 0.5rem; margin-bottom: 1rem;
}
.msg-row-bot {
    display: flex; justify-content: flex-start;
    align-items: flex-end; gap: 0.5rem;
    margin-top: 0.6rem; margin-bottom: 0.8rem;
}

.bubble-user {
    background: linear-gradient(135deg, #f43f6e 0%, #e91e8c 60%, #c0185c 100%);
    color: #fff;
    border-radius: 1.4rem 1.4rem 0.35rem 1.4rem;
    padding: 0.9rem 1.2rem; max-width: 62%;
    font-size: 0.9rem; line-height: 1.6;
    box-shadow: 0 4px 20px rgba(244,63,110,0.32);
    font-weight: 500;
    white-space: pre-wrap;
}
.bubble-bot {
    background: #ffffff;
    border: 1px solid rgba(236, 72, 120, 0.15);
    color: #2d0a1a;
    border-radius: 1.4rem 1.4rem 1.4rem 0.35rem;
    padding: 0.95rem 1.2rem; max-width: 72%;
    font-size: 0.9rem; line-height: 1.7;
    box-shadow: 0 4px 20px rgba(100,20,50,0.07);
}
.bubble-blocked {
    border-color: rgba(220, 80, 80, 0.35) !important;
    background: rgba(255,240,240,0.9) !important;
    color: #c0392b !important;
}
.av { width: 30px; height: 30px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.78rem; flex-shrink: 0; }
.av-bot  {
    background: linear-gradient(135deg, #ff9ec6, #f43f6e);
    box-shadow: 0 0 8px rgba(244,63,110,0.4);
}
.av-user {
    background: rgba(244,63,110,0.12);
    border: 1px solid rgba(244,63,110,0.3);
}

.src-tag {
    display: inline-block; margin-top: 0.5rem;
    padding: 0.2rem 0.6rem;
    background: rgba(244,63,110,0.08);
    border: 1px solid rgba(236,72,120,0.25);
    border-radius: 1rem; font-size: 0.7rem; color: #c0185c;
    text-decoration: none; margin-right: 0.3rem;
}
.ts-tag { font-size: 0.66rem; color: rgba(100,30,60,0.45); margin-top: 0.1rem; }
.src-row  { margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.3rem; align-items: center; }
.src-block { margin-top: 0.6rem; display: flex; flex-direction: column; gap: 0.3rem; }
.src-item  { display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; }

/* ── Sticky footer (stBottom) — solid bg so content hides behind it ── */
[data-testid="stBottom"] {
    background: linear-gradient(to bottom,
        rgba(252,232,239,0) 0%,
        rgba(252,232,239,1) 30%,
        rgba(252,232,239,1) 100%) !important;
    padding-top: 1.2rem !important;
    border-top: none !important;
    box-shadow: none !important;
}
[data-testid="stBottom"] > div,
[data-testid="stBottom"] > div > div,
[data-testid="stBottom"] > div > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
    outline: none !important;
}

/* ── Chat input wrapper — kill all border/bg on every ancestor ── */
[data-testid="stChatInputContainer"],
[data-testid="stChatInputContainer"] > div,
[data-testid="stChatInputContainer"] > div > div {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    outline: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}

/* ── Chat input bar — centered, blends with bg ─────────────────── */
[data-testid="stChatInput"],
.stChatInput {
    background: transparent !important;
    background-color: transparent !important;
    max-width: 780px !important;
    margin: 0 auto !important;
    width: 100% !important;
    box-shadow: none !important;
    border: none !important;
    padding: 0.4rem 0 0.6rem !important;
}
.stChatInput > div,
[data-testid="stChatInput"] > div {
    background: transparent !important;
    max-width: 780px !important;
    border: none !important;
    box-shadow: none !important;
}
.stChatInput textarea {
    background: rgba(255,255,255,0.95) !important;
    border: 1.5px solid rgba(236,72,120,0.35) !important;
    border-radius: 1.4rem !important;
    color: #2d0a1a !important;
    font-size: 0.9rem !important;
    box-shadow: 0 2px 16px rgba(244,63,110,0.10) !important;
    padding: 0.75rem 1.1rem !important;
}
.stChatInput textarea:focus {
    border-color: rgba(244,63,110,0.65) !important;
    box-shadow: 0 0 0 3px rgba(244,63,110,0.11) !important;
    outline: none !important;
}
.stChatInput textarea::placeholder { color: rgba(150,50,80,0.38) !important; }
.stChatInput button {
    background: linear-gradient(135deg, #f43f6e, #c0185c) !important;
    border-radius: 50% !important;
    color: #fff !important;
    box-shadow: 0 2px 12px rgba(244,63,110,0.35) !important;
    border: none !important;
}

/* ── Main buttons (non-sidebar) ─────────────────────────────── */
.main > div .stButton > button,
div[data-testid="column"] .stButton > button {
    background: linear-gradient(135deg, #f43f6e, #c0185c) !important;
    color: #fff !important; border: none !important;
    border-radius: 0.7rem !important;
    padding: 0.5rem 1rem !important;
    font-weight: 600 !important; font-size: 0.82rem !important;
    box-shadow: 0 3px 14px rgba(244,63,110,0.3) !important;
    transition: all 0.18s ease !important;
}
div[data-testid="column"] .stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 20px rgba(244,63,110,0.45) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(236,72,120,0.3); border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Data / Suggestions
# ─────────────────────────────────────────────────────────────────────────────

SIDEBAR_SUGGESTIONS = [
    "What is the NAV and expense ratio of HDFC Mid Cap?",
    "Does HDFC ELSS have a lock-in period?",
    "What are the top holdings of HDFC Flexi Cap Fund?",
]

HOME_SUGGESTIONS = [
    "💹  What is the HDFC Mid Cap expense ratio?",
    "📊  What is the minimum SIP for HDFC ELSS?",
    "🏢  Top 3 holdings of HDFC Flexi Cap Fund",
]

CAPABILITIES = [
    "💲 NAV Price", "📉 Expense Ratio", "🔒 Lock-in Period",
    "🔄 Exit Load", "💸 Minimum SIP", "⚠️ Riskometer", "🏦 Top Holdings",
]


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────

for key, val in [("messages", []), ("pending", None)]:
    if key not in st.session_state:
        st.session_state[key] = val


# ─────────────────────────────────────────────────────────────────────────────
# RAG — cached singleton
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_rag():
    from rag_pipeline import MutualFundRAG  # noqa
    return MutualFundRAG()


def run_query(query: str):
    """Append user msg, call RAG, append bot msg."""
    st.session_state.messages.append({"role": "user", "content": query})
    try:
        rag = load_rag()
        resp = rag.answer(query)
        st.session_state.messages.append({
            "role": "assistant",
            "content": resp.answer,
            "sources": resp.sources,
            "blocked": resp.blocked,
        })
    except Exception as exc:  # noqa: BLE001
        import traceback
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"⚠️ Error: {exc}\n\n```python\n{traceback.format_exc()}\n```",
            "sources": [], "blocked": False,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Process pending (from chip/sidebar clicks — happens at top of each run)
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.pending:
    q = st.session_state.pending
    st.session_state.pending = None
    run_query(q)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — fixed, no scroll
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<div class="sb-title">🔮 HDFC MF Chatbot</div>', unsafe_allow_html=True)
    st.markdown('<div class="sb-sub">Powered by Groq · llama-3.3-70b-versatile</div>', unsafe_allow_html=True)
    st.markdown('<hr class="sb-hr"/>', unsafe_allow_html=True)
    st.markdown('<div class="sb-label">Quick Prompts</div>', unsafe_allow_html=True)

    for i, s in enumerate(SIDEBAR_SUGGESTIONS):
        if st.button(s, key=f"sb_{i}", use_container_width=True):
            st.session_state.pending = s
            st.rerun()

    st.markdown('<hr class="sb-hr"/>', unsafe_allow_html=True)

    if st.button("🗑️  Clear Chat", use_container_width=True, key="clear"):
        st.session_state.messages = []
        try:
            load_rag().clear_history()
        except Exception:  # noqa
            pass
        st.rerun()

    st.markdown(f"""
    <hr class="sb-hr"/>
    <div class="sb-disclaimer">
    ⚠️ <strong>Disclaimer:</strong> Informational only.
    Not investment advice. Data from INDmoney.com.
    Consult a SEBI-registered advisor.<br/><br/>
    📅 Data as of: <strong>03 Mar 2026</strong>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main content
# ─────────────────────────────────────────────────────────────────────────────

is_home = len(st.session_state.messages) == 0

# ── HOME PAGE — centered MF capabilities ─────────────────────────────────────
if is_home:
    caps_html = "".join(f'<div class="cap-card">{p}</div>' for p in CAPABILITIES)
    st.markdown(f"""
    <div class="home-center">
        <div class="orb-wrap">
            <div class="shard"></div><div class="shard"></div><div class="shard"></div>
            <div class="shard"></div><div class="shard"></div><div class="shard"></div>
            <div class="shard"></div><div class="shard"></div>
            <div class="orb"></div>
        </div>
        <p class="home-title">Ask About HDFC<br/>Mutual Funds</p>
        <div class="home-info-row">
            <div class="home-desc-col">
                An AI-powered chatbot that answers real questions about
                HDFC's 5 flagship mutual funds — instantly, accurately,
                and with full source transparency.
            </div>
            <div class="home-funds-col">
                <p>Covered Funds</p>
                <ul>
                    <li>HDFC Mid Cap Opportunities Fund</li>
                    <li>HDFC Small Cap Fund</li>
                    <li>HDFC ELSS Tax Saver Fund</li>
                    <li>HDFC Large Cap Fund</li>
                    <li>HDFC Flexi Cap Fund</li>
                </ul>
            </div>
        </div>
        <div class="caps-grid">
            {caps_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


# -- CHAT VIEW ---------------------------------------------------------------
else:
    import re as _re
    import html as _html_lib

    _PRIVATE_KEYWORDS = (
        "pan", "pan number", "pan card",
        "account number", "bank account", "demat account",
        "password", "otp", "pin", "cvv",
        "personal", "aadhaar", "aadhar",
        "tax id", "gstin", "passbook",
        "mobile number", "phone number", "email id",
        "credit card", "debit card",
        "kyc", "ifsc", "nominee",
    )

    _FUND_PATTERNS = {
        "hdfc-small-cap-3580":     ["small cap", "small-cap"],
        "hdfc-flexi-cap-3184":     ["flexi cap", "flexi-cap"],
        "hdfc-elss-taxsaver-2685": ["elss", "tax saver", "taxsaver"],
        "hdfc-mid-cap-3097":       ["mid cap", "mid-cap"],
        "hdfc-large-cap-2989":     ["large cap", "large-cap", "top 100"],
    }

    def _is_private(text: str) -> bool:
        t = text.lower()
        return any(kw in t for kw in _PRIVATE_KEYWORDS)

    def _relevant_sources(sources: list, query: str, response: str) -> list:
        combined = (query + ' ' + response).lower()
        result, seen = [], set()
        for s in sources:
            url   = s.get("url", "")
            fid   = s.get("fund_id", "")
            fname = s.get("fund_name", "")
            if not url or url in seen or 'indmoney.com' not in url:
                continue
            pats = _FUND_PATTERNS.get(fid, [])
            if any(p in combined for p in pats) or fname.lower() in combined:
                seen.add(url)
                result.append(s)
        if not result:
            for s in sources:
                url = s.get("url", "")
                if url and url not in seen and 'indmoney.com' in url:
                    seen.add(url)
                    result.append(s)
        return result

    def _fmt_inline(text: str) -> str:
        text = _html_lib.escape(text)
        text = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = _re.sub(r'__(.+?)__',     r'<strong>\1</strong>', text)
        text = _re.sub(r'\*([^\*]+?)\*', r'<em>\1</em>', text)
        text = _re.sub(r'`(.+?)`',       r'<code>\1</code>', text)
        text = text.replace('&#x20b9;', '₹')
        return text

    def _md_to_html(text: str) -> str:
        lines = text.split('\n')
        out, in_ul, in_ol = [], False, False
        for line in lines:
            s = line.strip()
            ol_m = _re.match(r'^(\d+)\.\s+(.*)', s)
            is_ul = s.startswith(('- ', '* ', '+ '))
            if ol_m:
                if in_ul: out.append('</ul>'); in_ul = False
                if not in_ol: out.append('<ol>'); in_ol = True
                out.append(f'<li>{_fmt_inline(ol_m.group(2))}</li>')
            elif is_ul:
                if in_ol: out.append('</ol>'); in_ol = False
                if not in_ul: out.append('<ul>'); in_ul = True
                out.append(f'<li>{_fmt_inline(s[2:])}</li>')
            else:
                if in_ul: out.append('</ul>'); in_ul = False
                if in_ol: out.append('</ol>'); in_ol = False
                if s.startswith('### '): out.append(f'<h4>{_fmt_inline(s[4:])}</h4>')
                elif s.startswith('## '): out.append(f'<h3>{_fmt_inline(s[3:])}</h3>')
                elif s.startswith('# '): out.append(f'<h3>{_fmt_inline(s[2:])}</h3>')
                elif s.startswith('---') or s.startswith('***'): out.append('<hr/>')
                elif s == '': out.append('<br/>')
                else: out.append(f'<p>{_fmt_inline(s)}</p>')
        if in_ul: out.append('</ul>')
        if in_ol: out.append('</ol>')
        return ''.join(out)

    def _clean_text(text: str) -> str:
        text = _re.sub(r'\n?(Source:\s*.+|Data last updated:\s*.+)', '', text, flags=_re.IGNORECASE)
        text = _re.sub(r'</?div[^>]*>', '', text, flags=_re.IGNORECASE)
        text = _re.sub(r'</?span[^>]*>', '', text, flags=_re.IGNORECASE)
        text = _re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _fmt_ts(ts: str) -> str:
        try:
            return datetime.fromisoformat(ts).strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            return ts

    for msg in st.session_state.messages:
        role    = msg["role"]
        content = msg["content"]

        if role == 'user':
            safe = _html_lib.escape(content)
            st.markdown(
                f'<div class="msg-row-user">'
                f'<div class="bubble-user">{safe}</div>'
                f'<div class="av av-user">👤</div></div>',
                unsafe_allow_html=True,
            )
            continue

        blocked = msg.get('blocked', False)
        sources = msg.get('sources', [])
        bc      = 'bubble-blocked' if blocked else ''
        clean   = _clean_text(content)

        user_msgs  = [m['content'] for m in st.session_state.messages if m['role'] == 'user']
        last_query = user_msgs[-1] if user_msgs else ''

        cl = clean.lower()
        is_guardrail = (
            blocked
            or _is_private(last_query)
            or _is_private(clean)
            or clean.startswith('⚠️')
            or 'not allowed'          in cl
            or 'i cannot'             in cl
            or 'i’m sorry'             in cl
            or "i'm sorry"            in cl
            or 'personal information' in cl
            or 'cannot provide'       in cl
            or 'cannot share'         in cl
            or 'confidential'         in cl
            or 'source: none'         in cl
            or cl.startswith("i don't")
            or cl.startswith('i do not')
        )

        body_html = _md_to_html(clean)

        src_html = ''
        if not is_guardrail and sources:
            rel = _relevant_sources(sources, last_query, clean)
            if rel:
                parts = ['<div class="src-block">']
                for s in rel:
                    url  = s.get("url", "")
                    name = s.get("fund_name", "Source")
                    ts   = s.get("scraped_at", "")
                    ts_span = f'<span class="ts-tag">&nbsp;📅 {_fmt_ts(ts)}</span>' if ts else ''
                    parts.append(
                        f'<div class="src-item">'
                        f'<a class="src-tag" href="{url}" target="_blank">🔗 {name}</a>'
                        f'{ts_span}</div>'
                    )
                parts.append('</div>')
                src_html = ''.join(parts)

        st.markdown(
            f'<div class="msg-row-bot">'
            f'<div class="av av-bot">🔮</div>'
            f'<div class="bubble-bot {bc}">'
            f'{body_html}'
            f'{src_html}'
            f'</div></div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Sticky input
# ---------------------------------------------------------------------------

user_input = st.chat_input("❖  Ask about any HDFC Mutual Fund...")
if user_input and user_input.strip():
    run_query(user_input.strip())
    st.rerun()
