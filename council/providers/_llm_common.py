"""Shared helpers for real (non-mock) LLM provider adapters."""
from __future__ import annotations

import json
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from council.providers.base import ProviderError, ProviderResponse

ModelT = TypeVar("ModelT", bound=BaseModel)


def build_json_instruction(response_model: type[BaseModel]) -> str:
    """Render a strict 'respond with only this JSON schema' instruction block."""
    schema = response_model.model_json_schema()
    return (
        "You must respond with ONLY a single JSON object - no markdown fences, no "
        "commentary before or after - that validates against this JSON Schema:\n\n"
        f"{json.dumps(schema, indent=2)}\n"
    )


def parse_and_validate(raw_text: str, response_model: type[ModelT]) -> ModelT:
    """Parse an LLM's raw text as JSON and validate it against response_model.

    Real LLMs sometimes wrap JSON in markdown fences despite instructions; we
    strip those defensively before parsing.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"provider returned non-JSON output: {exc}\n---\n{raw_text}") from exc
    try:
        return response_model.model_validate(data)
    except ValidationError as exc:
        raise ProviderError(f"provider output failed schema validation:\n{exc}\n---\n{raw_text}") from exc


def estimate_cost_usd(
    tokens_in: int | None, tokens_out: int | None, price_per_1k_in: float, price_per_1k_out: float
) -> float | None:
    if tokens_in is None or tokens_out is None:
        return None
    return round((tokens_in / 1000) * price_per_1k_in + (tokens_out / 1000) * price_per_1k_out, 6)


def timed_call(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start
