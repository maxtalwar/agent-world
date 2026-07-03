# Research Notes

This file captures current observations and next hypotheses so future chats can continue without rediscovering the state of the project.

## What Has Emerged So Far

Small GPT-5.4-mini runs have shown:

- agents can survive for short runs
- agents gather food/water/fiber and move as local resources deplete
- agents remember depleted tiles and useful nearby resources
- agents communicate occasionally
- at least one run produced an accepted barter trade without being prompted to create trade

## What Has Not Emerged Reliably

- persistent structure building
- land claims
- group formation
- markets
- firms
- political rules or leadership

This is expected. The world is still shallow and agents can often survive through direct gathering.

## Recent Tuning

To make infrastructure more meaningful:

- wild food/fiber were reduced
- carry capacity was lowered
- starting food was lowered
- farm plots were made productive and persistent
- diagnostics were added to show when agents could build structures

Important: build-readiness diagnostics are for researchers only and are not included in agent observations.

## Current Hypothesis

Emergence requires pressure gradients:

- geography should create comparative advantage
- carrying capacity should make storage useful
- wild resources should not be so abundant that infrastructure is optional
- production chains should make specialization valuable
- public records/contracts should make coordination possible

## Near-Term Next Steps

1. Run 5-agent and 10-agent simulations under the new tuning.
2. Inspect whether `farm_plot` appears without explicit buildability hints.
3. If not, add deeper consequences rather than prompt nudges:
   - lower wild food further
   - make farm plots produce delayed harvests
   - make food spoil unless stored
   - make houses/storage reduce loss or improve recovery
4. Add a public notice board for posted offers/contracts.
5. Add ore -> ingot -> tool production chains.

## Currency Direction

Do not hard-code an official currency yet. Prefer currency-capable commodities and institutions:

- durable/scarce ingots
- posted offers
- IOUs/promissory notes
- escrowed trades
- group/shared ledgers

If a state later emerges, agents can create official currency through rules/policy.
