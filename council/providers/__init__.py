from __future__ import annotations

from council.providers.base import Provider, ProviderError, ProviderResponse
from council.providers.mock import MockProvider

PROVIDER_NAMES = ("mock", "openai", "anthropic", "ollama")


def get_provider(name: str, **kwargs) -> Provider:
    """Provider factory. Only 'mock' is exercised by the V0 test suite."""
    if name == "mock":
        return MockProvider()
    if name == "openai":
        from council.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(**kwargs)
    if name == "anthropic":
        from council.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(**kwargs)
    if name == "ollama":
        from council.providers.ollama_provider import OllamaProvider

        return OllamaProvider(**kwargs)
    raise ValueError(f"unknown provider '{name}' (choices: {', '.join(PROVIDER_NAMES)})")


__all__ = ["Provider", "ProviderError", "ProviderResponse", "MockProvider", "get_provider", "PROVIDER_NAMES"]
