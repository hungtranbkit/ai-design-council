"""Tests for:
  - the language instruction hook (CouncilOrchestrator(..., language="vi")
    prepends a Vietnamese instruction to every role's system_prompt; ignored
    by MockProvider itself, which never reads system_prompt, but verified at
    the point where a real provider would receive it)
  - MockProvider's brief-content-based scenario dispatch (the SSH Ops Console
    scenario vs. the original QR-restaurant scenario)
"""
from __future__ import annotations

from pathlib import Path

from council.pipeline.orchestrator import LANGUAGE_INSTRUCTIONS, CouncilOrchestrator
from council.providers.mock import MockProvider

QR_BRIEF = "A minimal test brief about a QR-ordering restaurant system."
SSH_BRIEF_VI = (
    "Thiết kế một hệ thống quản lý nhiều máy chủ và máy trạm trong mạng nội bộ/lẫn remote cho một "
    "nhóm kỹ thuật nhỏ. Hệ thống cần tự phát hiện các máy/SSH target đã từng kết nối."
)


class RecordingProvider(MockProvider):
    """Wraps MockProvider but records every system_prompt handed to it."""

    def __init__(self):
        super().__init__()
        self.seen_system_prompts: list[str] = []

    def complete(self, *, role, round_num, system_prompt, user_prompt, response_model, context):
        self.seen_system_prompts.append(system_prompt)
        return super().complete(
            role=role, round_num=round_num, system_prompt=system_prompt,
            user_prompt=user_prompt, response_model=response_model, context=context,
        )


def test_no_language_set_leaves_system_prompt_unchanged():
    provider = RecordingProvider()
    orchestrator = CouncilOrchestrator(provider=provider)
    orchestrator.run_round1(QR_BRIEF)
    assert all(LANGUAGE_INSTRUCTIONS["vi"] not in p for p in provider.seen_system_prompts)


def test_vietnamese_language_prepends_instruction_to_every_system_prompt():
    provider = RecordingProvider()
    orchestrator = CouncilOrchestrator(provider=provider, language="vi")
    orchestrator.run_round1(QR_BRIEF)
    assert len(provider.seen_system_prompts) == 6
    assert all(p.startswith(LANGUAGE_INSTRUCTIONS["vi"]) for p in provider.seen_system_prompts)


def test_unknown_language_key_is_a_harmless_no_op():
    provider = RecordingProvider()
    orchestrator = CouncilOrchestrator(provider=provider, language="fr")  # not registered
    orchestrator.run_round1(QR_BRIEF)
    assert all(not p.startswith("Hãy trả lời") for p in provider.seen_system_prompts)


def test_mock_provider_defaults_to_qr_scenario_for_unrelated_briefs():
    result = CouncilOrchestrator(provider=MockProvider()).run(QR_BRIEF)
    assert "qr_signing" in {i.topic for i in result.round5.items}


def test_mock_provider_selects_ssh_ops_scenario_for_the_ssh_brief():
    result = CouncilOrchestrator(provider=MockProvider()).run(SSH_BRIEF_VI)
    topics = {i.topic for i in result.round5.items}
    assert "credential_storage" in topics
    assert "qr_signing" not in topics  # must not leak the other scenario's content

    # real, Vietnamese, brief-relevant debate - not a copy of the QR script
    assert result.round1["architect"].summary.startswith("Một service trung tâm")
    mind_changes = sum(len(d.changed_decisions) for d in result.round4.values())
    assert mind_changes >= 3
    unresolved = result.round5.by_status("unresolved")
    assert len(unresolved) >= 1


def test_ssh_ops_scenario_devils_advocate_covers_all_categories():
    result = CouncilOrchestrator(provider=MockProvider()).run(SSH_BRIEF_VI)
    assert len(result.round3.findings) >= 5
    assert result.round3.missing_categories() == set()


def test_ssh_ops_example_brief_file_exists_and_selects_the_ssh_scenario():
    brief_path = Path(__file__).resolve().parent.parent / "examples" / "ssh_ops_console.md"
    assert brief_path.exists(), "expected the SSH ops brief to be saved under examples/"
    brief_text = brief_path.read_text(encoding="utf-8")
    result = CouncilOrchestrator(provider=MockProvider()).run(brief_text)
    assert "credential_storage" in {i.topic for i in result.round5.items}
