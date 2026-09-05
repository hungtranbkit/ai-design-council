"""MockProvider: a deterministic, offline simulation of a real multi-LLM debate.

This is not a random text generator and it is not an echo of the input. It
encodes an actual (hand-authored) simulated disagreement between six personas
about a QR-ordering restaurant system, keyed off the *contested topics* that
show up in examples/qr_restaurant.md:

    - guest checkout vs required login
    - signed/expiring QR tokens vs static QR
    - realtime transport: Redis+WebSocket vs SSE vs polling
    - offline-lite handling for flaky restaurant wifi
    - split billing (by item vs equal share)
    - capturing a guest phone number for marketing/notifications

Round 1 answers never look at each other (enforced by the orchestrator, not by
this class - see pipeline/round1.py). Round 2 onward, this class reads the
structured `context` dict the orchestrator hands it (prior rounds' parsed
models, already validated) to decide what a given persona would say *given
what it has just learned*, including reversing itself on >=1 topic when the
critique is strong enough - which is the whole point of the exercise.
"""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from council.pipeline.schemas import (
    ChangedDecision,
    ConsensusItem,
    ConsensusReport,
    CrossReview,
    Defense,
    DefenseResponse,
    DevilsAdvocateFinding,
    DevilsAdvocateReport,
    Proposal,
    SoloDesign,
)
from council.providers.base import Provider, ProviderResponse

# ---------------------------------------------------------------------------
# Round 1: independent proposals (no visibility into other agents)
# ---------------------------------------------------------------------------

_ROUND1_PRODUCT_BA = Proposal(
    role="product_ba",
    summary=(
        "Guests scan a per-table QR to open a menu and order without creating an "
        "account; waiters get a live ticket queue; kitchen gets prioritized order "
        "tickets; cashier reconciles and closes the table."
    ),
    requirements=[
        "Guest can view menu and place an order by scanning a table QR code",
        "Waiter can see and acknowledge incoming orders per table",
        "Kitchen sees a ticket queue with item-level status (queued/cooking/ready)",
        "Cashier can view a table's full order history and take payment",
        "Menu items can be marked unavailable in real time (86'd items)",
    ],
    decisions=[
        "No login required for guests - anonymous ordering scoped to a table session, "
        "to remove signup friction and maximize order conversion",
        "Split billing supported by item only in V1 (equal-share split deferred to V2)",
    ],
    edge_cases=[
        "Guest places an order after the waiter has already closed/settled the table",
        "Two phones at the same table submit overlapping orders",
    ],
    risks=[
        "Fraudulent or spoofed orders if the QR/table link can be reused or shared",
        "Abandoned carts inflate kitchen queue if orders aren't confirmed",
    ],
    assumptions=["Guests carry a smartphone with a working camera and mobile data/wifi"],
)

_ROUND1_UX_DESIGNER = Proposal(
    role="ux_designer",
    summary=(
        "A 3-tap ordering flow (scan -> browse -> order) with large food photography, "
        "live order-status for the guest, and no account creation."
    ),
    requirements=[
        "Menu browsing with photos and dietary tags, optimized for one-handed phone use",
        "Guest sees live status of their own order (received/cooking/ready)",
        "Ordering flow completes in 3 taps or fewer from QR scan to submit",
        "Optional guest phone number field to receive an SMS when the order is ready",
    ],
    decisions=[
        "Agrees with no-login guest checkout - any login wall would tank conversion",
        "Order-status should update live on the guest's screen without a manual refresh",
    ],
    edge_cases=[
        "QR scanning fails in low restaurant lighting - needs a manual table-code fallback",
        "Customers without a smartphone (or a dead phone) have no ordering path at all",
    ],
    risks=["Menu photos/prices going stale if not synced with the kitchen system"],
    assumptions=["Every customer is comfortable scanning a QR code with their own phone"],
)

_ROUND1_ARCHITECT = Proposal(
    role="architect",
    summary=(
        "Three services - ordering-service, kitchen-display, cashier-service - sharing "
        "a Postgres store, fanned out over WebSocket via Redis pub/sub for realtime "
        "kitchen/waiter updates."
    ),
    requirements=[
        "ordering-service: table sessions, menu, order submission",
        "kitchen-display: realtime ticket queue with status transitions",
        "cashier-service: order aggregation, payment, table close-out",
    ],
    decisions=[
        "Realtime fan-out via WebSocket connections, backed by Redis pub/sub so any "
        "ordering-service instance can push to any connected kitchen-display/waiter client",
        "Single shared Postgres database across services for V1 simplicity",
    ],
    edge_cases=["Kitchen display must reconnect and resync its queue after a network blip"],
    risks=["Redis becomes a single point of failure for all realtime updates"],
    assumptions=["The venue has a target of one Redis instance being acceptable ops overhead"],
)

_ROUND1_BUSINESS_CRITIC = Proposal(
    role="business_critic",
    summary=(
        "Target customer is a single independent restaurant or a small 1-5 location "
        "chain; the system must be cheap to run and easy to justify commercially."
    ),
    requirements=[
        "Total infra cost per venue should be justifiable against the labor it saves",
        "Onboarding a new venue (menu setup, table QR generation) must take under a day",
    ],
    decisions=[
        "Recommend the cheapest realtime mechanism that meets the UX bar - reject "
        "always defaulting to Redis+WebSocket infra before the cost is justified",
    ],
    edge_cases=["A venue churns mid-month - billing/infra must scale down, not just up"],
    risks=[
        "No pricing/monetization model has been proposed yet for a system with real "
        "infra cost per venue",
        "Infra cost could exceed what a small independent restaurant will pay for this",
    ],
    assumptions=["Target buyer is price-sensitive and evaluates against a free paper-ticket status quo"],
)

_ROUND1_QA_SECURITY = Proposal(
    role="qa_security",
    summary=(
        "Security and correctness requirements for a system that lets anonymous "
        "guests place orders and cashiers take payment against a shared table link."
    ),
    requirements=[
        "All guest input (order contents, quantities) must be server-validated",
        "Payment actions must be idempotent to prevent double-charging a table",
        "Rate limiting on order submission per table session",
    ],
    decisions=[
        "QR codes must be signed (HMAC) and time-limited - a plain static QR per table "
        "is a critical vulnerability: anyone who photographs or reprints it can place "
        "orders or view another guest's session indefinitely",
    ],
    edge_cases=[
        "An expired QR is scanned and still accepted by a lenient client",
        "A QR code photographed and shared on social media is scanned by someone not "
        "physically at the venue",
    ],
    risks=[
        "Combining anonymous no-login checkout with an unsigned, non-expiring QR is a "
        "compounding risk: there is no identity and no token to invalidate",
        "Payment double-charge on cashier retry without an idempotency key",
    ],
)

_ROUND1_DEVILS_ADVOCATE = Proposal(
    role="devils_advocate",
    summary=(
        "Independent skeptical take: the proposal set (not yet seen by this agent in "
        "detail) likely underweights operational failure modes common in real "
        "restaurants - flaky wifi, and non-smartphone customers - before it even "
        "reaches security review."
    ),
    requirements=[
        "The system must degrade gracefully when venue wifi drops mid-service",
        "There must be a non-app fallback path for guests without a working smartphone",
    ],
    decisions=[
        "Do not assume 100% smartphone coverage or 100% wifi uptime as a starting "
        "premise for V1 scope",
    ],
    edge_cases=["Kitchen loses connectivity mid-rush and cannot see new tickets at all"],
    risks=["Nobody has proposed an offline-lite story yet for order capture during an outage"],
    open_questions=["Should V1 explicitly scope out or explicitly design for offline operation?"],
)

_ROUND1 = {
    "product_ba": _ROUND1_PRODUCT_BA,
    "ux_designer": _ROUND1_UX_DESIGNER,
    "architect": _ROUND1_ARCHITECT,
    "business_critic": _ROUND1_BUSINESS_CRITIC,
    "qa_security": _ROUND1_QA_SECURITY,
    "devils_advocate": _ROUND1_DEVILS_ADVOCATE,
}

# ---------------------------------------------------------------------------
# Round 2: cross review (reviewer_role -> target_role -> CrossReview)
# ---------------------------------------------------------------------------

_ROUND2: dict[str, dict[str, CrossReview]] = {
    "product_ba": {
        "architect": CrossReview(
            reviewer_role="product_ba",
            target_role="architect",
            agree=["Three-service split matches the product's user roles cleanly"],
            disagree=[],
            missing_requirements=["No mention of what happens to an in-flight order if a service restarts"],
            risks=[],
            proposed_changes=["Document order-submission durability guarantees across service restarts"],
        ),
        "qa_security": CrossReview(
            reviewer_role="product_ba",
            target_role="qa_security",
            agree=["Signed QR is reasonable and shouldn't materially hurt the ordering flow"],
            disagree=[],
            missing_requirements=[],
            risks=[],
            proposed_changes=["Confirm signed QR can still be generated per-table without per-guest login"],
        ),
    },
    "ux_designer": {
        "product_ba": CrossReview(
            reviewer_role="ux_designer",
            target_role="product_ba",
            agree=["No-login guest checkout is the right default"],
            disagree=["Item-only split billing may frustrate large groups who want to split evenly"],
            missing_requirements=["Equal-share split as at least an option, even if item-split is the default"],
            risks=[],
            proposed_changes=["Add an equal-share split calculator alongside item-level split"],
        ),
        "architect": CrossReview(
            reviewer_role="ux_designer",
            target_role="architect",
            agree=["Realtime push is necessary for the guest order-status requirement"],
            disagree=[],
            missing_requirements=["No fallback ordering path described for guests without a smartphone"],
            risks=[],
            proposed_changes=["Architecture should not assume every guest is an app/websocket client"],
        ),
    },
    "architect": {
        "ux_designer": CrossReview(
            reviewer_role="architect",
            target_role="ux_designer",
            agree=["3-tap flow is a good design constraint"],
            disagree=["Assuming universal smartphone/QR capability is not safe for V1 architecture scope"],
            missing_requirements=["A defined non-smartphone fallback so backend doesn't special-case it late"],
            risks=[],
            proposed_changes=["UX spec should define the fallback flow, not just flag it as a risk"],
        ),
        "business_critic": CrossReview(
            reviewer_role="architect",
            target_role="business_critic",
            agree=["Cost is a legitimate constraint on infra choice"],
            disagree=["Rejecting Redis+WebSocket outright ignores that it directly serves the UX realtime requirement"],
            missing_requirements=[],
            risks=[],
            proposed_changes=["Propose a cost/latency comparison instead of a blanket rejection"],
        ),
    },
    "business_critic": {
        "architect": CrossReview(
            reviewer_role="business_critic",
            target_role="architect",
            agree=["Service boundaries are reasonable"],
            disagree=[
                "Redis + WebSocket fan-out is meaningful added infra (a managed Redis instance, "
                "connection-state ops) for a segment of 1-5 location independent restaurants that "
                "does not need this at launch scale",
            ],
            missing_requirements=["A lighter-weight realtime option (SSE or short-poll) evaluated as the V1 default"],
            risks=["Ongoing Redis hosting/ops cost eats into a thin per-venue margin"],
            proposed_changes=["Default to SSE/polling for V1; gate Redis+WebSocket behind a concurrency trigger"],
        ),
        "product_ba": CrossReview(
            reviewer_role="business_critic",
            target_role="product_ba",
            agree=["Anonymous guest checkout keeps conversion high"],
            disagree=[],
            missing_requirements=["No monetization/pricing model tied to the feature set"],
            risks=["Building infra-heavy features (realtime, signed QR) with no validated willingness-to-pay"],
            proposed_changes=["Attach a lightweight pricing hypothesis to the V1 scope before further build-out"],
        ),
    },
    "qa_security": {
        "product_ba": CrossReview(
            reviewer_role="qa_security",
            target_role="product_ba",
            agree=["Anonymous, low-friction checkout is fine as a UX default"],
            disagree=[
                "Treating unsigned/static QR as an acceptable default is not fine: combined with no "
                "login, a shared or reprinted QR gives an attacker an indefinite ordering/viewing channel",
            ],
            missing_requirements=["QR signing + expiry must be a stated product requirement, not just an infra detail"],
            risks=["Spoofed/replayed QR codes enabling order fraud or session snooping"],
            proposed_changes=["Add 'QR tokens are signed and short-lived' as an explicit product requirement"],
        ),
        "architect": CrossReview(
            reviewer_role="qa_security",
            target_role="architect",
            agree=["Service split is reasonable from a blast-radius perspective"],
            disagree=["No mention of authenticating the realtime channel itself (WebSocket/SSE connections)"],
            missing_requirements=["Auth/signing on the realtime transport, not only on initial QR scan"],
            risks=["An unauthenticated realtime channel could leak another table's order data"],
            proposed_changes=["Require the realtime channel to carry the same signed table token as the QR"],
        ),
    },
    "devils_advocate": {
        "architect": CrossReview(
            reviewer_role="devils_advocate",
            target_role="architect",
            agree=["Clear service boundaries"],
            disagree=["Zero mention of what kitchen-display does when it loses its realtime connection"],
            missing_requirements=["An explicit offline/degraded-mode behavior for kitchen-display"],
            risks=["A wifi blip during dinner rush silently drops new tickets with no operator-visible alarm"],
            proposed_changes=["Define an offline-lite mode: local queue + resync, not just 'reconnect'"],
        ),
        "ux_designer": CrossReview(
            reviewer_role="devils_advocate",
            target_role="ux_designer",
            agree=["3-tap flow and live status are good UX goals"],
            disagree=["Flagging 'no smartphone' as a risk, then not requiring a fallback, leaves a customer segment with literally no way to order"],
            missing_requirements=["A concrete non-smartphone ordering fallback (e.g. printed menu + call-waiter)"],
            risks=[],
            proposed_changes=["Promote the non-smartphone fallback from 'risk noted' to a required flow"],
        ),
    },
}

# ---------------------------------------------------------------------------
# Round 3: Devil's Advocate - reads everything, must not rubber-stamp
# ---------------------------------------------------------------------------

_ROUND3_FINDINGS = [
    DevilsAdvocateFinding(
        category="security",
        description=(
            "product_ba's original 'no login, static QR is fine' stance combined with "
            "qa_security's signed-QR requirement means the two proposals directly "
            "contradict each other and must be reconciled, not just noted side by side"
        ),
        target_role="product_ba",
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="unnecessary_complexity",
        description=(
            "architect's Redis+WebSocket fan-out is being proposed before any traffic "
            "estimate exists for the actual target segment (1-5 location independent "
            "restaurants); this is solving a scale problem the business may never have"
        ),
        target_role="architect",
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="missing_business_case",
        description=(
            "business_critic correctly flagged the missing pricing model, but nobody's "
            "V1 requirement set actually depends on an answer - the team can keep adding "
            "infra-heavy features indefinitely with no monetization checkpoint forcing a stop"
        ),
        target_role="business_critic",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="scalability",
        description=(
            "architect's kitchen-display reconnect handling is described as 'reconnect and "
            "resync' with no definition of what happens to tickets that arrived while "
            "disconnected - this is a data-loss bug waiting to happen at real dinner-rush volume"
        ),
        target_role="architect",
        severity="high",
    ),
    DevilsAdvocateFinding(
        category="ux",
        description=(
            "ux_designer's flow assumes every guest owns a working smartphone; this is a "
            "hidden assumption that silently excludes a real customer segment (older "
            "guests, dead batteries, guests who forgot a phone) from ordering at all"
        ),
        target_role="ux_designer",
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="hidden_assumption",
        description=(
            "every proposal assumes venue wifi is reliable enough for realtime sync during "
            "service; none of the six proposals states this as an assumption to validate, "
            "it is just silently baked into the architecture"
        ),
        target_role=None,
        severity="medium",
    ),
    DevilsAdvocateFinding(
        category="operations",
        description=(
            "there is no offline-lite story anywhere in round 1: if venue wifi drops "
            "mid-service, kitchen-display and the ordering flow both have undefined "
            "behavior rather than a designed degraded mode"
        ),
        target_role="architect",
        severity="high",
    ),
]


def _round3_devils_advocate() -> DevilsAdvocateReport:
    return DevilsAdvocateReport(findings=list(_ROUND3_FINDINGS))


# ---------------------------------------------------------------------------
# Round 4: Defense / Revision - this is where mind changes get recorded
# ---------------------------------------------------------------------------


def _defense_product_ba() -> Defense:
    return Defense(
        role="product_ba",
        responses=[
            DefenseResponse(
                critique_source="qa_security (round2)",
                critique_summary="Static/unsigned QR + no login is a compounding fraud/replay risk",
                stance="revise",
                rationale=(
                    "Agreed - the security argument is concrete (replay via photographed QR) and "
                    "signing costs nothing in guest-facing friction since it's transparent to the scan flow"
                ),
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="product_ba and qa_security proposals directly contradict each other on QR trust",
                stance="revise",
                rationale="Resolved by adopting qa_security's signed/short-lived QR token as the product requirement",
            ),
            DefenseResponse(
                critique_source="ux_designer (round2)",
                critique_summary="Item-only split billing may frustrate groups wanting an equal split",
                stance="revise",
                rationale="Low cost to add as a client-side convenience calculator; keep item-split as source of truth",
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="qr_signing",
                old_decision="A static QR per table is sufficient; no login required for guests",
                new_decision=(
                    "No user login is still required, but the table QR must encode a signed, "
                    "short-lived token (HMAC + expiry) that the ordering session validates on scan"
                ),
                reason=(
                    "qa_security showed static QR + anonymous checkout has no invalidation "
                    "mechanism at all - a photographed/reprinted QR works forever"
                ),
                triggered_by="qa_security (round2), devils_advocate (round3)",
            ),
            ChangedDecision(
                topic="split_billing",
                old_decision="Support split-by-item only in V1; equal-share split deferred to V2",
                new_decision="Ship both split-by-item and a simple equal-share calculator in V1",
                reason="ux_designer showed group parties commonly want equal split and the cost to add it now is low",
                triggered_by="ux_designer (round2)",
            ),
        ],
        final_decisions=[
            "No account/login required for guests",
            "Table QR encodes a signed, short-lived token validated at scan time",
            "Split-by-item is the default; equal-share split is offered as an alternative in V1",
        ],
    )


def _defense_ux_designer() -> Defense:
    return Defense(
        role="ux_designer",
        responses=[
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="Design silently assumes every guest has a working smartphone",
                stance="revise",
                rationale=(
                    "Fair - this was a flagged risk, not a designed fallback. A customer segment "
                    "with no ordering path at all is a real gap, not an acceptable edge case"
                ),
            ),
            DefenseResponse(
                critique_source="architect (round2)",
                critique_summary="Architecture shouldn't have to special-case a fallback flow late",
                stance="defend",
                rationale=(
                    "Agree the fallback needs to be designed now; keeping the primary flow app-only "
                    "and adding a parallel manual path is simpler than architect fears"
                ),
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="no_smartphone_fallback",
                old_decision="No fallback specified; smartphone + QR assumed for all guests",
                new_decision=(
                    "Add a required fallback: a printed physical menu plus a 'call waiter' button "
                    "at the table for guests without a working smartphone; waiter manually enters "
                    "their order into the same ordering-service"
                ),
                reason="devils_advocate showed this silently excludes a real, non-trivial customer segment",
                triggered_by="devils_advocate (round3)",
            ),
        ],
        final_decisions=[
            "Primary flow: scan QR -> browse -> order in <=3 taps, with live order status",
            "Fallback flow: printed menu + call-waiter button, waiter enters the order manually",
            "Optional guest phone number field remains opt-in for order-ready SMS notification",
        ],
    )


def _defense_architect() -> Defense:
    return Defense(
        role="architect",
        responses=[
            DefenseResponse(
                critique_source="business_critic (round2)",
                critique_summary="Redis+WebSocket is meaningful added infra/ops cost for the target segment",
                stance="revise",
                rationale=(
                    "Reasonable for V1 - the realtime UX requirement can be met with SSE against the "
                    "existing Postgres store, at a fraction of the operational surface"
                ),
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="Redis+WebSocket solves a scale problem the business may not have yet",
                stance="revise",
                rationale="Accepted - defer Redis+WebSocket behind a measured concurrency trigger instead of shipping it by default",
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="No offline-lite story; reconnect/resync behavior for in-flight tickets is undefined",
                stance="revise",
                rationale="This is a real gap; defining a local queue + idempotent resync closes it",
            ),
            DefenseResponse(
                critique_source="qa_security (round2)",
                critique_summary="The realtime channel itself isn't authenticated, only the initial QR scan",
                stance="revise",
                rationale="The realtime channel will carry the same signed table token product_ba is now issuing",
            ),
        ],
        changed_decisions=[
            ChangedDecision(
                topic="realtime_transport",
                old_decision="WebSocket fan-out backed by Redis pub/sub for all realtime updates",
                new_decision=(
                    "V1 default is Server-Sent Events (SSE) reading from a Postgres-backed outbox "
                    "table, with no Redis dependency; Redis+WebSocket is revisited only if a venue "
                    "crosses a defined concurrency threshold (e.g. >20 simultaneously open tables)"
                ),
                reason=(
                    "business_critic and devils_advocate both showed this infra was being added "
                    "ahead of any evidence the target segment needs it"
                ),
                triggered_by="business_critic (round2), devils_advocate (round3)",
            ),
            ChangedDecision(
                topic="offline_lite",
                old_decision="Not addressed - reconnect handling left undefined",
                new_decision=(
                    "kitchen-display caches its last known ticket queue locally and the "
                    "ordering-service queues submitted orders locally with an idempotency key "
                    "when connectivity drops, syncing both once the connection returns"
                ),
                reason="devils_advocate showed this was a silent data-loss risk at real dinner-rush volume",
                triggered_by="devils_advocate (round3)",
            ),
        ],
        final_decisions=[
            "ordering-service, kitchen-display, cashier-service over a single shared Postgres store",
            "Realtime updates via SSE + Postgres outbox in V1; Redis+WebSocket gated behind a concurrency trigger",
            "Realtime channel requires the same signed table token issued at QR scan",
            "Offline-lite: local queue with idempotency key on both kitchen-display and ordering-service, resync on reconnect",
        ],
    )


def _defense_business_critic() -> Defense:
    return Defense(
        role="business_critic",
        responses=[
            DefenseResponse(
                critique_source="architect (round2)",
                critique_summary="Rejecting Redis+WebSocket outright ignored that it serves a real UX requirement",
                stance="partially_accept",
                rationale=(
                    "Fair that a blanket rejection wasn't constructive; the concrete proposal is a "
                    "cost-gated escalation path (SSE by default, Redis+WebSocket past a concurrency "
                    "threshold), which architect has now adopted"
                ),
            ),
            DefenseResponse(
                critique_source="devils_advocate (round3)",
                critique_summary="No monetization checkpoint constrains ongoing infra-heavy feature growth",
                stance="defend",
                rationale=(
                    "Standing by this: it's a governance gap, not something this round's technical "
                    "revisions fix. Recorded as an unresolved item for the human decision-maker."
                ),
            ),
        ],
        changed_decisions=[],
        final_decisions=[
            "Infra choices must default to the cheapest option that meets the UX bar, with cost-based "
            "escalation triggers instead of upfront heavy infra",
            "A pricing/monetization checkpoint is required before further infra-heavy features are added "
            "(escalated to Round 5 as unresolved)",
        ],
    )


def _defense_qa_security() -> Defense:
    return Defense(
        role="qa_security",
        responses=[
            DefenseResponse(
                critique_source="product_ba (round2)",
                critique_summary="Confirms signed QR can be generated per-table without per-guest login",
                stance="defend",
                rationale="Correct and compatible - signing is per-table-session, not per-user, so no account system is needed",
            ),
        ],
        changed_decisions=[],
        final_decisions=[
            "Table QR encodes a signed, short-lived (HMAC + expiry) token",
            "Realtime channel and payment actions both validate the same signed table token",
            "Payment actions are idempotent; order submission is rate-limited per table session",
        ],
    )


_ROUND4 = {
    "product_ba": _defense_product_ba,
    "ux_designer": _defense_ux_designer,
    "architect": _defense_architect,
    "business_critic": _defense_business_critic,
    "qa_security": _defense_qa_security,
}

# ---------------------------------------------------------------------------
# Round 5: Consensus / Moderator - synthesis, not majority vote
# ---------------------------------------------------------------------------


def _round5_consensus() -> ConsensusReport:
    items = [
        ConsensusItem(
            topic="qr_signing",
            status="accepted",
            decision="Table QR encodes a signed, short-lived (HMAC + expiry) token; no user login required",
            rationale=(
                "Not decided by majority - it was a 1-vs-1 disagreement (product_ba vs qa_security) "
                "resolved because qa_security's evidence (indefinite replay via a photographed/reprinted "
                "static QR) was concrete and product_ba's revision preserves the no-login UX goal at "
                "effectively zero added guest friction"
            ),
            evidence=[
                "qa_security round1: static QR + no login has no invalidation mechanism",
                "product_ba round4: revised to signed/short-lived QR, no login preserved",
                "devils_advocate round3: flagged the direct contradiction forcing resolution",
            ],
        ),
        ConsensusItem(
            topic="realtime_transport",
            status="accepted",
            decision="SSE + Postgres outbox by default in V1; Redis+WebSocket gated behind a defined concurrency trigger",
            rationale=(
                "architect initially had the strongest technical case for Redis+WebSocket, but "
                "business_critic and devils_advocate independently showed the cost/complexity was "
                "being paid ahead of any evidence of need for the actual target segment; architect's "
                "own revision (not a vote against them) is what settled this"
            ),
            evidence=[
                "business_critic round2: Redis ops cost vs a 1-5 location segment margin",
                "devils_advocate round3: 'solving a scale problem the business may never have'",
                "architect round4: revised to SSE-default with a concrete concurrency trigger",
            ],
        ),
        ConsensusItem(
            topic="offline_lite",
            status="accepted",
            decision=(
                "kitchen-display and ordering-service both keep a local queue with idempotency keys "
                "during a connectivity drop and resync on reconnect"
            ),
            rationale=(
                "Nobody proposed this in round 1 - it surfaced only because devils_advocate treated "
                "'reconnect and resync' as underspecified rather than accepting it at face value; "
                "accepted because architect's round4 answer is concrete and testable, not just a promise"
            ),
            evidence=[
                "devils_advocate round3: reconnect handling silently undefined for in-flight tickets",
                "architect round4: concrete local-queue + idempotency-key design",
            ],
        ),
        ConsensusItem(
            topic="non_smartphone_fallback",
            status="accepted",
            decision="Printed menu + call-waiter button fallback, waiter manually enters the order",
            rationale=(
                "ux_designer's own round1 proposal already named this as a risk without a fix; "
                "accepted once devils_advocate forced it from 'noted risk' to a required flow, and "
                "ux_designer's round4 answer is a real designed flow rather than a vague mitigation"
            ),
            evidence=[
                "ux_designer round1: flagged as risk, not designed",
                "devils_advocate round3: 'no way to order' gap for a real customer segment",
                "ux_designer round4: concrete printed-menu + call-waiter flow",
            ],
        ),
        ConsensusItem(
            topic="split_billing",
            status="accepted",
            decision="Ship both split-by-item (default) and equal-share split in V1",
            rationale="Low-disagreement, low-cost addition once ux_designer raised it; product_ba agreed in round4 with no real counter-argument",
            evidence=["ux_designer round2: groups want equal split", "product_ba round4: added as V1 scope"],
        ),
        ConsensusItem(
            topic="guest_phone_number_capture",
            status="unresolved",
            decision=None,
            rationale=(
                "This is a genuine unresolved business/policy trade-off, not a technical one: "
                "business_critic wants a monetization/CRM hook, ux_designer wants it opt-in only to "
                "protect conversion, and qa_security has an open question about privacy/PII handling "
                "obligations that depend on the venue's jurisdiction - none of that is something the "
                "council can resolve on the council's own authority. Escalated to the human decision-maker."
            ),
            evidence=[
                "ux_designer round1: proposed as opt-in only",
                "business_critic round4: flagged monetization checkpoint as still open",
                "qa_security: PII handling obligations depend on jurisdiction, out of council scope",
            ],
            dissent="business_critic would prefer capture be encouraged more assertively for CRM value; ux_designer opposes any friction added to the opt-in prompt",
        ),
        ConsensusItem(
            topic="monetization_checkpoint",
            status="unresolved",
            decision=None,
            rationale=(
                "business_critic maintained through round4 that no pricing/monetization model "
                "constrains further infra-heavy feature growth. This is a strategic business decision "
                "outside the council's mandate to resolve technically - it is recorded as-is for the "
                "human decision-maker rather than forced to a false resolution"
            ),
            evidence=["business_critic round1 and round4: flagged and never withdrawn"],
            dissent="No other role directly disputes this; it remains unresolved because nobody has the authority or data to close it, not because of disagreement",
        ),
    ]
    summary = (
        "5 topics reached accepted decisions through evidence-based resolution (not majority vote); "
        "2 topics remain genuinely unresolved and require a human business decision."
    )
    return ConsensusReport(items=items, summary=summary)


# ---------------------------------------------------------------------------
# Single-agent baseline (A/B harness) - deliberately misses what only debate surfaces
# ---------------------------------------------------------------------------

_SOLO_DESIGN = SoloDesign(
    summary=(
        "Guests scan a per-table QR to browse the menu and order without an account; "
        "a WebSocket connection pushes live status to guest, waiter, and kitchen; "
        "cashier reconciles and closes the table at the end of service."
    ),
    requirements=[
        "Guest can view menu and place an order by scanning a table QR code",
        "Waiter can see and acknowledge incoming orders per table",
        "Kitchen sees a ticket queue with item-level status",
        "Cashier can view a table's order history and take payment",
        "Guest sees live order status on their own screen",
    ],
    decisions=[
        "No login required for guests; QR is a simple static per-table code",
        "Realtime updates over WebSocket",
        "Split billing by item only",
    ],
    edge_cases=[
        "Guest places an order after the table has already been closed",
        "Kitchen display needs to reconnect after a network blip",
    ],
    risks=["Menu photos/prices going stale if not synced with the kitchen system"],
    open_questions=[
        "Should there be a way to notify the guest when their order is ready?",
    ],
)


class MockProvider(Provider):
    """Deterministic offline provider implementing the interface in base.Provider."""

    name = "mock"

    def complete(
        self,
        *,
        role: str,
        round_num: int,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        context: dict[str, Any],
    ) -> ProviderResponse:
        start = time.perf_counter()
        parsed = self._dispatch(role=role, round_num=round_num, response_model=response_model, context=context)
        elapsed = time.perf_counter() - start
        raw = parsed.model_dump_json(indent=2)
        # Deterministic pseudo token accounting so metrics/cost fields are populated
        # end-to-end even though no real LLM call happened.
        tokens_in = max(1, len(system_prompt + user_prompt) // 4)
        tokens_out = max(1, len(raw) // 4)
        return ProviderResponse(
            parsed=parsed,
            raw_text=raw,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            estimated_cost_usd=0.0,  # mock provider: free, no real API call
            latency_seconds=elapsed,
            provider_name=self.name,
            metadata={"role": role, "round": round_num},
        )

    def _dispatch(
        self,
        *,
        role: str,
        round_num: int,
        response_model: type[BaseModel],
        context: dict[str, Any],
    ) -> BaseModel:
        if response_model is SoloDesign:
            return _SOLO_DESIGN.model_copy(deep=True)

        if round_num == 1:
            if role not in _ROUND1:
                raise KeyError(f"MockProvider has no round-1 script for role '{role}'")
            return _ROUND1[role].model_copy(deep=True)

        if round_num == 2:
            reviewer = role
            target = context.get("target_role")
            table = _ROUND2.get(reviewer, {})
            if target not in table:
                raise KeyError(f"MockProvider has no round-2 script for reviewer='{reviewer}' target='{target}'")
            return table[target].model_copy(deep=True)

        if round_num == 3:
            return _round3_devils_advocate()

        if round_num == 4:
            if role not in _ROUND4:
                raise KeyError(f"MockProvider has no round-4 script for role '{role}'")
            return _ROUND4[role]()

        if round_num == 5:
            return _round5_consensus()

        raise ValueError(f"MockProvider does not support round {round_num}")
