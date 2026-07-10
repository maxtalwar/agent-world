# Economy Experiments

Agent World keeps its original neutral world as the default and exposes named treatments for testing why different institutions emerge. The treatments change incentives and affordances; they do not tell agents to trade, found firms, or adopt a political system.

## Treatment Axes

| Axis | Values | Purpose |
|---|---|---|
| `objective_mode` | `neutral`, `collective`, `individual` | Separates the original ambiguous objective from explicit group-welfare and private-utility treatments. |
| `geography_mode` | `shared_oasis`, `dispersed` | Compares a tightly clustered settlement with geographically separated specialists. |
| `economy_mode` | `baseline`, `commerce` | Enables market-wide offers, productive-asset capacity and upkeep, access fees, contributor dividends, and secured credit. |

The `commerce` experiment condition pairs `dispersed` geography with `commerce` mechanics. The ordinary world remains `neutral` + `shared_oasis` + `baseline` for backwards comparison.

## Commerce Mechanics

- Dispersed agents begin in different resource regions with a visible specialty, aptitude, endowment, and asymmetric needs.
- Repeated work raises skill. Skill can increase output and reduce energy cost.
- Equipped `tool` and `advanced_tool` items increase production, reduce energy use, wear down, and eventually break.
- The production chain now includes `ore -> ingot -> advanced_tool`; ingots and advanced tools require an accessible workshop.
- Commerce-mode public offers can be global standing offers. Accepted terms are retained in `market_history` for price discovery.
- Accepting or rejecting a trade is free, so a completed exchange no longer costs twice as much collective action capacity as a gift.
- Productive structures have per-tick capacity and periodic upkeep in commerce mode. An inactive structure must be maintained before it provides services again.
- Owners may publish an access fee. Outsiders pay on use; receipts enter the structure treasury and are credited to construction contributors according to their material-value shares.
- Secured credit contracts escrow the lender's advance, escrow borrower collateral on acceptance, set a due tick, and resolve repayment or default mechanically.
- Speech and group administration cost action points in commerce mode. They remain free in the historical baseline.

New agent-facing actions include:

- `set_access_fee`, `maintain_structure`, and `claim_dividend`
- `offer_contract`, `accept_contract`, and `repay_contract`
- `offer_trade` with `scope: "global"` for commerce-mode public offers

## Reproducible Runs

The experiment runner defaults to the local scripted brain. LLM calls happen only with an explicit `--brain llm`.

Run the full 2x2 design on several seeds:

```bash
python3 -m agent_world.cli experiment \
  --brain llm \
  --model z-ai/glm-5.2 \
  --agents 5 \
  --ticks 60 \
  --seeds 11 13 17 \
  --environment all \
  --objective all \
  --out-dir runs/experiments/glm52-factorial \
  --progress
```

Run one treatment cell:

```bash
python3 -m agent_world.cli experiment \
  --brain llm \
  --model z-ai/glm-5.2 \
  --agents 5 \
  --ticks 60 \
  --seeds 23 \
  --environment commerce \
  --objective individual \
  --out-dir runs/experiments/commerce-individual-seed23 \
  --progress
```

Each run writes raw events, a snapshot, LLM usage, a structured report, and a provenance manifest. Manifests include the git SHA and dirty state, source hashes, exact initial prompt hashes, model/provider settings, condition, seed, target and final ticks, output paths, and analysis-validity status. The experiment root contains aggregate JSON and Markdown with paired factorial contrasts.

## Interpretation Metrics

Do not compare gifts and trades using event counts alone. Reports and live metrics include:

- gift units, book value, item mix, subsistence versus productive inputs, group status, and reciprocity;
- offer conversion, acceptance latency, invalid accept attempts, transferred value, and completed-price history;
- productive activity concentration and division-of-labor indices;
- construction contributions, contributor shares, asset value, fee income, and asset-adjusted wealth;
- contract offers, acceptances, repayment, fulfillment, and default;
- survival, capacity, invalid actions, LLM reliability, and inference cost.

The intended question is not whether markets can be prompted into existence. It is whether markets, firms, credit, or commons become the lower-cost solution under different objectives, geography, production technology, ownership rules, and coordination costs.
