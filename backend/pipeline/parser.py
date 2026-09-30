"""
backend/pipeline/parser.py
Parses raw requirement text into atomic requirements with IDs.
Extracts entities, actions, and structured constraints.
"""
from __future__ import annotations

import json
import re
from typing import List

from backend.llm import generate_json
from backend.models import ParseResult, ParsedRequirement, ConstraintSchema


# Use string concatenation to avoid .format() conflicts with JSON braces in template
def _build_parse_prompt(text: str) -> str:
    return (
        "You are a requirements engineer. Split the following product requirements text into\n"
        "individual atomic requirements. For each requirement:\n"
        "- Assign an ID like REQ-001, REQ-002, etc.\n"
        "- Write a clear, standalone requirement text (restate it, do not abbreviate)\n"
        "- Extract the original source_sentence from the input\n"
        "- List all business entities (nouns: users, orders, accounts, etc.)\n"
        "- List all actions (verbs: create, approve, share, validate, etc.)\n"
        "- Extract structured constraints as a list of objects with fields:\n"
        "  subject (string), attribute (string), op (one of ==, !=, <, <=, >, >=), value (any)\n"
        "  Only include constraints when there is a clear numeric or categorical bound.\n"
        '  Example: "orders over $500" -> {"subject":"order","attribute":"amount","op":">","value":500}\n'
        "\n"
        "Return ONLY valid JSON matching this schema:\n"
        '{\n'
        '  "requirements": [\n'
        '    {\n'
        '      "req_id": "REQ-001",\n'
        '      "text": "...",\n'
        '      "source_sentence": "...",\n'
        '      "entities": ["..."],\n'
        '      "actions": ["..."],\n'
        '      "constraints": [{"subject":"...","attribute":"...","op":"...","value":"..."}]\n'
        '    }\n'
        '  ]\n'
        '}\n'
        "\n"
        "Requirements text:\n"
        "---\n"
        f"{text.strip()}\n"
        "---\n"
    )


def parse_requirements(text: str) -> ParseResult:
    """
    Split raw text into atomic ParsedRequirements.
    In MOCK_MODE the LLM layer returns fixture data.
    """
    prompt = _build_parse_prompt(text)
    result = generate_json(prompt, ParseResult)
    # Ensure IDs are unique and well-formed
    seen: set[str] = set()
    cleaned: List[ParsedRequirement] = []
    for i, req in enumerate(result.requirements, start=1):
        if not req.req_id or req.req_id in seen:
            req = req.model_copy(update={"req_id": f"REQ-{i:03d}"})
        seen.add(req.req_id)
        cleaned.append(req)
    return ParseResult(requirements=cleaned)
