"""Unit tests for the Anthropic adapter's own logic (auth check, response
mapping, error wrapping) - all without a real network call or API key, by
monkeypatching the constructed SDK client's `.messages.parse`.

A real end-to-end call against the live API is deliberately NOT part of this
suite (no key is configured in CI) - see README for how to run one manually.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from council.pipeline.schemas import Proposal
from council.providers.base import ProviderError

anthropic = pytest.importorskip("anthropic", reason="anthropic extra not installed - pip install -e '.[anthropic]'")

# AnthropicProvider itself lazy-imports `anthropic` inside __init__, but this
# whole test file exercises real SDK exception types, so skip the file (not
# just individual tests) when the optional [anthropic] extra isn't installed.
from council.providers.anthropic_provider import AnthropicProvider  # noqa: E402


def _fake_usage(tokens_in=100, tokens_out=50):
    return SimpleNamespace(input_tokens=tokens_in, output_tokens=tokens_out)


def _fake_text_block(text=""):
    return SimpleNamespace(type="text", text=text)


def _fake_response(*, parsed_output, stop_reason="end_turn", stop_details=None, text=""):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=stop_details,
        parsed_output=parsed_output,
        content=[_fake_text_block(text)],
        usage=_fake_usage(),
        _request_id="req_test123",
    )


@pytest.fixture()
def provider():
    return AnthropicProvider(api_key="fake-test-key-not-real", model="claude-opus-5")


def test_missing_api_key_raises_provider_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider()


def test_defaults_to_claude_opus_5(provider):
    assert provider.model == "claude-opus-5"


def test_model_overridable_via_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5")
    p = AnthropicProvider(api_key="fake-test-key-not-real")
    assert p.model == "claude-sonnet-5"


def test_successful_call_returns_provider_response(provider):
    valid_proposal = Proposal(role="architect", summary="x", requirements=["r"], decisions=["d"])
    fake_resp = _fake_response(parsed_output=valid_proposal, text=valid_proposal.model_dump_json())
    provider._client.messages.parse = lambda **kwargs: fake_resp

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
    assert resp.provider_name == "anthropic"
    assert resp.estimated_cost_usd is not None and resp.estimated_cost_usd > 0
    assert resp.metadata["request_id"] == "req_test123"


def test_none_parsed_output_raises_provider_error(provider):
    fake_resp = _fake_response(parsed_output=None, stop_reason="max_tokens")
    provider._client.messages.parse = lambda **kwargs: fake_resp

    with pytest.raises(ProviderError, match="did not return structured output"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_refusal_raises_provider_error(provider):
    fake_resp = _fake_response(parsed_output=None, stop_reason="refusal", stop_details={"category": "cyber"})
    provider._client.messages.parse = lambda **kwargs: fake_resp

    with pytest.raises(ProviderError, match="refused"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_validation_error_from_sdk_is_wrapped(provider):
    def _raise(**kwargs):
        raise ValidationError.from_exception_data("Proposal", [])

    provider._client.messages.parse = _raise
    with pytest.raises(ProviderError, match="schema validation"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_rate_limit_error_is_wrapped(provider):
    def _raise(**kwargs):
        request = SimpleNamespace()
        response = SimpleNamespace(status_code=429, headers={}, request=SimpleNamespace())
        raise anthropic.RateLimitError("rate limited", response=response, body=None)

    provider._client.messages.parse = _raise
    with pytest.raises(ProviderError, match="rate limit"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})


def test_authentication_error_is_wrapped(provider):
    def _raise(**kwargs):
        response = SimpleNamespace(status_code=401, headers={}, request=SimpleNamespace())
        raise anthropic.AuthenticationError("bad key", response=response, body=None)

    provider._client.messages.parse = _raise
    with pytest.raises(ProviderError, match="authentication failed"):
        provider.complete(role="architect", round_num=1, system_prompt="s", user_prompt="u", response_model=Proposal, context={})
