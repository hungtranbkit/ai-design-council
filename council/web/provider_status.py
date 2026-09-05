"""Which providers are actually usable right now, for the New Session screen
and the Role Catalog's runtime/provider badge.

Deliberately conservative/honest: a provider only shows as "ready" if this
process can actually see credentials for it (or, for Ollama, a live server).
Otherwise it is "planned" - visible in the UI (per the spec) but disabled,
so nobody is misled into picking a provider that will just error out.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request

PROVIDER_INFO = {
    "mock": "Offline, deterministic - the fully tested V0 demo path.",
    "openai": "Calls a real OpenAI model. Requires OPENAI_API_KEY.",
    "anthropic": "Calls a real Claude model. Requires ANTHROPIC_API_KEY.",
    "ollama": "Calls a local Ollama server. Requires `ollama serve` running.",
}

# Kept in sync with each provider module's own DEFAULT_MODEL / fallback -
# shown as a placeholder in the New Session model field, and as the Role
# Catalog's runtime badge. Not imported directly from the provider modules to
# avoid importing the `anthropic`/`openai` packages just to read a string.
DEFAULT_MODEL = {
    "mock": None,
    "openai": "gpt-6-astra",
    "anthropic": "claude-opus-5",
    "ollama": "llama3.1",
}


def _ollama_reachable(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=0.3):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def default_provider_name() -> str:
    """The provider the Role Catalog shows as the pipeline's current shared
    runtime. V0 runs the whole council on one provider (not per-role) - see
    the Role Catalog page's note. Override with COUNCIL_DEFAULT_PROVIDER."""
    return os.environ.get("COUNCIL_DEFAULT_PROVIDER", "mock")


def provider_statuses() -> list[dict]:
    statuses = []
    for name, description in PROVIDER_INFO.items():
        if name == "mock":
            ready, reason = True, "Always available."
        elif name == "openai":
            ready = bool(os.environ.get("OPENAI_API_KEY"))
            reason = "OPENAI_API_KEY set." if ready else "OPENAI_API_KEY not set - planned, not active."
        elif name == "anthropic":
            ready = bool(os.environ.get("ANTHROPIC_API_KEY"))
            reason = "ANTHROPIC_API_KEY set." if ready else "ANTHROPIC_API_KEY not set - planned, not active."
        else:  # ollama
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            ready = _ollama_reachable(base_url)
            reason = f"Reached {base_url}." if ready else f"Could not reach {base_url} - planned, not active."
        model = os.environ.get(f"{name.upper()}_MODEL", DEFAULT_MODEL[name])
        statuses.append(
            {
                "name": name,
                "status": "ready" if ready else "planned",
                "description": description,
                "reason": reason,
                "default_model": model,
            }
        )
    return statuses


def provider_status_by_name(name: str) -> dict | None:
    return next((p for p in provider_statuses() if p["name"] == name), None)
