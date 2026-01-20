"""
Utilities for strict JSON parsing with a single retry.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional


class LLMJsonError(ValueError):
    """Raised when LLM output cannot be parsed/validated as JSON."""


def parse_json_with_retry(
    prompt: str,
    llm_call: Callable[[str], str],
    validate_fn: Optional[Callable[[Any], None]] = None,
) -> Any:
    """
    Parse JSON from an LLM response, retrying once with a fix instruction.

    Args:
        prompt: The base prompt to send to the LLM.
        llm_call: Callable that takes a prompt and returns raw text.
        validate_fn: Optional validator; should raise ValueError on invalid shape.

    Returns:
        Parsed JSON object.

    Raises:
        LLMJsonError: If parsing/validation fails after one retry.
    """

    def _attempt(p: str) -> Any:
        raw = llm_call(p)
        if not isinstance(raw, str):
            raise LLMJsonError("LLM output is not a string.")
        obj = json.loads(raw)
        if validate_fn is not None:
            validate_fn(obj)
        return obj

    try:
        return _attempt(prompt)
    except Exception as exc:
        fix_prompt = (
            f"{prompt}\n\nFIX_JSON: Return ONLY valid JSON. "
            "Do not output markdown. Do not add prose."
        )
        try:
            return _attempt(fix_prompt)
        except Exception as exc2:
            raise LLMJsonError(f"Invalid JSON after retry: {exc2}") from exc2
