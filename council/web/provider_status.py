"""Which providers are actually usable right now, for the New Session screen.

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


def _ollama_reachable(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=0.3):
            return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


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
        statuses.append(
            {"name": name, "status": "ready" if ready else "planned", "description": description, "reason": reason}
        )
    return statuses
