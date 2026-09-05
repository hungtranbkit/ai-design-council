# AI Design Council (V0)

[![tests](https://github.com/hungtranbkit/ai-design-council/actions/workflows/tests.yml/badge.svg)](https://github.com/hungtranbkit/ai-design-council/actions/workflows/tests.yml)

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
network, no API key.

**`AnthropicProvider` is fully wired to call real Claude models** via the
SDK's structured-output helper (`client.messages.parse(..., output_format=<pydantic
model>)`) - Claude's response is constrained to our own pydantic schema and
`response.parsed_output` is already a validated instance, including our
custom business-rule validators (rubber-stamp rejection, "a review must take
a position", etc. - those run as normal pydantic validation on the parsed
JSON, so a real model that violates one raises a clear `ProviderError`).
Defaults to `claude-opus-5`; override with `ANTHROPIC_MODEL` in `.env`
(e.g. `claude-sonnet-5` for a cheaper run). Not exercised in CI (no key
configured there), but `tests/test_anthropic_provider.py` covers the adapter's
own logic (auth check, response mapping, error wrapping for rate
limits/auth/refusals/schema violations) against a mocked SDK client - no
network or key needed for those.

**`OpenAIProvider` is fully wired the same way**, via the Responses API's
structured-output helper (`client.responses.parse(..., text_format=<pydantic
model>)`) - `response.output_parsed` is validated the same way
(`model_validate_json` under the hood), so the same business-rule validators
apply. Defaults to `gpt-6-astra` (OpenAI's recommended flagship as of this
writing); override with `OPENAI_MODEL` (e.g. `gpt-5.4-mini` for a cheaper
run). `tests/test_openai_provider.py` covers the adapter's own logic the same
way as the Anthropic tests - mocked SDK client, no key needed.

`OllamaProvider` remains an adapter skeleton (calls a real local model,
hand-parses its JSON against the same pydantic schemas) - Ollama's
OpenAI-compatible endpoint doesn't support the same strict structured-output
mode, so it's a different (harder) problem than porting the pattern above;
not yet wired and not exercised by the test suite.

### Try a real provider

```bash
pip install -e '.[anthropic]'   # or '.[openai]'
cp .env.example .env            # fill in ANTHROPIC_API_KEY or OPENAI_API_KEY
python -m council run --brief examples/qr_restaurant.md --provider anthropic   # or --provider openai
```

Cost note: one full council run makes 25 real LLM calls (6 independent
proposals + 12 cross-reviews + 1 Devil's Advocate pass + 5 defenses + 1
consensus). At list pricing for the default flagship model on either
provider, that's on the order of a few cents to low tens of cents per run
depending on response length - `metrics.json` records the real
`tokens_in`/`tokens_out`/`estimated_cost_usd` per run so you can see exactly
what it cost.

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

## Web UI - the "meeting room"

A FastAPI app turns the same pipeline into a visual "AI design council"
meeting: a round table with the 6 roles seated around it, a live transcript
with filters, a ChatGPT Observer panel, and a Human Decision Center. It is a
**pure read/write layer on top of the existing artifacts** - it does not
duplicate or change any pipeline logic, and everything it produces
(`events.json`, `playback_state.json`, `session_config.json`,
`human_decisions.json`, `final_summary_for_chatgpt.json`) is additional files
inside the same `runs/<run_id>/` directory. A run made by the CLI shows up in
the web UI too (as an instantly-"completed" meeting); a run started from the
web UI is a completely normal run directory the CLI/tests can also read.

```bash
pip install -e '.[web]'
python -m council serve                 # http://127.0.0.1:8420
python -m council serve --port 8080     # custom port
python -m council serve --reload        # dev mode
```

Pages: **Meetings** (dashboard) → **New Council Session** (brief, provider,
roles/skills, playback toggle) → **Meeting Room** (round table + live
transcript + ChatGPT Observer) → **Human Decision Center** (Approve / Reject
/ Defer / Pending per topic, with your notes) → **Roles & Skills** (edit
which skills are attached to each role) → **Reports** → **Settings**.

Starting a session runs the *entire* 5-round pipeline immediately (the mock
provider is instant), then reveals it gradually - a random 0.5-1.5s delay per
transcript event, computed statelessly from a fixed per-run schedule (so it
survives a server restart, no background worker needed) - purely so a human
can watch it happen. Uncheck "Play back gradually" to see the finished
meeting immediately. This playback layer is entirely separate from the CLI
and does not slow it down.

### Read-only API (for an external ChatGPT/observer to poll)

```
GET  /api/meetings                              list of runs
GET  /api/meetings/{run_id}                      meta + metrics + consensus
GET  /api/meetings/{run_id}/status               current round/speaker/progress
GET  /api/meetings/{run_id}/transcript?filter=    all | arguments | risks | mind_changes | decisions
GET  /api/meetings/{run_id}/summary               ChatGPT-oriented payload (see below)
GET  /api/meetings/{run_id}/artifacts             file manifest
GET  /api/meetings/{run_id}/artifacts/file?path=  raw content of one artifact (path-traversal guarded)
GET  /api/meetings/{run_id}/decisions             current Human Decision Center state
POST /api/meetings/{run_id}/decisions             save decisions (writes human_decisions.json +
                                                   final_summary_for_chatgpt.json)
GET  /api/roles · /api/skills · /api/providers    role/skill config + provider readiness
POST /api/meetings                                start a new council session
PATCH /api/roles/{role_id}/skills                 edit a role's skill tags
```

`/summary` only reflects events *revealed so far* during playback (so an
external reader never sees "spoilers" ahead of the visible meeting) and its
`recommendation` field explicitly says "not yet reached" until round 5 is
revealed. Every payload carries `human_decision_required: true` and a note
that the user, not the council or ChatGPT, makes the final call - the web UI
repeats this in the Meeting Room and the Human Decision Center.

**Known V0 limitation:** the 6 council roles are fixed (the pipeline and
MockProvider script are written for exactly these 6 ids) - the New Session
screen's role checkboxes are therefore locked on. Skill tags *are* fully
editable (data-driven from `council/agents/skills.yaml` + a small
`council/agents/role_skill_overrides.json`, edited via the Roles & Skills
page or `PATCH /api/roles/{id}/skills`) but are informational/display
metadata in V0 - MockProvider's deterministic script doesn't read them back.
Wiring skill selection into a real LLM's prompt is a natural V1 addition
(see "Next steps" below).

### Publishing it

`python -m council serve` binds to `127.0.0.1` only. To publish, put a
reverse proxy or tunnel in front of it - e.g. a dedicated Cloudflare Tunnel
(see `~/.cloudflared/ai-design-council-config.yml` for the pattern used in
this repo's own deployment: one named tunnel per app, never the shared root
`config.yml`).

## Tests

```bash
pytest -q
```

Covers: round-1 isolation, schema validation (including rejecting rubber-stamp
reviews/critiques), mind-change detection (>=3 recorded, spanning >=2 agents),
non-overwriting artifact directories, the A/B comparison harness, the web
API (meeting creation, status/transcript/summary payloads, human decisions,
path-traversal-guarded artifact reads, non-destructive reads), and
server-rendered page smoke tests.

## Next steps for the remaining provider

Anthropic and OpenAI are both fully wired (see above). Only Ollama is left:

1. Ollama's OpenAI-compatible endpoint doesn't expose the same strict
   structured-output/JSON-schema mode the Anthropic and OpenAI adapters rely
   on, so `council/providers/ollama_provider.py` still uses the older "ask
   for JSON in the prompt, strip markdown fences, `json.loads`" approach
   (`council/providers/_llm_common.py`). Some local models (notably ones with
   native JSON-schema-constrained decoding support in Ollama, e.g. via its
   `format` parameter with a JSON schema rather than just `"json"`) can get
   closer to the same guarantee - worth revisiting once a specific target
   model is picked.
2. `pip install -e '.[web]'`'s CLI already reports Ollama as "planned" rather
   than "ready" in the New Session screen unless a local server actually
   responds at `OLLAMA_BASE_URL` (see `council/web/provider_status.py`).
3. All providers populate `tokens_in`/`tokens_out`/`estimated_cost_usd` from
   actual usage once wired - `metrics.json` already has the fields ready.
