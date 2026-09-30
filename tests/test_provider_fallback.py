"""
tests/test_provider_fallback.py
Tests for LLM provider fallback logic.
Simulates Gemini returning 429, verifies fallback to Groq.
All patches done within test functions to avoid module-level side effects.
"""
import os
import pytest
from unittest.mock import patch
from pydantic import BaseModel


class SimpleSchema(BaseModel):
    result: str = "default"


def _clear_cache():
    """Clear LLM disk cache between tests to prevent cache hits."""
    import backend.llm as llm_module
    import shutil
    cache_dir = llm_module.CACHE_DIR
    if cache_dir.exists():
        for f in cache_dir.glob("*.json"):
            f.unlink(missing_ok=True)


def test_fallback_on_gemini_429():
    """Simulate Gemini 429 -> should fall back to Groq."""
    import backend.llm as llm_module
    _clear_cache()

    def mock_gemini_429(prompt: str) -> str:
        raise RuntimeError("429 Too Many Requests")

    def mock_groq_ok(prompt: str) -> str:
        return '{"result": "groq_answer"}'

    with patch.object(llm_module, "MOCK_MODE", False):
        with patch.object(llm_module, "GEMINI_API_KEY", "fake-gemini-key"):
            with patch.object(llm_module, "GROQ_API_KEY", "fake-groq-key"):
                with patch.object(llm_module, "_call_gemini", side_effect=mock_gemini_429):
                    with patch.object(llm_module, "_call_groq", side_effect=mock_groq_ok):
                        with patch.object(llm_module, "BACKOFF_BASE", 0.001):
                            result = llm_module.generate_json("test prompt fallback1", SimpleSchema)
                            assert result.result == "groq_answer"
                            assert llm_module._active_provider == "groq"


def test_fallback_on_gemini_repeated_failure():
    """Gemini fails multiple times -> falls back to Groq."""
    import backend.llm as llm_module
    _clear_cache()

    def mock_gemini_fail(prompt: str) -> str:
        raise RuntimeError("500 Internal Server Error")

    def mock_groq_ok(prompt: str) -> str:
        return '{"result": "groq_fallback"}'

    with patch.object(llm_module, "MOCK_MODE", False):
        with patch.object(llm_module, "GEMINI_API_KEY", "fake-gemini-key"):
            with patch.object(llm_module, "GROQ_API_KEY", "fake-groq-key"):
                with patch.object(llm_module, "_call_gemini", side_effect=mock_gemini_fail):
                    with patch.object(llm_module, "_call_groq", side_effect=mock_groq_ok):
                        with patch.object(llm_module, "BACKOFF_BASE", 0.001):
                            result = llm_module.generate_json("test prompt fallback2", SimpleSchema)
                            assert result.result == "groq_fallback"


def test_no_fallback_when_both_fail():
    """If both providers fail, raise RuntimeError."""
    import backend.llm as llm_module
    _clear_cache()

    def mock_fail(prompt: str) -> str:
        raise RuntimeError("429 rate limit")

    with patch.object(llm_module, "MOCK_MODE", False):
        with patch.object(llm_module, "GEMINI_API_KEY", "fake-gemini-key"):
            with patch.object(llm_module, "GROQ_API_KEY", "fake-groq-key"):
                with patch.object(llm_module, "_call_gemini", side_effect=mock_fail):
                    with patch.object(llm_module, "_call_groq", side_effect=mock_fail):
                        with patch.object(llm_module, "BACKOFF_BASE", 0.001):
                            with patch.object(llm_module, "MAX_RETRIES", 1):
                                with pytest.raises(RuntimeError):
                                    llm_module.generate_json("test prompt both_fail", SimpleSchema)


def test_json_validation_retry():
    """If provider returns invalid JSON on first call, retry with valid JSON."""
    import backend.llm as llm_module
    _clear_cache()

    call_count = [0]

    def mock_gemini_retry(prompt: str) -> str:
        call_count[0] += 1
        if call_count[0] == 1:
            return "not valid json"
        return '{"result": "valid_on_retry"}'

    with patch.object(llm_module, "MOCK_MODE", False):
        with patch.object(llm_module, "GEMINI_API_KEY", "fake-gemini-key"):
            with patch.object(llm_module, "GROQ_API_KEY", ""):
                with patch.object(llm_module, "_call_gemini", side_effect=mock_gemini_retry):
                    with patch.object(llm_module, "BACKOFF_BASE", 0.001):
                        with patch.object(llm_module, "MAX_RETRIES", 3):
                            result = llm_module.generate_json("test prompt json_retry", SimpleSchema)
                            assert result.result == "valid_on_retry"
                            assert call_count[0] == 2


def test_no_keys_mock_false_raises():
    """With MOCK_MODE=false and no keys, should raise RuntimeError."""
    import backend.llm as llm_module

    with patch.object(llm_module, "MOCK_MODE", False):
        with patch.object(llm_module, "GEMINI_API_KEY", ""):
            with patch.object(llm_module, "GROQ_API_KEY", ""):
                with pytest.raises(RuntimeError, match="No LLM API keys"):
                    llm_module.generate_json("test", SimpleSchema)


def test_mock_mode_active_by_default():
    """In MOCK_MODE, generate_json returns a valid instance."""
    import backend.llm as llm_module
    from backend.models import LLMIssueList

    with patch.object(llm_module, "MOCK_MODE", True):
        # Use a known schema that has a fallback
        result = llm_module.generate_json("dummy prompt for issues", LLMIssueList)
        assert isinstance(result, LLMIssueList)
        assert llm_module._active_provider == "mock"
