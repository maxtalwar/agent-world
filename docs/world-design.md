# World Design

Agent World is currently a fixed 16x16, tick-based world. The map is handcrafted rather than randomly generated so runs are easier to compare.

## Canonical Map

Legend:

```text
. = plains
F = forest
M = mountain
W = water
```

Map:

```text
WWFFFFFFFMMMMMMM
WWFFFFFFMMMMMMMMM
WFFFFFFFMMMMMMMMM
WFFFFFF..MMMMMMM.
WFFFFF....MMMMM..
WFFFF.....WMMM...
WFFF.....WWWMM...
WFF......WWW.....
WF.......WW......
W........W.......
W................
W.............FFF
WW..........FFFFF
WWW.......FFFFFFF
WWWW.....FFFFFFFF
WWWWW...FFFFFFFFF
```

The geography is meant to create natural economic gradients:

- western coast and central water features for adjacent water gathering and fishing
- northwestern and southeastern forests for wood
- eastern/northeastern mountain range for stone and ore
- central/southern plains for settlement and farms

Agents spawn near the center at `(8,8)`.

## Resources

- `coin`: durable physical token with negligible carry weight and no survival use. Organic agents inherit four; one ingot can be minted into eight at a workshop.
- `water`: carried/consumed to restore thirst. Water tiles are not occupiable; agents gather water from adjacent land.
- `food`: carried/consumed to restore hunger and some energy. Carried food spoils periodically, while stored food is protected.
- `fiber`: early building/crafting input.
- `wood`: building/crafting/repair input from forests.
- `stone`: building/crafting input from mountains.
- `ore`: high-value raw material, reserved for later production chains.
- `tool`: craftable/equippable item, reserved for deeper tool effects.

Wild food/fiber are intentionally modest so persistent infrastructure can become valuable.

## Structures

Structures are neutral affordances. Agents are not told to build them; they see recipes and broad descriptions, but exact productivity details are left to discovery.

- `farm_plot`: persistent improved land on plains/forest that can support more reliable food production than wild foraging.
- `storage`: large inventory container with owner/access controls. Structures and claimed tiles can be personally or group owned, and stored food is protected from spoilage.
- `shelter`: simple rest structure. Improves waiting and prevents passive energy decay.
- `house`: better rest structure with moderate storage. Intended to support settlement clustering.
- `workshop`: material cache and crafting site. Reduces crafting energy cost and is the base for future production chains.
- `well`: local water infrastructure for settlements away from open water.

## Current Tuning

- Carry capacity is tight enough for storage to matter: `10`.
- Food and water reserves start at `10` and cap at `20`; energy starts at `25` and caps at `30`.
- Agents start with limited supplies: `food 1`, `water 2`.
- Water tiles are impassable until a future bridge/boat mechanic exists.
- Carried food spoils every few ticks; food inside storage, houses, or workshops is protected.
- Farming requires a farm plot; wild food comes from gathering, harvesting, or fishing rather than standing still.
- Trade can be direct to a visible agent or posted locally for any visible counterparty; offered goods are escrowed until accepted, rejected, or expired.
- Groups can own claims/structures and keep persistent agreements as a small institutional ledger.
- Wild food regrowth is intentionally low so construction pressure appears earlier.
- Build-readiness diagnostics are computed for researchers, but not included in agent observations.

The historical defaults use `shared_oasis`, `baseline`, and `neutral` treatment modes. The optional commerce experiment uses dispersed specialist spawns, productivity-bearing skills and durable tools, global standing offers with price history, productive-asset capacity/upkeep, paid public access, contributor dividends, and secured credit. See [economy-experiments.md](economy-experiments.md).

The organic experiment instead uses dispersed specialists, stronger skill differences, expensive/high-capacity infrastructure, physical offer escrow, co-located settlement, local market knowledge, and physical coins. It deliberately omits global discovery and enforced credit so transport, marketplaces, and trust remain agent problems.

## Next Likely Mechanics

- multi-tick construction and crop growth stages
- additional tool quality and capital-good tiers
- roads/paths lowering movement cost
- boats/bridges for crossing water
- longer production chains beyond ore, ingots, and advanced tools
- richer order-book matching beyond standing barter lots
- richer group governance and enforcement
