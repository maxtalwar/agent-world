# Agent World

Agent world is a LLM-civilization simulator that benchmarks agent capabilities through their ability to form societies. Agents can trade, run businesses, create political institutions, build, and explore in a model world similar to Minecraft. By measuring agent's ability to carry out their goals, survive, and cooperate, agent world serves as a novel benchmark on model traits like alignment, intelligence, and personality. Most importantly, it gives us a window into the types of societies they would build.

Because this is not an environment the leading models were trained on, it gives us a novel way to measure the general intelligence of different LLMs. 

## The setup

Each agent is spawned into the world and is only given the explicit instruction to survive. Agents can just see their surroundings, inventory, the rules of the game, and their memories. With that limited information they make decisions about how to respond to survival pressures like hunger, thirst, and cold exposure. 

From those pressures come larger choices. An agent can spend its day
foraging, invest in a farm, or try to buy food from a neighbor. A workshop can
serve its owner or become a public good. A group of agents can come to agreements, create contracts, and own buildings together. 

The world provides the ingredients for society: resources, property, exchange,
communication, and shared institutions. What agents do with them is the
experiment. Markets, businesses, governments and capital formation are all possible emergent behavior but are not hardcoded. 

## What can we learn?

Agent World asks questions that unfold across many decisions and many agents:

- **Can they plan effectively?** As the seasons progress surival pressure changes. Addressing short-term needs, while necessary, is a different skillset from preparing for winter. How successfully they do both helps us measure different model's planning ability. 
- **Can they cooperate in practice?** We can measure how often agents communicate, and how effectively they turn that communication into actual results.
- **What do they do with opportunity?** Surplus resources might become a
  business, a public good, a gift, or an unused stockpile.
- **What kinds of institutions emerge?** Who owns what, who gets access, and
  which agreements survive beyond the conversation that created them?
- **How does the world shape their behavior?** Scarcity, geography, memory,
  and the other agents in a population can all change what happens.

These questions connect individual capability to collective outcomes. A capable
agent might thrive while its neighbors struggle. A generous population might
share everything yet fail to build a reliable food supply. The interesting
question is how individual choices add up to a society.

## A laboratory and a benchmark

Agent World is a laboratory for changing worlds, populations, and agent
configurations, then observing what follows. Populations can use one model or
bring different models into the same world.

Within that laboratory, versioned benchmark recipes define comparable tests.
They measure things like general competence, execution ability, cost, speed, and
entrepreneurship while preserving the conditions and evidence behind
each result. See the [model leaderboard](docs/model-leaderboard.md) for results
and the [recipe guide](docs/experiment-recipes.md) for how comparisons are defined.

The broader ambition is to study alignment, intelligence, and personality
through behavior. What happens here depends on the world, the instructions,
and the model's connection to it.

## Watch a society unfold

The local observatory lets you watch live worlds and replay past runs. Follow
agents across the map, inspect what they build, read their exchanges, and see
how population, trade, and infrastructure change over time.

For observations grounded in actual runs, explore the
[insights journal](docs/insights.md).

## Try it

If you get confused, Codex or Claude can handle the setup :).

You need Python 3.10 or newer. From the repository directory, run a small,
scripted simulation and open it in the observatory:

```bash
python3 -m agent_world.cli run --ticks 25 --agents 5 --seed 11 --out runs/example.jsonl --snapshot runs/example-snapshot.json
python3 -m agent_world.cli view --events runs/example.jsonl --snapshot runs/example-snapshot.json
```

Open [the local observatory](http://127.0.0.1:8765). This first example uses
scripted agents, so it needs no model account and makes no LLM calls.

To run LLM agents, follow the [managed-run quickstart](docs/run-quickstart.md).
It covers configuring an experiment and launching it with saved progress and
automatic recovery. Connector setup and implementation details are in the
[technical reference](docs/technical-reference.md).

## Explore further

- [World design](docs/world-design.md): resources, geography, and the rules agents live with.
- [Agent interface](docs/agent-interface.md): what agents can perceive and do.
- [Architecture](docs/architecture.md): how the simulation works.
- [Economy experiments](docs/economy-experiments.md): different conditions for exchange and cooperation.
- [Observability](docs/observability.md): inspecting and replaying runs.
- [Technical reference](docs/technical-reference.md): connector configuration, command examples, and implementation details.
