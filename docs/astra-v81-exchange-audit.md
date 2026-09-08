# Astra v8.1 exchange funnel audit

2026-09-07. Manual retrospective audit of both completed, clean, admitted
`gpt-6-astra-v8-revised-20260907` worlds, seeds 11/41. The database verified
successfully. This does not rerun the v6 judge or alter frozen labels or scores.
[Machine-readable episodes, transfer actions, hashes and ledger lines](astra-v81-exchange-audit.json)
make the judgment boundaries reviewable.

## Finding

Astra demonstrates completed informal procurement and useful cooperative
follow-through, but this evidence does not establish that it solved low market
conversion. Most identified goods-procurement solicitations never gained an
evidenced commitment. Its stronger story is local construction and upkeep,
including adaptations to physical and permission failures. The previous narrative
should not be read as evidence of a large hidden volume of completed trades.

## Denominators

Read all 268 emitted messages, all 13 successful gift-action transfers, failed
handoffs and messages, construction contributions, access grants, and the raw
agent_response actions for successful transfers. Count one procurement episode
per requester/counterparty-or-open-market/objective, collapsing repeated adverts,
revised prices, and a formal contract that repeats the same unmet demand.
Separate goods procurement from unpriced shared-access/cooperative projects,
aid, information exchange and ongoing upkeep. These are analyst-defined episodes,
not a canonical metric or an exhaustive numerical count of every social promise.

| Funnel | Offered episodes | Evidenced commitment | Settlement |
|---|---:|---:|---:|
| Goods procurement with both material quantities specified | 3 | 1 | 1 |
| Including exploratory goods-for-goods solicitations | 7 | 1 | 1 |

Thus conversion is 1/3 (33.3%) for fully quantified bargains, or 1/7 (14.3%)
under the broader definition. The only committed priced procurement settled;
1/1 is too small to establish generally reliable promises. These denominators
exclude ongoing upkeep transfers and shared construction, so
neither percentage should be called the ratio for all economically useful exchange.

The seven episodes are: seed 11 agent 2's food-for-stone campaign (unfilled),
agent 8's coin/food-for-stone offer to agent 3 (declined); seed 41 agents 7 and 6
separately asking agent 9 to exchange stone for wood/fiber (no agreement), agent
5's four-coins-for-two-stone bargain (settled), and agent 9's later wood-for-food
and food-for-water solicitations (no agreement). Repeated stone broadcasts and
agent 2's replacement contract are not new independent deals.

Agent 5's settlement has both physical legs: agent 3 contributes two stone to
structure-14 at tick 36, then receives four coins at tick 37. There was an
existing cooperative relationship; the price announcement and delivery
announcement both occur at tick 35. Simultaneous frozen-tick decisions do not
establish that the new price induced the delivery. Later payment is verified.

Formal instruments remained unused as settlement mechanisms: one offer_trade,
one contract_proposed, zero accept_trade and zero accepted/fulfilled contracts.
The report's trades_offered=2 combines the two instrument proposals; both are
one stone-procurement campaign in this audit. Pinned source e10d1a4 world.py
_action_accept_trade validates location, goods and capacity and then exchanges
the goods atomically. A successful accept_trade event is settlement, not an
unfulfilled promise. Verbal acceptance and accepted delivery contracts are
different stages and must be counted separately.

## Cooperative fulfillment and failures

Ten identifiable construction-collaboration projects were advertised or discussed:
six actually completed with multiple contributors; two completed through the
owner before the partner could contribute; two late well projects remained
unfinished at tick 60. These are project outcomes, not ten independent trades,
and one overlaps the paid procurement episode. Do not add their denominators.
The late wells are horizon-censored rather than demonstrated defaults.

Examples of effective repair:

- Seed 11 agent 5's wood gift fails on recipient capacity at tick 10. It drops
  the wood, picks it up, and contributes directly at tick 12. The shared shelter
  completes at tick 15 and access is granted.
- Seed 41 agent 4 cannot maintain another agent's farm despite farm access.
  It hands fiber to the owner at tick 23; the owner supplies upkeep the same tick.
- Seed 41 the partner cannot maintain a well because the owner finished it
  without the partner's contribution. Two wood are transferred at tick 58 and
  the owner applies them at tick 59.

Counterexamples prevent a blanket reliability claim. Agent 6 repeatedly promises
two wood for the northern shelter but agent 7 eventually supplies those wood;
agent 6 later supplies stone instead. Agent 9's promised onward water gift fails
on carrying capacity, with no later successful gift to that recipient. Agent 5's
offered water handoff at tick 38 fails on adjacency; a later tick-51 water gift
is a new observed transfer, not proof of timely fulfillment of the urgent promise.
Agent 7 promises to bring water back at tick 40 but no later gift to agent 9 is
recorded. Late seed-11 farm-access offers yield grants, but agent 10's promised
help has no recorded contribution to that host's farm; its later farm action
is on its own structure. Some commitments are repaired, some superseded, and
some do not materialize.

## Label failure is partly a default, not expressed intent

Across all 13 successful transfers, the ledger shows two payments, 11 gifts,
and zero barter. Raw actions show two explicit payment labels, four explicit
gift labels, and SEVEN OMITTED LABELS. Pinned world.py line 1669 defaults a missing
or empty kind to gift. Five of the seven omissions are upkeep-material transfers.
Seven of the eleven recorded gifts are accompanied by upkeep context, although
upkeep or gratitude alone does not prove an enforceable commercial bargain.
The old v6 judge also required explicit evidence of consideration; it would not
legitimately convert every reciprocal or helpful gift into a payment.

The strongest caution is therefore measurement design: recorded gift must not
be presented as an explicit declaration of unrequited intent when the field was
absent. Useful economic action also happens through contribute, grant_access,
maintain_structure and shared storage. Restoring the gift-only Sol classifier
would still miss those channels and offers that never caused any transfer.

## Historical interpretation and proposed measurement

The older comparative-advantage audit reported Sol 15/159 and Luna 6/100 formal
offer settlements; many offers expired UNACCEPTED. Those are different worlds,
populations and event-based denominators, so comparing them directly with Astra's
manual 1/7 episode ratio cannot establish improvement. A valid historical
comparison requires applying the same episode rubric to both sets of ledgers.

Retain optional participant labels as claims, preserve omitted versus explicit
labels, and add a separate evidence-linked analytical layer. Track solicitation,
commitment, delivery, reciprocal payment/access, lateness, failure reason, and
horizon censoring. Collapse repeated adverts. Distinguish material transfer,
construction, access and upkeep benefits, with uncertainty when consideration
is unstated. Freeze any semantic annotations with rubric and evidence pointers;
keep them separate from canonical benchmark accounting. This audit recommends
that work; it does not change the harness, recipes or scoring.
