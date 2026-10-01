"""
backend/llm.py
Multi-provider LLM layer with:
- Primary: Gemini via google-genai SDK
- Fallback: Groq via groq SDK
- Additional: Ollama (local)
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
import re
from pathlib import Path
from typing import Any, Optional, Type, TypeVar
from abc import ABC, abstractmethod

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() in ("true", "1", "yes")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "")

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
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for fpath in FIXTURE_DIR.glob("*.json"):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        triggers = data.get("triggers", [])
        if any(t.lower() in prompt_hint.lower() for t in triggers):
            return json.dumps(data.get("response", {}))
    return None


def _mock_generate(prompt: str, schema: Type[T]) -> T:
    global _active_provider, _active_model
    _active_provider = "mock"
    _active_model = "mock"

    schema_name = schema.__name__
    logger.info(f"[MOCK] Generating {schema_name}")

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
# Provider Architecture
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> str:
        """Call the LLM and return the raw text response."""
        pass


class GeminiProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return GEMINI_MODEL

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> str:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise RuntimeError("google-genai not installed")

        client = genai.Client(api_key=GEMINI_API_KEY)
        config = types.GenerateContentConfig(temperature=0.1)
        if schema:
            config.response_mime_type = "application/json"

        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        return response.text or ""


class GroqProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return GROQ_MODEL

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> str:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set")
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError("groq not installed")

        client = Groq(api_key=GROQ_API_KEY)
        kwargs = {"temperature": 0.1}
        if schema:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.choices[0].message.content or ""


class OllamaProvider(LLMProvider):
    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return OLLAMA_MODEL

    def generate(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> str:
        if not OLLAMA_MODEL:
            raise RuntimeError("OLLAMA_MODEL not set")
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }
        if schema:
            payload["format"] = "json"

        try:
            response = httpx.post(ollama_url, json=payload, timeout=120.0)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            raise RuntimeError(f"Ollama call failed: {e}")


def get_providers() -> list[LLMProvider]:
    providers = []
    # Primary
    if GEMINI_API_KEY:
        providers.append(GeminiProvider())
    # Fallback
    if GROQ_API_KEY:
        providers.append(GroqProvider())
    # Additional
    if OLLAMA_MODEL:
        providers.append(OllamaProvider())
    return providers


# ---------------------------------------------------------------------------
# Core generate_json
# ---------------------------------------------------------------------------

def generate_json(prompt: str, schema: Type[T]) -> T:
    global _active_provider, _active_model

    if MOCK_MODE:
        return _mock_generate(prompt, schema)

    providers = get_providers()
    if not providers:
        raise RuntimeError(
            "No LLM providers available. Set GEMINI_API_KEY, GROQ_API_KEY, or OLLAMA_MODEL, "
            "or set MOCK_MODE=true for demo mode."
        )

    last_error: Exception = RuntimeError("No providers available")

    for provider in providers:
        cache_key = _cache_key(prompt, provider.name, provider.model_name)
        cached = _cache_get(cache_key)
        if cached:
            try:
                result = schema.model_validate_json(cached)
                _active_provider = provider.name
                _active_model = provider.model_name
                logger.info(f"[LLM] Cache hit for {provider.name}/{provider.model_name}")
                return result
            except Exception:
                pass

        for attempt in range(MAX_RETRIES):
            try:
                raw = provider.generate(prompt, schema)
                parse_error = None
                try:
                    result = schema.model_validate_json(raw)
                except Exception as ve:
                    parse_error = ve
                    raw_stripped = re.sub(r"```json\s*|\s*```", "", raw).strip()
                    # Normalise non-standard severity values produced by some models
                    raw_normalised = re.sub(
                        r'"severity"\s*:\s*"(?!blocking|warning)[^"]*"',
                        lambda m: '"severity": "blocking"' if any(
                            w in m.group(0).lower() for w in ("critical", "high", "error", "major")
                        ) else '"severity": "warning"',
                        raw_stripped,
                    )
                    try:
                        result = schema.model_validate_json(raw_normalised)
                        raw = raw_normalised
                        parse_error = None
                    except Exception as ve2:
                        parse_error = ve2

                if parse_error is not None:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"[LLM] {provider.name} JSON parse error (attempt {attempt+1}): {parse_error}")
                        last_error = parse_error
                        continue
                    else:
                        last_error = parse_error
                        break

                _active_provider = provider.name
                _active_model = provider.model_name
                _cache_set(cache_key, raw)
                logger.info(f"[LLM] {provider.name}/{provider.model_name} answered (attempt {attempt+1})")
                return result

            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower()
                is_server_error = bool(re.search(r"\b5\d{2}\b", err_str)) or "unavailable" in err_str.lower() or "server error" in err_str.lower()

                if is_rate_limit or is_server_error:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(f"[LLM] {provider.name} error (attempt {attempt+1}): {e}. Waiting {wait}s")
                    time.sleep(wait)
                    last_error = e
                    if attempt == MAX_RETRIES - 1:
                        break
                else:
                    last_error = e
                    logger.error(f"[LLM] {provider.name} non-retryable error: {e}")
                    break

    # All providers exhausted — return a safe empty fallback so the pipeline doesn't crash.
    # Deterministic detectors (Z3, lexicon, completeness) already ran and their results
    # are collected by the caller; only the LLM semantic pass is missing.
    logger.error(f"All LLM providers failed. Last error: {last_error}. Returning empty result.")
    schema_name = schema.__name__
    try:
        if schema_name == "ParseResult":
            return schema.model_validate({"requirements": []})
        elif schema_name == "LLMIssueList":
            return schema.model_validate({"issues": []})
        elif schema_name == "OpenAPIGenerateResult":
            return schema.model_validate({"yaml_content": "", "source_req_ids": []})
        elif schema_name == "SQLGenerateResult":
            return schema.model_validate({"ddl_content": "", "source_req_ids": []})
        elif schema_name == "TestPlanResult":
            return schema.model_validate({"test_cases": []})
        else:
            return schema.model_validate({"issues": []})
    except Exception:
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


def generate_text(prompt: str) -> str:
    global _active_provider, _active_model

    if MOCK_MODE:
        _active_provider = "mock"
        _active_model = "mock"
        return "MOCK: No repair needed."

    providers = get_providers()
    if not providers:
        return "Error: No providers available."

    for provider in providers:
        for attempt in range(MAX_RETRIES):
            try:
                result = provider.generate(prompt)
                _active_provider = provider.name
                _active_model = provider.model_name
                return result
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    time.sleep(BACKOFF_BASE ** attempt)
                else:
                    break

    return "Error: All providers failed."


# Initialize UI defaults correctly on startup
if not MOCK_MODE:
    _available = get_providers()
    if _available:
        _active_provider = _available[0].name
        _active_model = _available[0].model_name

