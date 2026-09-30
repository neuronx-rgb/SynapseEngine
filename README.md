# Synapse Engine

**An LLM Specification Compiler** — paste product requirements in plain English, get machine-checkable artifacts with full traceability.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![MOCK_MODE](https://img.shields.io/badge/MOCK__MODE-true-green.svg)](#mock-mode)

---

## What It Does

1. **Parse** → Splits requirements into atomic items (REQ-001…), extracts entities, actions, and structured constraints.
2. **Analyze** → Detects ambiguity (lexicon + LLM), conflicts (Z3 SMT + LLM), and incompleteness (checklist).
3. **Clarify** → One targeted question per issue; loop until no blocking issues. Explicit decision log — zero silent assumptions.
4. **Generate** → OpenAPI 3 YAML, SQL DDL, Test Plan JSON with traceability to each requirement.
5. **Verify** → Validates each artifact deterministically; repairs via LLM if needed (up to 2 attempts).
6. **Trace** → Interactive graph + matrix: REQ → API endpoint / DB table / test case.

---

## Quick Start

```bash
# 1. Clone and set up
git clone <repo-url>
cd synapse-engine
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure (copy and edit)
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux

# 4. Run in MOCK_MODE (no API keys needed)
streamlit run streamlit_app.py
```

Open http://localhost:8501 in your browser.

---

## API Keys (Optional — Real LLM Mode)

- **Gemini** (primary): [Get a free key at Google AI Studio](https://aistudio.google.com/app/apikey)
- **Groq** (fallback): [Get a free key at Groq Console](https://console.groq.com/keys)

Set in `.env`:
```
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here
MOCK_MODE=false
```

---

## Running Tests

```bash
# All tests (offline, MOCK_MODE=true)
pytest tests/ -v

# Run evaluation metrics
python eval/run_eval.py

# Manual real LLM connectivity check (requires keys)
python scripts/test_llm.py
```

---

## Running Backend Separately

```bash
# Terminal 1: FastAPI backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Streamlit frontend
BACKEND_MODE=remote BACKEND_URL=http://127.0.0.1:8000 streamlit run streamlit_app.py
```

---

## Architecture

```
streamlit_app.py          # Root entry point (embedded backend launcher)
├── backend/
│   ├── main.py           # FastAPI app factory
│   ├── models.py         # SQLModel DB + Pydantic API/LLM schemas
│   ├── db.py             # SQLite engine (./data/synapse.db)
│   ├── llm.py            # Multi-provider LLM (Gemini → Groq fallback, cache, MOCK_MODE)
│   ├── routes.py         # All REST endpoints
│   └── pipeline/
│       ├── parser.py     # Requirement atomization + constraint extraction
│       ├── analyzer.py   # Ambiguity (lexicon+LLM), Conflict (Z3+LLM), Completeness
│       ├── clarifier.py  # Issue answer/assume loop, decision log
│       ├── generator.py  # OpenAPI YAML, SQL DDL, Test Plan (separate LLM calls)
│       ├── validators.py # OpenAPI spec-validator, SQLite exec, Pydantic, coverage
│       └── traceability.py # networkx graph, matrix, decision log
└── frontend/
    ├── app.py            # Streamlit 5-tab UI (dark navy theme)
    └── api_client.py     # httpx wrapper (BACKEND_MODE switching)
```

### LLM Provider Strategy

```
generate_json(prompt, schema)
  │
  ├─ MOCK_MODE=true → fixture lookup → minimal valid instance
  │
  └─ MOCK_MODE=false
       ├─ Try Gemini (exponential backoff on 429/5xx, up to 3 retries)
       │   └─ On failure → fall back to Groq
       ├─ On-disk cache (./data/llm_cache/) keyed by SHA256(prompt+provider+model)
       └─ Validate against Pydantic schema; retry once on invalid JSON
```

---

## REST API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status, provider, MOCK_MODE |
| POST | `/projects` | Create project |
| POST | `/projects/{id}/requirements` | Parse requirements text |
| POST | `/projects/{id}/analyze` | Run all three detectors |
| GET | `/projects/{id}/issues` | List all issues |
| POST | `/issues/{id}/answer` | Answer a clarification question |
| POST | `/issues/{id}/assume` | Assume default (logs to decision log) |
| POST | `/projects/{id}/generate` | Generate + validate artifacts |
| GET | `/projects/{id}/artifacts` | Get all artifacts |
| GET | `/projects/{id}/traceability` | Graph + matrix + decision log |
| GET | `/projects/{id}/export` | ZIP of all artifacts |
| POST | `/evaluate` | Run evaluation suite |

---

## Deployment (Streamlit Community Cloud)

1. **Push to GitHub** (ensure `.gitignore` excludes `.env` and secrets)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app**
3. Pick your repo, branch, and main file: `streamlit_app.py`
4. **Advanced settings** → Python version: 3.11
5. **Secrets** → paste contents of `.streamlit/secrets.toml.example` with real values
6. Click **Deploy**

> ⚠️ **Storage is ephemeral** on Community Cloud — SQLite data resets on each restart. Tables are auto-recreated at startup.
>
> 💤 **Free apps sleep when idle** — first request after sleep may take 10–30 seconds.
>
> 🔒 **Default MOCK_MODE=true** unless API keys are set in secrets.

---

## 2-Minute Demo Script

1. Open the app → sidebar shows `MOCK_MODE 🎭`
2. Click **New Project** in sidebar
3. Go to **Requirements** tab → select **(b) Account Email Conflict** → click **Load Sample** → **Parse & Analyze**
4. App finds: REQ-001 (global unique email) ↔ REQ-003 (family sharing) → `BLOCKING CONFLICT`
5. Go to **Issues** tab → see the conflict card with explanation
6. Type answer: *"Email must be globally unique. Family sharing not permitted."* → **Submit**
7. Click **⚙️ Generate Specifications →**
8. Go to **Specs** tab → see OpenAPI YAML, SQL DDL, Test Plan with ✓ VALID badges
9. Go to **Traceability** tab → interactive graph shows REQ-001 → API endpoints → test cases
10. Decision log shows the resolved conflict with your answer
11. Go to **Evaluation** tab → click **Run Evaluation Now** → see P/R/F1 metrics

---

## Evaluation Results (MOCK_MODE)

| Issue Type | Precision | Recall | F1 |
|-----------|-----------|--------|-----|
| Ambiguity | ~0.80 | ~0.85 | ~0.82 |
| Conflict | ~0.90 | ~0.90 | ~0.90 |
| Incompleteness | ~0.75 | ~0.80 | ~0.77 |

- OpenAPI validity: **100%** (fixture is valid 3.0.3 spec)
- SQL execution: **100%** (SQLite-compatible DDL)
- Test coverage: **93%** (15 test cases covering 14/15 requirements)

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MOCK_MODE` | `true` | Use fixture data (no API calls) |
| `GEMINI_API_KEY` | — | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model |
| `GROQ_API_KEY` | — | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model |
| `BACKEND_MODE` | `embedded` | `embedded` or `remote` |
| `BACKEND_URL` | `http://127.0.0.1:8000` | Backend URL (remote mode) |
| `DATA_DIR` | `./data` | SQLite + cache directory |

---

## Sample Inputs

| File | Description |
|------|-------------|
| `samples/order_system.txt` | 15-req order system with `>$500 approval` threshold |
| `samples/account_email.txt` | **Email uniqueness vs family sharing** (key demo conflict) |
| `samples/salon_booking.txt` | Vague brief: `fast`, `secure`, `as needed`, double negation |

---

*Built for the hackathon. Core principle: **ZERO SILENT ASSUMPTIONS.***
