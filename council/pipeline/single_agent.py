"""Single-agent baseline used by the A/B harness (`council compare`)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from council.agents.loader import load_solo_designer
from council.pipeline import prompts
from council.pipeline.orchestrator import CallRecord
from council.pipeline.schemas import SoloDesign
from council.providers.base import Provider, ProviderResponse


@dataclass
class SoloRunResult:
    design: SoloDesign
    calls: list[CallRecord]
    wall_time_seconds: float


def run_solo(provider: Provider, brief_text: str) -> SoloRunResult:
    role = load_solo_designer()
    start = time.perf_counter()
    user_prompt = prompts.render_solo_prompt(brief_text, role.round1_instructions)
    resp: ProviderResponse = provider.complete(
        role="solo_designer",
        round_num=1,
        system_prompt=role.system_prompt,
        user_prompt=user_prompt,
        response_model=SoloDesign,
        context={"brief": brief_text},
    )
    wall_time = time.perf_counter() - start
    call = CallRecord(
        role="solo_designer",
        round=1,
        tokens_in=resp.tokens_in,
        tokens_out=resp.tokens_out,
        estimated_cost_usd=resp.estimated_cost_usd,
        latency_seconds=resp.latency_seconds,
        provider_name=resp.provider_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return SoloRunResult(design=resp.parsed, calls=[call], wall_time_seconds=wall_time)
