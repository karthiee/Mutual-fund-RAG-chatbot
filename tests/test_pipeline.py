"""
Phase 4 Integration Test Suite.

Tests the full RAG pipeline end-to-end:
  - Phase 1 data (raw JSON) → Phase 2 chunks → Phase 3 ChromaDB → Phase 4 Groq LLM

Run from project root:
    py -3 tests/test_pipeline.py
    py -3 tests/test_pipeline.py --verbose   (show full LLM answers)
    py -3 tests/test_pipeline.py --guardrails-only  (skip LLM, test guardrails only)

Requirements: Phases 1-3 must be set up and the .env must contain a valid GROQ_API_KEY.
"""

import argparse
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows to avoid charmap codec errors from LLM responses
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add phase directories to path so imports work
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "phase4_rag_pipeline"))
sys.path.insert(0, str(ROOT / "phase3_embedder"))

# ANSI colours for readable output
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ─────────────────────────────────────────────────────────────────────────────
# Test result helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str, passed: bool, detail: str = "", answer: str = ""):
        self.name   = name
        self.passed = passed
        self.detail = detail
        self.answer = answer

    def __str__(self) -> str:
        icon = f"{GREEN}PASS{RESET}" if self.passed else f"{RED}FAIL{RESET}"
        s = f"  [{icon}] {self.name}"
        if self.detail:
            s += f"\n       {YELLOW}{self.detail}{RESET}"
        return s


def _run_test(name: str, rag, query: str, expected_substring: str = None,
              expect_blocked: bool = False, verbose: bool = False) -> TestResult:
    """Run a single test case and return a TestResult."""
    try:
        t0 = time.time()
        response = rag.answer(query)
        elapsed = time.time() - t0

        answer_lower = response.answer.lower()
        expected_lower = (expected_substring or "").lower()

        if expect_blocked:
            passed = response.blocked
            detail = (
                f"Guardrail fired: {response.block_reason}" if passed
                else f"Expected block — got answer: {response.answer[:120]}"
            )
        elif expected_substring:
            passed = expected_lower in answer_lower
            detail = (
                f"Found '{expected_substring}' in answer ({elapsed:.1f}s)"
                if passed
                else f"Expected '{expected_substring}' not found. Answer: {response.answer[:200]}"
            )
        else:
            # Just check we got a non-empty, non-error answer
            passed = bool(response.answer) and not response.blocked
            detail = f"Got answer ({elapsed:.1f}s)"

        if verbose and not expect_blocked:
            print(f"\n  {CYAN}Q: {query}{RESET}")
            print(f"  {BOLD}A: {response.answer[:500]}{RESET}")
            if response.sources:
                for s in response.sources:
                    print(f"  Source: {s['url']}  (updated: {s['scraped_at']})")

        return TestResult(name, passed, detail, response.answer)

    except Exception as exc:  # noqa: BLE001
        return TestResult(name, False, f"Exception: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Test definitions
# ─────────────────────────────────────────────────────────────────────────────

GUARDRAIL_TESTS = [
    # (test_name, query, expected_substring, expect_blocked)
    ("PII — PAN number blocked",
     "My PAN is ABCDE1234F, what funds should I invest in?",
     None, True),

    ("PII — Aadhaar number blocked",
     "My Aadhaar is 1234 5678 9012, can you check my account?",
     None, True),

    ("PII — account keyword blocked",
     "Tell me about my bank account and HDFC Mid Cap NAV",
     None, True),

    ("PII — OTP keyword blocked",
     "My OTP is 784512 verify it please",
     None, True),

    ("Buy/Sell — invest advice blocked",
     "Should I invest in HDFC Small Cap Fund?",
     None, True),

    ("Buy/Sell — sell advice blocked",
     "When should I sell my HDFC ELSS fund?",
     None, True),

    ("Buy/Sell — recommend blocked",
     "Which fund do you recommend for long term?",
     None, True),

    ("Safe query — NAV not blocked",
     "What is the NAV of HDFC Mid Cap Fund?",
     None, False),
]

RAG_TESTS = [
    # (test_name, query, expected_substring_in_answer)

    # ── The primary test case given by the user ──────────────────────────────
    ("HDFC Mid Cap — expense ratio is 0.74%",
     "What is the HDFC Mid Cap expense ratio?",
     "0.74"),

    # ── NAV tests ─────────────────────────────────────────────────────────────
    ("HDFC Mid Cap — NAV",
     "What is the current NAV of HDFC Mid Cap Opportunities Fund?",
     "191"),

    ("HDFC Small Cap — NAV",
     "What is the NAV of HDFC Small Cap Fund?",
     "139"),

    ("HDFC Large Cap — NAV",
     "What is the current NAV of HDFC Top 100 Large Cap Fund?",
     "1,090"),

    # ── Expense ratio tests ───────────────────────────────────────────────────
    ("HDFC Small Cap — expense ratio 0.67%",
     "What is the expense ratio of HDFC Small Cap Fund?",
     "0.67"),

    ("HDFC ELSS — expense ratio 0.82%",
     "Tell me the expense ratio of HDFC ELSS Tax Saver fund",
     "0.82"),

    ("HDFC Flexi Cap — expense ratio 0.75%",
     "What is the TER of HDFC Flexi Cap Fund?",
     "0.75"),

    ("HDFC Large Cap — expense ratio 0.55%",
     "What is the expense ratio of HDFC Top 100 Large Cap?",
     "0.55"),

    # ── Exit load tests ───────────────────────────────────────────────────────
    ("HDFC ELSS — exit load is Nil",
     "Is there any exit load on HDFC ELSS fund?",
     "no exit load"),

    ("HDFC Mid Cap — exit load 1%",
     "What is the exit load for HDFC Mid Cap fund?",
     "1%"),

    # ── SIP and lock-in tests ─────────────────────────────────────────────────
    ("HDFC ELSS — minimum SIP Rs 500",
     "What is the minimum SIP for HDFC ELSS Tax Saver?",
     "500"),

    ("HDFC ELSS — lock-in 3 years",
     "What is the lock-in period of HDFC ELSS?",
     "3"),

    ("HDFC Mid Cap — no lock-in",
     "Does HDFC Mid Cap Fund have a lock-in period?",
     "no"),

    # ── Riskometer tests ──────────────────────────────────────────────────────
    ("HDFC Small Cap — riskometer Very High Risk",
     "What is the risk level of HDFC Small Cap Fund?",
     "very high"),

    # ── Holdings tests ────────────────────────────────────────────────────────
    ("HDFC Mid Cap — top holding Cholamandalam",
     "What are the top holdings of HDFC Mid Cap Fund?",
     "cholamandalam"),

    ("HDFC Flexi Cap — top holding HDFC Bank",
     "What are the top 3 holdings in HDFC Flexi Cap Fund?",
     "hdfc bank"),

    ("HDFC Large Cap — top holding Reliance",
     "What stocks does HDFC Large Cap fund hold?",
     "reliance"),

    # ── Source URL in response ────────────────────────────────────────────────
    ("Response contains indmoney.com source URL",
     "What is the NAV of HDFC ELSS fund?",
     "indmoney.com"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_guardrail_tests() -> list[TestResult]:
    """Test guardrails without needing the LLM (fast)."""
    from guardrails import check_query  # noqa: PLC0415

    results = []
    for name, query, _, expect_blocked in GUARDRAIL_TESTS:
        _, violation = check_query(query)
        actually_blocked = violation is not None
        passed = actually_blocked == expect_blocked
        detail = (
            f"Blocked by: {violation.rule}" if actually_blocked
            else "Not blocked (safe query)"
        )
        results.append(TestResult(name, passed, detail))
    return results


def run_rag_tests(verbose: bool = False) -> list[TestResult]:
    """Full RAG pipeline tests — requires ChromaDB populated and GROQ_API_KEY."""
    from rag_pipeline import MutualFundRAG  # noqa: PLC0415

    print(f"\n{CYAN}Initialising RAG pipeline (loading model + ChromaDB)…{RESET}")
    rag = MutualFundRAG()

    results = []
    for name, query, expected in RAG_TESTS:
        result = _run_test(name, rag, query, expected, verbose=verbose)
        results.append(result)
        print(result)

    return results


def run_guardrail_rag_tests(verbose: bool = False) -> list[TestResult]:
    """Test guardrail behaviour via the full RAG pipeline."""
    from rag_pipeline import MutualFundRAG  # noqa: PLC0415

    rag = MutualFundRAG()
    results = []
    for name, query, _, expect_blocked in GUARDRAIL_TESTS:
        result = _run_test(name, rag, query, expect_blocked=expect_blocked, verbose=verbose)
        results.append(result)
        print(result)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Phase 4 Integration Test Suite — HDFC Mutual Fund RAG Chatbot"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print full LLM answers for each RAG test"
    )
    parser.add_argument(
        "--guardrails-only", action="store_true",
        help="Only run guardrail tests (no LLM calls, fast)"
    )
    parser.add_argument(
        "--rag-only", action="store_true",
        help="Only run RAG accuracy tests (skip guardrail check via RAG pipeline)"
    )
    args = parser.parse_args()

    print(f"\n{BOLD}{'='*60}")
    print("  HDFC Mutual Fund RAG Chatbot — Integration Test Suite")
    print(f"{'='*60}{RESET}\n")

    all_results = []

    # ── Guardrail unit tests (no LLM) ────────────────────────────────────────
    if not args.rag_only:
        print(f"{BOLD}[ Guardrail Unit Tests — no LLM required ]{RESET}")
        g_results = run_guardrail_tests()
        for r in g_results:
            print(r)
        all_results.extend(g_results)

    # ── RAG accuracy tests ────────────────────────────────────────────────────
    if not args.guardrails_only:
        print(f"\n{BOLD}[ RAG Accuracy Tests — Groq llama3-70b-8192 ]{RESET}")
        rag_results = run_rag_tests(verbose=args.verbose)
        all_results.extend(rag_results)

        print(f"\n{BOLD}[ Guardrail Integration Tests — via RAG pipeline ]{RESET}")
        grag_results = run_guardrail_rag_tests(verbose=args.verbose)
        all_results.extend(grag_results)

    # ── Final summary ──────────────────────────────────────────────────────────
    passed = sum(1 for r in all_results if r.passed)
    total  = len(all_results)
    rate   = passed / total * 100 if total else 0

    print(f"\n{BOLD}{'='*60}")
    colour = GREEN if rate >= 80 else (YELLOW if rate >= 60 else RED)
    print(f"  Results: {colour}{passed}/{total} passed ({rate:.0f}%){RESET}")
    if passed < total:
        failures = [r for r in all_results if not r.passed]
        print(f"\n{RED}  Failed tests:{RESET}")
        for r in failures:
            print(f"    - {r.name}")
            if r.detail:
                print(f"      {r.detail}")
    print(f"{BOLD}{'='*60}{RESET}\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
