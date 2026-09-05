# AI Design Council (V0)

A standalone multi-agent debate pipeline: six AI agent personas independently
propose a design for a software brief, cross-review each other, get subjected
to a mandatory Devil's Advocate critique, defend or revise their positions,
and have a neutral moderator synthesize a final report - **for a human (or
ChatGPT/you) to read and decide on**. The council never has the final word.

This is **not** integrated with PromptFlow or ProjectFlow. It is a fully
independent project, deliberately kept filesystem-artifact-based rather than
a service with a database, so every intermediate step is a plain JSON/Markdown
file you can open and audit.

## Why

Most "multi-agent" demos either echo the same answer six ways, or produce
consensus theater (everyone politely agrees). This project's MockProvider is a
hand-authored, deterministic simulation of a **real disagreement** - about a
QR-ordering restaurant system - where agents start from genuinely different
positions, get challenged with concrete evidence, and some of them **change
their mind** (recorded explicitly, with the old decision, new decision,
reason, and what triggered it). Others hold their ground. A moderator then
resolves each contested topic with evidence and rationale - not a vote count -
and explicitly marks some items **unresolved** because they're business/policy
calls outside the council's authority.

## The 5 rounds

1. **Independent proposals** - each of 6 agents proposes a design with zero
   visibility into any other agent's output (structurally enforced, see
   `tests/test_isolation.py`).
2. **Cross review** - each agent reads a fixed subset of other agents'
   proposals and returns a structured review (agree / disagree /
   missing_requirements / risks / proposed_changes). A review that only
   agrees is rejected by schema validation.
3. **Devil's Advocate** - reads every proposal and every review, and must
   raise at least 5 findings covering hidden assumptions, unnecessary
   complexity, missing business cases, scalability, UX, security, and
   operations. "Looks good" and equivalents are rejected by schema validation.
4. **Defense / Revision** - each of the 5 debating agents (not the Devil's
   Advocate) responds to every critique it received: defend, revise, or
   partially accept. Revisions are recorded as explicit `changed_decisions`.
5. **Consensus / Moderator** - a neutral 7th role (no stake in any proposal)
   synthesizes accepted / rejected / unresolved decisions, each with a
   rationale and evidence pulled from the transcript - never a plain vote
   count - plus recorded dissent where relevant.

## The 6 council roles (+ moderator)

Product/BA, UX Designer, Architect, Business Critic, QA+Security, Devil's
Advocate - each defined in `council/agents/roles/*.yaml` (persona, focus
areas, per-round instructions). Edit those files to change how an agent
argues; no code changes needed.

## Providers

`council/providers/base.py` defines the interface. `MockProvider` (the only
one required for tests) is a fully offline, deterministic simulation - no
network, no API key. `OpenAIProvider`, `AnthropicProvider`, and
`OllamaProvider` are working adapter skeletons that call a real LLM and
validate its JSON output against the same pydantic schemas; they need a real
key (or a running Ollama server) and are not exercised by the test suite.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Requires Python 3.12+. Copy `.env.example` to `.env` only if you plan to wire
up a real provider - `--provider mock` needs none of it.

## Usage

```bash
# Run the full 5-round council pipeline against a brief
python -m council run --brief examples/qr_restaurant.md --provider mock

# Run the single-agent baseline instead (no debate)
python -m council run --brief examples/qr_restaurant.md --provider mock --mode single-agent

# Run BOTH and produce an A/B comparison
python -m council compare --brief examples/qr_restaurant.md --provider mock

# Print a previous run's final report
python -m council report <run_id>
```

Every `run` writes a self-contained, never-overwritten directory:

```
runs/<run_id>/
  meta.json
  brief.md
  agents/round1/<role>.json           # independent proposals
  agents/round2/<reviewer>__reviews__<target>.json
  agents/round4/<role>.json           # defense/revision, incl. changed_decisions
  debate/round3_devils_advocate.json
  consensus.json                      # round 5 synthesis
  metrics.json
  final_report.md                     # <- read this one
```

`compare` additionally writes `runs/comparisons/<compare_id>/{comparison.json,comparison.md}`.

## Tests

```bash
pytest -q
```

Covers: round-1 isolation, schema validation (including rejecting rubber-stamp
reviews/critiques), mind-change detection (>=3 recorded, spanning >=2 agents),
non-overwriting artifact directories, and the A/B comparison harness.

## Next steps to wire up a real provider

1. `pip install -e '.[anthropic]'` (or `[openai]`), fill in `.env` from
   `.env.example`.
2. `python -m council run --brief examples/qr_restaurant.md --provider anthropic`
3. Expect some early runs to fail schema validation as a real model's JSON
   drifts from the pydantic schema - `council/providers/_llm_common.py`
   already strips markdown fences and raises a clear `ProviderError` with the
   raw text on failure; tightening the JSON-schema instruction or adding a
   repair-retry loop is the natural next increment, deliberately left out of
   V0 to keep the pipeline itself simple to audit first.
4. Real providers will also populate `tokens_in`/`tokens_out`/`estimated_cost_usd`
   from actual usage instead of the mock's char-count proxy - `metrics.json`
   already has the fields ready.
