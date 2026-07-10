# Research Notes

This file captures current observations and next hypotheses so future chats can continue without rediscovering the state of the project.

## What Has Emerged So Far

GLM-5.2 and smaller model runs have shown:

- agents can survive for short runs
- agents gather food/water/fiber and move as local resources deplete
- agents remember depleted tiles and useful nearby resources
- agents communicate occasionally
- accepted barter without a trade instruction
- a five-member settlement, six group-owned structures, and two heavy cooperative builds
- a centralized aid network: the 60-tick Lakeside run had 27 gifts, of which 23 were food/water aid, versus eight offers and one accepted trade

## What Has Not Emerged Reliably

- repeated price formation across independent counterparties
- wage labor or a durable firm
- recurring access-fee/dividend income
- credit repayment/default in an LLM run
- political rules that agents actually need to enforce

The earlier world made a small, trusted gift economy cheaper than formal exchange. The new commerce treatment makes specialization, priced productive access, capital returns, standing markets, and secured credit mechanically possible without instructing agents to use them.

## Recent Tuning

To distinguish agent priors from world incentives:

- objective modes now separate neutral, collective, and individual treatments
- geography can disperse agents into different resource regions with persistent specialties and asymmetric needs
- skills and durable tools affect output and energy; ore now feeds an ingot/advanced-tool capital chain
- public standing offers retain completed-price history and acceptances no longer spend an extra action point
- productive structures can have capacity, upkeep, public fees, contributor shares, and dividend claims
- secured credit contracts enforce advances, collateral, repayment dates, and default
- commerce-mode speech and group administration have nonzero coordination cost
- reports value transfers/assets and correctly identify interrupted runs and LLM failures

Important: build-readiness diagnostics are for researchers only and are not included in agent observations.

## Current Hypothesis

Emergence requires pressure gradients:

- geography should create comparative advantage
- carrying capacity should make storage useful
- wild resources should not be so abundant that infrastructure is optional
- production chains should make specialization valuable
- public records/contracts should make coordination possible

## Near-Term Next Steps

1. Run matched GLM-5.2 cells across several seeds with `agent_world.cli experiment`.
2. Compare gift value and purpose, market conversion/value, specialization, asset-adjusted wealth, fee/dividend income, contracts, survival, and invalid actions.
3. Only after replicated results, vary one mechanism at a time: geography without commerce, market access without private objectives, or coordination cost without specialization.
4. Scale to multiple settlements and more agents once the five-agent treatment demonstrates reliable interaction.
5. Add richer order matching, wages/equity issuance, transport capital, and population turnover only where observed behavior exposes a missing primitive.

## Currency Direction

Do not hard-code an official currency yet. Prefer currency-capable commodities and institutions:

- durable/scarce ingots
- posted offers
- IOUs/promissory notes
- escrowed trades
- group/shared ledgers

If a state later emerges, agents can create official currency through rules/policy.
