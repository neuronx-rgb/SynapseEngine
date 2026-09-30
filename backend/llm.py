"""
backend/llm.py
Multi-provider LLM layer with:
- Primary: Gemini via google-genai SDK
- Fallback: Groq via OpenAI-compatible endpoint
- MOCK_MODE: returns fixture data, no real API calls
- On-disk cache keyed by hash(prompt+provider+model)
- Exponential-backoff + auto-fallback on 429/5xx
- generate_json(): structured output + Pydantic validation
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

CACHE_DIR = Path(os.getenv("CACHE_DIR", "./data/llm_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MAX_RETRIES = 3
BACKOFF_BASE = 2.0

# Track which provider answered last call
_active_provider: str = "mock"
_active_model: str = "mock"


def get_active_provider() -> tuple[str, str]:
    return _active_provider, _active_model


# ---------------------------------------------------------------------------
# On-disk cache
# ---------------------------------------------------------------------------

def _cache_key(prompt: str, provider: str, model: str) -> str:
    raw = f"{prompt}|{provider}|{model}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_get(key: str) -> Optional[str]:
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _cache_set(key: str, value: str) -> None:
    path = CACHE_DIR / f"{key}.json"
    path.write_text(value, encoding="utf-8")


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def _get_fixture(prompt_hint: str) -> Optional[str]:
    """Return a fixture JSON string matching the prompt hint."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    # Match by keyword in prompt
    for fpath in FIXTURE_DIR.glob("*.json"):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        triggers = data.get("triggers", [])
        if any(t.lower() in prompt_hint.lower() for t in triggers):
            return json.dumps(data.get("response", {}))
    return None


def _mock_generate(prompt: str, schema: Type[T]) -> T:
    """Return mock/fixture response matching schema.

    Strategy:
    1. Try to find a fixture whose 'triggers' match the prompt AND
       whose 'response' is valid for the given schema.
    2. Fall back to schema-specific minimal instances.
    """
    global _active_provider, _active_model
    _active_provider = "mock"
    _active_model = "mock"

    schema_name = schema.__name__
    logger.info(f"[MOCK] Generating {schema_name}")

    # Try fixture lookup — attempt ALL matching fixtures and pick valid one
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fpath in FIXTURE_DIR.glob("*.json"):
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            triggers = data.get("triggers", [])
            if not any(t.lower() in prompt.lower() for t in triggers):
                continue
            candidate = json.dumps(data.get("response", {}))
            result = schema.model_validate_json(candidate)
            logger.info(f"[MOCK] Fixture match: {fpath.name} for schema {schema_name}")
            return result
        except Exception:
            continue

    # Schema-specific fallback instances
    if schema_name == "ParseResult":
        return schema.model_validate({
            "requirements": [
                {
                    "req_id": "REQ-001",
                    "text": "The system shall process the request.",
                    "source_sentence": "The system shall process the request.",
                    "entities": ["system", "request"],
                    "actions": ["process"],
                    "constraints": []
                }
            ]
        })
    if schema_name == "LLMIssueList":
        return schema.model_validate({"issues": []})
    if schema_name == "OpenAPIGenerateResult":
        yaml_stub = (
            "openapi: '3.0.3'\n"
            "info:\n  title: Generated API\n  version: '1.0.0'\n"
            "paths:\n  /health:\n    get:\n      summary: Health check\n"
            "      responses:\n        '200':\n          description: OK\n"
        )
        return schema.model_validate({"yaml_content": yaml_stub, "source_req_ids": ["REQ-001"]})
    if schema_name == "SQLGenerateResult":
        ddl_stub = (
            "CREATE TABLE items (\n"
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "  name TEXT NOT NULL\n"
            ");\n"
        )
        return schema.model_validate({"ddl_content": ddl_stub, "source_req_ids": ["REQ-001"]})
    if schema_name == "TestPlanResult":
        return schema.model_validate({
            "test_cases": [
                {
                    "test_id": "TC-001",
                    "name": "Happy path",
                    "category": "positive",
                    "req_ids": ["REQ-001"],
                    "description": "Verify basic functionality",
                    "input_data": {},
                    "expected_outcome": "success"
                }
            ]
        })
    raise ValueError(f"[MOCK] No fixture or fallback for schema {schema_name}")



# ---------------------------------------------------------------------------
# Real providers
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    """Call Gemini API and return raw text."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        return response.text or ""
    except ImportError:
        raise RuntimeError("google-genai not installed")


def _call_groq(prompt: str) -> str:
    """Call Groq via OpenAI-compatible endpoint."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
    except ImportError:
        raise RuntimeError("openai package not installed")


# ---------------------------------------------------------------------------
# Core generate_json
# ---------------------------------------------------------------------------

def generate_json(prompt: str, schema: Type[T]) -> T:
    """
    Generate structured JSON from an LLM and validate against `schema`.
    MOCK_MODE returns fixture/fallback data.
    Real mode: tries Gemini first, then Groq.
    """
    global _active_provider, _active_model

    if MOCK_MODE:
        return _mock_generate(prompt, schema)

    # Check keys
    if not GEMINI_API_KEY and not GROQ_API_KEY:
        raise RuntimeError(
            "No LLM API keys set. Set GEMINI_API_KEY or GROQ_API_KEY, "
            "or set MOCK_MODE=true for demo mode."
        )

    providers = []
    if GEMINI_API_KEY:
        providers.append(("gemini", GEMINI_MODEL, _call_gemini))
    if GROQ_API_KEY:
        providers.append(("groq", GROQ_MODEL, _call_groq))

    last_error: Exception = RuntimeError("No providers available")

    for provider_name, model_name, call_fn in providers:
        cache_key = _cache_key(prompt, provider_name, model_name)
        cached = _cache_get(cache_key)
        if cached:
            try:
                result = schema.model_validate_json(cached)
                _active_provider = provider_name
                _active_model = model_name
                logger.info(f"[LLM] Cache hit for {provider_name}/{model_name}")
                return result
            except Exception:
                pass

        for attempt in range(MAX_RETRIES):
            try:
                raw = call_fn(prompt)
                # Validate JSON — try with markdown fence stripping
                parse_error = None
                try:
                    result = schema.model_validate_json(raw)
                except Exception as ve:
                    parse_error = ve
                    import re as _re
                    raw_stripped = _re.sub(r"```json\s*|\s*```", "", raw).strip()
                    try:
                        result = schema.model_validate_json(raw_stripped)
                        raw = raw_stripped
                        parse_error = None
                    except Exception as ve2:
                        parse_error = ve2

                if parse_error is not None:
                    # JSON parse failure — retry once more (not an API error)
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"[LLM] {provider_name} JSON parse error (attempt {attempt+1}): {parse_error}")
                        last_error = parse_error
                        continue  # retry same provider
                    else:
                        last_error = parse_error
                        break  # try next provider

                _active_provider = provider_name
                _active_model = model_name
                _cache_set(cache_key, raw)
                logger.info(f"[LLM] {provider_name}/{model_name} answered (attempt {attempt+1})")
                return result

            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "rate" in err_str.lower()
                is_server_error = "5" in err_str[:3] if err_str else False

                if is_rate_limit or is_server_error:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(f"[LLM] {provider_name} error (attempt {attempt+1}): {e}. Waiting {wait}s")
                    time.sleep(wait)
                    last_error = e
                    if attempt == MAX_RETRIES - 1:
                        break  # Try next provider
                else:
                    last_error = e
                    logger.error(f"[LLM] {provider_name} non-retryable error: {e}")
                    break  # Try next provider immediately

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")



def generate_text(prompt: str) -> str:
    """Generate plain text (used for repair prompts)."""
    global _active_provider, _active_model

    if MOCK_MODE:
        _active_provider = "mock"
        _active_model = "mock"
        return "MOCK: No repair needed."

    providers = []
    if GEMINI_API_KEY:
        providers.append(("gemini", GEMINI_MODEL, _call_gemini))
    if GROQ_API_KEY:
        providers.append(("groq", GROQ_MODEL, _call_groq))

    for provider_name, model_name, call_fn in providers:
        for attempt in range(MAX_RETRIES):
            try:
                result = call_fn(prompt)
                _active_provider = provider_name
                _active_model = model_name
                return result
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    time.sleep(BACKOFF_BASE ** attempt)
                else:
                    break

    return "Error: All providers failed."
