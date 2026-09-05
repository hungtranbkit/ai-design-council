"""Unit tests for the OpenAI adapter's own logic (auth check, response
mapping, error wrapping) - all without a real network call or API key, by
monkeypatching the constructed SDK client's `.responses.parse`.

A real end-to-end call against the live API is deliberately NOT part of this
suite (no key is configured in CI) - see README for how to run one manually.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from council.pipeline.schemas import Proposal
from council.providers.base import ProviderError

openai = pytest.importorskip("openai", reason="openai extra not installed - pip install -e '.[openai]'")

# OpenAIProvider itself lazy-imports `openai` inside __init__, but this whole
# test file exercises real SDK exception types, so skip the file (not just
# individual tests) when the optional [openai] extra isn't installed.
from council.providers.openai_provider import OpenAIProvider  # noqa: E402


def _fake_usage(tokens_in=100, tokens_out=50):
    return SimpleNamespace(input_tokens=tokens_in, output_tokens=tokens_out)


def _fake_response(*, output_parsed, status="completed", output_text="", error=None, incomplete_details=None, output=None):
    return SimpleNamespace(
        status=status,
        output_parsed=output_parsed,
        output_text=output_text,
        output=output or [],
        error=error,
        incomplete_details=incomplete_details,
        usage=_fake_usage(),
        _request_id="req_test123",
    )


@pytest.fixture()
def provider():
    return OpenAIProvider(api_key="fake-test-key-not-real", model="gpt-6-astra")


def test_missing_api_key_raises_provider_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY"):
        OpenAIProvider()


def test_defaults_to_gpt_6_astra(provider):
    assert provider.model == "gpt-6-astra"


def test_model_overridable_via_env(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-mini")
    p = OpenAIProvider(api_key="fake-test-key-not-real")
    assert p.model == "gpt-5.4-mini"


def test_successful_call_returns_provider_response(provider):
    valid_proposal = Proposal(role="architect", summary="x", requirements=["r"], decisions=["d"])
    fake_resp = _fake_response(output_parsed=valid_proposal, output_text=valid_proposal.model_dump_json())
    provider._client.responses.parse = lambda **kwargs: fake_resp

    resp = provider.complete(
        role="architect",
        round_num=1,
        system_prompt="sys",
        user_prompt="user",
        response_model=Proposal,
        context={},
    )
    assert resp.parsed is valid_proposal
    assert resp.tokens_in == 100
    assert resp.tokens_out == 50
    assert resp.provider_name == "openai"
    assert resp.estimated_cost_usd is not None and resp.estimated_cost_usd > 0
    assert resp.metadata["request_id"] == "req_test123"


def test_none_parsed_output_raises_provider_error(provider):
    fake_resp = _fake_response(output_parsed=None, status="completed")
    provider._client.responses.parse = lambda **kwargs: fake_resp

    with pytest.raises(ProviderError, match="did not return structured output"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_incomplete_status_raises_provider_error(provider):
    fake_resp = _fake_response(
        output_parsed=None, status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens")
    )
    provider._client.responses.parse = lambda **kwargs: fake_resp

    with pytest.raises(ProviderError, match="not completed"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_refusal_raises_provider_error_with_refusal_text(provider):
    refusal_block = SimpleNamespace(type="refusal", refusal="I can't help with that.")
    message_item = SimpleNamespace(type="message", content=[refusal_block])
    fake_resp = _fake_response(output_parsed=None, status="failed", output=[message_item])
    provider._client.responses.parse = lambda **kwargs: fake_resp

    with pytest.raises(ProviderError, match="can't help"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_validation_error_from_sdk_is_wrapped(provider):
    def _raise(**kwargs):
        raise ValidationError.from_exception_data("Proposal", [])

    provider._client.responses.parse = _raise
    with pytest.raises(ProviderError, match="schema validation"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_rate_limit_error_is_wrapped(provider):
    def _raise(**kwargs):
        response = SimpleNamespace(status_code=429, headers={}, request=SimpleNamespace())
        raise openai.RateLimitError("rate limited", response=response, body=None)

    provider._client.responses.parse = _raise
    with pytest.raises(ProviderError, match="rate limit"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_authentication_error_is_wrapped(provider):
    def _raise(**kwargs):
        response = SimpleNamespace(status_code=401, headers={}, request=SimpleNamespace())
        raise openai.AuthenticationError("bad key", response=response, body=None)

    provider._client.responses.parse = _raise
    with pytest.raises(ProviderError, match="authentication failed"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})
