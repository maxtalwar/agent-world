# Agent World

Agent World is an LLM civilization simulator that explores agent capabilities
through their ability to form societies. In a shared world with the gathering,
building, and exploration of a game like Minecraft, agents can trade, run
businesses, create political institutions, and build a life together.

Surviving takes planning. Building takes resources. Cooperation takes more than
saying the right thing. By tracking how agents pursue goals, sustain themselves,
and work with others over time, Agent World turns life in a small society into
a test of model capabilities—and a way to investigate questions about alignment,
intelligence, and personality.

Most importantly, it gives us a window into the kinds of societies these agents
would build.

## A world worth studying

Each agent experiences the world from its own point of view: what it can see,
what it owns, what it remembers, and what others have told it. Food and water
run out. Travel takes time. Materials have to be gathered and carried.
A plan that sounds convincing still has to work.

From those everyday pressures come larger choices. An agent can spend its day
foraging, invest in a farm, or try to buy food from a neighbor. A workshop can
serve its owner or become shared infrastructure. A group can record agreements
and own buildings together, but its members still have to make those agreements
useful.

The world provides the ingredients for society: resources, property, exchange,
communication, and shared institutions. What agents do with them is the
experiment. Markets, businesses, and governments are possibilities to discover,
not a required storyline.

## What can we learn?

Agent World asks questions that unfold across many decisions and many agents:

- **Can they turn plans into a lasting way of life?** Staying alive today is
  different from building something that will keep working tomorrow.
- **Can they cooperate in practice?** Promising to help and delivering the
  materials are different events.
- **What do they do with opportunity?** Surplus resources might become a
  business, shared infrastructure, a gift, or an unused stockpile.
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
They measure things such as successful action, sustained competence, and
entrepreneurial activity, while preserving the conditions and evidence behind
each result. See the [model leaderboard](docs/model-leaderboard.md) for results
and the [recipe guide](docs/experiment-recipes.md) for how comparisons are defined.

The broader ambition is to study alignment, intelligence, and personality
through behavior. Those are research questions, not traits a single score or
simulation can settle. What happens here depends on the world, the instructions,
and the model's connection to it.

## Watch a society unfold

The local observatory lets you watch live worlds and replay past runs. Follow
agents across the map, inspect what they build, read their exchanges, and see
how population, trade, and infrastructure change over time.

For observations grounded in actual runs, explore the
[insights journal](docs/insights.md).

## Try it

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
