"""
scripts/test_llm.py
Manual test to verify real LLM API connectivity.
Run: python scripts/test_llm.py
Requires GEMINI_API_KEY and/or GROQ_API_KEY to be set.
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Force real mode for this test
os.environ["MOCK_MODE"] = "false"

from pydantic import BaseModel


class PingResponse(BaseModel):
    message: str
    provider: str


PING_PROMPT = """
Reply with exactly this JSON and nothing else:
{"message": "hello from LLM", "provider": "your_provider_name"}
"""


def test_gemini():
    from backend.llm import GeminiProvider, GEMINI_API_KEY
    if not GEMINI_API_KEY:
        print("  SKIP: GEMINI_API_KEY not set")
        return False
    try:
        provider = GeminiProvider()
        raw = provider.generate(PING_PROMPT)
        print(f"  Gemini raw response: {raw[:200]}")
        print("  ✅ Gemini OK")
        return True
    except Exception as e:
        print(f"  ❌ Gemini FAILED: {e}")
        return False


def test_groq():
    from backend.llm import GroqProvider, GROQ_API_KEY
    if not GROQ_API_KEY:
        print("  SKIP: GROQ_API_KEY not set")
        return False
    try:
        provider = GroqProvider()
        raw = provider.generate(PING_PROMPT)
        print(f"  Groq raw response: {raw[:200]}")
        print("  ✅ Groq OK")
        return True
    except Exception as e:
        print(f"  ❌ Groq FAILED: {e}")
        return False


def main():
    print("=== Synapse Engine — LLM Connectivity Test ===\n")
    print("Testing Gemini...")
    g_ok = test_gemini()
    print("\nTesting Groq...")
    q_ok = test_groq()
    print("\n=== Summary ===")
    print(f"  Gemini: {'✅ OK' if g_ok else '❌ FAIL or SKIP'}")
    print(f"  Groq:   {'✅ OK' if q_ok else '❌ FAIL or SKIP'}")

    if not g_ok and not q_ok:
        print("\nNo providers available. Check your API keys.")
        sys.exit(1)
    else:
        print("\nAt least one provider is working. App is ready for real LLM use.")


if __name__ == "__main__":
    main()
