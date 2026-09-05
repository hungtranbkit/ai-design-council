# Brief: QR Ordering for a Sit-Down Restaurant

## Context

A single independent sit-down restaurant (with an option to expand to a small
1-5 location chain later) wants a QR-code ordering system. A guest sits down,
scans a QR code on their table, and can browse the menu and place an order
directly from their phone. The system needs to serve four user roles:

- **Guest**: scans the table QR, browses the menu, places an order, sees order status.
- **Waiter**: sees incoming orders per table, can acknowledge/adjust them, handles
  guest requests (e.g. "call waiter").
- **Kitchen**: sees a prioritized ticket queue, marks items queued/cooking/ready.
- **Cashier**: sees a table's full order history at the end of the meal, takes
  payment, and closes the table.

## Known open questions (intentionally left for the design team to resolve)

- **Login vs. guest checkout**: should guests create an account, or should
  ordering be fully anonymous/guest, scoped only to the table session?
- **QR trust**: is a simple static QR code per table good enough, or does it
  need to be signed/expiring to prevent someone photographing and reusing it
  later, or from another table?
- **Realtime mechanism**: how should the kitchen display and waiter dashboard
  receive live order updates - WebSocket + Redis pub/sub, Server-Sent Events,
  or plain polling? What are the cost/complexity tradeoffs for a small
  independent restaurant versus a future multi-location chain?
- **Offline-lite**: restaurant wifi is not always reliable. What should happen
  to an in-progress order, or to the kitchen display, if connectivity drops
  mid-service?
- **Split billing**: should the system support splitting a bill by item, by
  equal share among guests, or both, in the first version?
- **Non-smartphone guests**: is there a fallback for a guest who doesn't have
  a smartphone, has a dead battery, or can't scan a QR code?

## Constraints

- Must work in a single restaurant location on day one.
- Must not require the restaurant to hire dedicated IT staff to operate it.
- Menu items must be markable "unavailable" in real time (86'd items) so the
  guest-facing menu never lets someone order something the kitchen ran out of.
- Payment must never double-charge a table.

## Deliverable expected from the design process

A concrete V1 scope: which of the open questions above are resolved (and why),
which are deferred to a later version (and why), and which need a human
business decision rather than a technical one.
