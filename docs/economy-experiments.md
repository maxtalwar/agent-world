# Economy Experiments

Agent World keeps its original neutral world as the default and exposes named treatments for testing why different institutions emerge. The treatments change incentives and affordances; they do not tell agents to trade, found firms, or adopt a political system.

## Treatment Axes

| Axis | Values | Purpose |
|---|---|---|
| `objective_mode` | `neutral`, `collective`, `individual` | Separates the original ambiguous objective from explicit group-welfare and private-utility treatments. |
| `geography_mode` | `shared_oasis`, `dispersed` | Compares a tightly clustered settlement with geographically separated specialists. |
| `economy_mode` | `baseline`, `commerce`, `organic` | `commerce` enables market-wide exchange tools; `organic` keeps exchange and information local while strengthening specialization and economies of scale. |

The `commerce` experiment condition pairs `dispersed` geography with `commerce` mechanics. The ordinary world remains `neutral` + `shared_oasis` + `baseline` for backwards comparison.

The `organic` condition pairs dispersed specialists with physical local exchange. It is intentionally excluded from the default 2x2 sweep and can be selected explicitly with `--environment organic --objective neutral`.

## Organic Mechanics

- Specialists start with much higher skill and aptitude in one occupation. Off-specialty work remains possible but produces less, costs two additional energy, and improves slowly.
- Farms, wells, storage, houses, shelters, and workshops have substantially higher fixed costs. Their capacity and upkeep intervals scale up too, making one shared asset cheaper than five duplicates without requiring sharing.
- Each agent begins with four physical `coin` items. Coins have no survival effect, weigh nothing at the current integer scale, can be lost/stored/transferred, and can be minted from ingots in a workshop. The prompt does not assign them a price or require their use.
- Offering a trade removes the offered goods from inventory and deposits them at the offer tile. Both parties must meet on that exact tile to settle.
- Public offers and completed prices are visible only locally. If an offer expires while its owner is away, the goods remain as an owned pile at the offer tile.
- Market history contains the actual accepted `give` and `receive` bundles, not an engine-assigned conversion value.
- Construction contributor shares use recipe-completion credits: completing each required input category carries equal project credit, independent of offline accounting units or market prices.
- Local speech and group administration are free. Global order books and engine-enforced credit are disabled; agents can still create groups, record agreements, grant access, and exchange physical goods.

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

The experiment runner defaults to the local scripted brain. Provider calls
happen only with an explicit model-backed brain such as `--brain openrouter`
or `--brain codex`, `--brain cursor`, or `--brain devin`.

Run the full 2x2 design on several seeds:

```bash
python3 -m agent_world.cli experiment \
  --brain openrouter \
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
  --brain openrouter \
  --model z-ai/glm-5.2 \
  --agents 5 \
  --ticks 60 \
  --seeds 23 \
  --environment commerce \
  --objective individual \
  --out-dir runs/experiments/commerce-individual-seed23 \
  --progress
```

Run the neutral organic treatment with GPT-5.6 Luna:

```bash
python3 -m agent_world.cli experiment \
  --brain codex \
  --model gpt-5.6-luna \
  --agents 5 --ticks 40 --seeds 29 \
  --environment organic --objective neutral \
  --out-dir runs/experiments/gpt56-luna-organic-neutral-seed29 \
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
