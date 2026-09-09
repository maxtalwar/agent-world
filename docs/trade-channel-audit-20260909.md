# Trade offers, settlements, and informal exchange: Astra and benchmark leaders

Audit completed 2026-09-09 UTC (September 8 Pacific). **A formal-trade headline understates Astra's economic cooperation, but the evidence does not support a large hidden market of settled priced trades. The distinction is protocol-specific: restored v6 Astra actually settled more formal trades than historical Sol; v6.1 Sol settled far more formal trades, while Astra made more service-payment transfers.** Other leaders, particularly Opus 5, also have substantial informal commerce.

This retrospective audit covers 24 completed worlds, seeds 11/41, ten agents, medium effort. V6/v6.1 have 50 ticks; v8.1 has 60. Historical leaders were selected from the verified metrics database: the top four historical v6 leaders plus Sol, and the admitted v8.1 leaders Astra, Grok 4.6, Sonnet 5 and Terra. There is no admitted matched no-healing v8.1 Sol study in that database; healing-enabled Sol experiments are not substituted. The three supplemental managed studies have ready manifests, clean integrity, full usage coverage and frozen transfer accounting. Their model provenance remains requested-only. Their use here is not new leaderboard admission.

[Reproducible evidence](trade-channel-audit-20260909.json) contains per-seed counts, original frozen scores, formal events, every transfer and nearby context, completed joint-project records, source hashes and manual Astra service-follow-through annotations. Regenerate with `python3 scripts/audit-trade-channels-20260909.py`. The [script](../scripts/audit-trade-channels-20260909.py) checks terminal horizons and exact alignment of all frozen classifications with successful transfer events. Database verification returned 95 runs, 41 models, 41,491 decisions, 100% latency coverage, and no integrity/foreign-key errors.

## What is being counted

- **Formal offer:** a successful `offer_trade` event. Reposts are separate events. Delivery-contract proposals are shown separately, not folded into this denominator.
- **Formal settlement:** a successful `accept_trade` event, which exchanges the goods atomically. It is not just a promise to deliver later. None of these selected runs has multiple successful lots against the same offer ID, so the event ratios below also equal the fraction of posted offer IDs filled.
- **Commercial transfer:** an executed gift-channel handoff classified as `payment_for_service` or `barter_settlement` in v6/v6.1, or declared `payment`/`barter` in v8.1. This measures a delivered leg, not necessarily a whole bargain or completed reciprocal obligation.
- **Service follow-through:** a manual link between that handoff and an observed access grant/public-access policy, completed construction, upkeep or storage action. Existing benefits, same-tick decisions and fungible inputs prevent a causal interpretation.
- **Joint completion:** a successful `build` event whose structure has multiple recorded contributors. This excludes unfinished projects and can miss indirect contributions made through another agent's inventory. It differs from report/database cooperative-build metrics that may include unfinished projects.

Do not add payment legs, formal settlements, access grants and joint projects into a synthetic number of trades. Two handoffs can be opposite legs of one swap; several payments can fund one shelter; one paid construction deal can appear in several channels. Neither repeated adverts nor a classifier's payment label alone establishes settlement.

## Historical/restored v6

Totals across both seeds. The restored Astra study is `astra-v6-restored-20260908`; it must not be confused with the board-enabled study originally labeled v6, analyzed below as v6.1. Historical source differences and replay-based restoration are documented in [the restoration audit](benchmark-recipe-restoration-20260908.md).

| Model | Formal offers | Formal settlements | Formal conversion | Service-payment legs | Barter legs | All gift-channel transfers | Joint completions |
|---|---:|---:|---:|---:|---:|---:|---:|
| Astra | 14 | 2 | 14.3% | 5 | 0 | 15 | 6 |
| Sol | 21 | 1 | 4.8% | 1 | 2 | 20 | 4 |
| Fable 5 | 103 | 21 | 20.4% | 4 | 2 | 10 | 6 |
| Grok 4.6 | 71 | 7 | 9.9% | 7 | 1 | 14 | 3 |
| Opus 5 | 98 | 3 | 3.1% | 13 | 3 | 24 | 4 |
| Opus 4.8 | 37 | 1 | 2.7% | 3 | 0 | 4 | 3 |

**Astra is not below Sol on settled formal trade in restored v6.** Seed 11 posted two offers and settled none; seed 41 posted 12 and settled two. Both settlements were food/water exchanges between agents 2 and 8, at ticks 39 and 42 (`run.jsonl` lines 2834 and 3019). The second exchange reverses their roles. These are two valid settlements, not evidence of broad participation in a market.

Astra's five classified service-payment transfers all occur in seed 11. All five have an observed counterpart benefit: farm access, storage access/upkeep, shelter completion and farm restoration, ongoing shelter upkeep, or tile access. For example, agent 8 hands agent 6 two fiber at tick 28; storage upkeep occurs at tick 29 and access is finally granted at tick 33. Agent 4 supplies the last stone at tick 43 while requesting tile access; the grant succeeds that tick and the stone is contributed at tick 44. The evidence JSON records every linked line. Five of the other transfers remain unclassifiable and five are classified as unrequited; those labels are preserved.

Offers still often failed. Agent 2 repeatedly advertised food/access for two shelter stone in seed 11 (ticks 30, 33, 35, 40, 43); the formal offer expired and the shelter remained unfinished. Agent 5 separately solicited stone at ticks 39/42. In seed 41, agent 5 reposted wood procurement with changing prices/counterparties four times (trades 1–4), all unfilled. These are not four independent economic objectives. An expired water offer followed by a smaller explicitly free water gift in seed 11 is aid, not settlement of the original bargain.

The correction applies to the leaders too. **Opus 5's three formal settlements hide 16 commercially classified transfer legs**, mostly shelter access, construction and upkeep, plus three barter legs. That is stronger evidence of an informal service economy than its formal count suggests, but not 16 additional complete trades. Historical Sol's two barter-classified transfers at seed-11 ticks 45/46 are the fiber and water legs of one exchange, not two deals. Fable's 21 formal settlements remain much greater than Astra's two even after acknowledging both models' informal activity.

## Matched v6.1

The retained Astra study is `web-gpt-6-astra-1dafc66aaaea`; matched Sol is `sol-v61-ledger-comparison-20260908`. Both include the initially empty global board and delivery contracts. Original source commits differ; the restoration/replay documentation preserves that fact. Do not pool these worlds with historical v6.

| Model | Formal offers | Formal settlements | Formal conversion | Classified service-payment legs | All gift-channel transfers | Joint completions |
|---|---:|---:|---:|---:|---:|---:|
| Astra | 1 | 0 | 0% | 15 | 39 | 7 |
| Sol | 68 | 15 | 22.1% | 9 | 34 | 4 |

Sol also proposed two delivery contracts: one was accepted then defaulted and the other cancelled. Neither settled. Contract acceptance therefore differs materially from atomic trade acceptance.

**Astra's zero formal settlements is a poor description of its service cooperation. The frozen Sol classifier already recognizes 15 service-payment legs, compared with Sol's nine.** The 15 Astra legs comprise five in seed 11 and ten in seed 41. All have an observed corresponding benefit by the horizon, but that is conditional follow-through among executed payment legs, not 100% conversion of all offers.

The handoffs include installments and shared benefits. Agent 4 sends agent 9 three wood and three fiber in two actions at tick 10, requesting shelter access. The shelter completes at tick 27; after an initial failed public-access action, it is restored and made publicly accessible at tick 28. That is one agreement with an 18-tick lag, not two instant trades. In seed 11, agents 8 and 10 each send agent 5 one wood at tick 36; one well is restored at tick 37, with additional upkeep at tick 43. In seed 41, fiber at tick 32 and food at tick 33 support the same agent-4/agent-10 storage relationship.

Yet priced goods procurement remained weak. **Four distinct seed-11 stone-procurement campaigns are explicit in the public messages/board: agents 2, 4, 7 and 3, each seeking two stone. None settled as an evidenced paid goods bargain.** Agent 2's initial food exchange becomes a four-coin offer; agents 7 and 3 offer four coins; agent 4 posts three food for two stone. The latter offer expires; agents 4, 3 and 7 later finish their own shelters, while agent 2's remains unfinished. Owner self-provision is not procurement settlement. These four campaigns alone show why payment-follow-through cannot be used as the denominator for all commercial intent. They are an identified campaign set, not an exhaustive census of all service offers.

## V8.1, no healing

| Model | Formal offers | Formal settlements | Formal conversion | Declared payment legs | Gift-labeled legs | Joint completions |
|---|---:|---:|---:|---:|---:|---:|
| Astra | 1 | 0 | 0% | 2 | 11 | 6 |
| Grok 4.6 | 117 | 12 | 10.3% | 1 | 13 | 2 |
| Sonnet 5 | 27 | 4 | 14.8% | 2 | 1 | 3 |
| Terra | 16 | 2 | 12.5% | 0 | 7 | 0 |

Astra additionally proposed one delivery contract; Grok proposed two. None settled. This explains the report/database headline of two Astra offers and 119 Grok offers: those counts combine instrument types. The table above consistently uses actual `offer_trade` events.

The [existing complete Astra exchange audit](astra-v81-exchange-audit.md) examined all 268 emitted messages and 13 successful transfers. Its deduplicated goods-procurement funnel is **seven solicitations → one evidenced commitment → one settled deal (14.3%)**. Restricting to three fully quantified bargains gives one settlement out of three (33.3%). The wider denominator includes exploratory solicitations; neither includes ongoing upkeep and shared projects.

The paid deal is seed 41: agent 5 offers four coins for two stone at tick 35; agent 3 contributes two stone at tick 36; four coins change hands at tick 37. Both material legs are observed. Six of ten discussed construction-collaboration projects complete with multiple contributors, two are completed by their owners and two late wells remain unfinished. These project outcomes overlap the paid deal and cannot be added to it.

The label problem is real but different from v6: **v8.1 does not use the frozen Sol gift classifier.** Raw Astra actions show two explicit payments, four explicit gifts and seven missing `kind` fields; the engine records omissions as gifts. Five omissions supply upkeep materials. The formal count therefore misses a paid delivery and useful collaboration, but relabeling all eleven gift events as trades would be unjustified.

The same caution applies to the peers. Grok's gift-labeled fiber at seed-11 tick 38 accompanies shelter access/farm upkeep; its food at tick 50 and water back at tick 51 show reciprocity without an explicit fixed barter obligation. Sonnet sends shelter-access payments in both seeds; in seed 11 the recipient explicitly says no payment is needed while granting access. Counting every `payment` label as a mutually agreed sale would overstate Sonnet's commerce. Terra's smaller water gifts near larger unfilled offers likewise do not automatically settle those offers.

## Interpretation and limits

The evidence supports **Astra's preference for shared infrastructure and maintenance over posted markets**, not an absence of exchange. That activity partly bypasses the formal trade counter; in v6/v6.1 much of it was already picked up by the classifier and scored as service income. V8.1 additionally has a missing-label default. Neither mechanism justifies assuming that all generosity, resource pooling or access provision is a commercial bargain.

The formal offer/settlement inventory and transfer coverage are complete for the selected 24 worlds. Astra's 20 v6/v6.1 classified payment legs have individually annotated observed benefits. The peer review preserves frozen labels and inspects transfer context; it is **not a new exhaustive semantic annotation of every peer's conversational offers and reciprocal obligations**. There is therefore no defensible combined informal-plus-formal conversion ranking here. Astra's 1/7 manual procurement rate must not be compared as if it shared a denominator with Sol's 15/68 posted-offer rate. Two seeds also do not establish a general model ranking or a causal board effect.

This audit leaves frozen reports, classifications, recipes, source catalog and leaderboard scores unchanged. Original per-seed scores are included in the evidence JSON rather than introducing unrelated rescoring. The practical reporting improvement is to show formal proposals/settlements, commercially classified transfer legs, verified counterpart benefits and completed shared projects alongside one another, with explicit units.
