"""Seed-derived hidden facts and shocks for hidden-world experiments.

Everything here is a pure function of the seed, computed by hashing rather than
drawn from the engine RNG. Agent actions, checkpoint resumes, and other random
draws therefore cannot shift it, so models on one seed face the same world.
"""
import hashlib
from dataclasses import dataclass

# seeded-v1 is the first v9 world; the facts/shocks modes isolate its halves for
# ablations. seeded-v2 widens crop suitability modestly, strengthens shocks, and
# drops the rulebook hint about hidden facts. Older modes stay reproducible.
# seeded-v3 is the simplified v9 world: seed-scheduled shocks at v2 strength, and
# season rules described in plain words instead of exact multipliers. It has no
# per-seed or per-area production differences.
# shocks-v3 isolates the seeded-v3 shocks: same strength, without soil or
# plain-word seasons.
# shocks-soil-v3 adds seeded-v3 soil to shocks-v3, still with exact season numbers.
HIDDEN_WORLD_MODES = {"off", "seeded-v1", "facts-v1", "shocks-v1", "seeded-v2", "seeded-v3", "shocks-v3",
                      "shocks-soil-v3"}
HIDDEN_FACT_MODES = {"seeded-v1", "facts-v1", "seeded-v2"}
SHOCK_MODES = {"seeded-v1", "shocks-v1", "seeded-v2", "seeded-v3", "shocks-v3", "shocks-soil-v3"}
# These modes describe seasons in words rather than giving exact multipliers.
PLAIN_SEASON_MODES = {"seeded-v3"}
# These modes give each tile a soil quality that follows the land.
SOIL_MODES = {"seeded-v3", "shocks-soil-v3"}
SOIL_LEVELS = {-1: 0.4, 0: 1.0, 1: 1.7}
SOIL_WATER_RANGE = 2
SOIL_MOUNTAIN_RANGE = 1
# Only these modes tell agents in the rulebook that hidden facts exist.
HIDDEN_FACT_HINT_MODES = {"seeded-v1", "facts-v1"}
# Suitability varies by region, so one farm is evidence about its neighbors.
CROP_REGION_TILES = 4
REGROWTH_FACTOR_RANGE = (0.7, 1.2)
# Winter severity scales winter regrowth only; exposure damage stays public.
WINTER_REGROWTH_FACTOR_RANGE = (0.3, 1.0)
SEASONS_PER_YEAR = 4
# Each shock strikes once a year: a start season and a duration in seasons.
SHOCK_WINDOWS = (("drought", 0, 2), ("blight", 2, 1), ("cold_snap", 3, 1))


@dataclass(frozen=True)
class Tuning:
    crop_levels: tuple[float, ...]
    shock_effects: dict[str, dict[str, float]]
    shock_duration_fraction: dict[str, tuple[float, float]]


V1 = Tuning(
    crop_levels=(0.5, 1.0, 1.5),
    shock_effects={
        "drought": {"regen": 0.4, "farm": 0.5},
        "blight": {"regen": 1.0, "farm": 0.25},
        "cold_snap": {"regen": 0.0, "farm": 0.25},
    },
    shock_duration_fraction={name: (0.3, 0.5) for name, _, _ in SHOCK_WINDOWS},
)
V2 = Tuning(
    crop_levels=(0.4, 1.0, 1.7),
    shock_effects={
        "drought": {"regen": 0.25, "farm": 0.35},
        "blight": {"regen": 1.0, "farm": 0.1},
        "cold_snap": {"regen": 0.0, "farm": 0.25},
    },
    shock_duration_fraction={"drought": (0.5, 0.7), "blight": (0.3, 0.5), "cold_snap": (0.3, 0.5)},
)


def tuning(mode: str) -> Tuning:
    return V2 if mode in {"seeded-v2", "seeded-v3", "shocks-v3", "shocks-soil-v3"} else V1


# Kept for callers that predate seeded-v2; these are the v1 values.
CROP_SUITABILITY_LEVELS = V1.crop_levels
SHOCK_EFFECTS = V1.shock_effects


@dataclass(frozen=True)
class Shock:
    name: str
    start_tick: int
    end_tick: int


def _unit(seed: int, *parts: object) -> float:
    label = ":".join(str(part) for part in (seed, "hidden", *parts))
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _between(bounds: tuple[float, float], fraction: float) -> float:
    return bounds[0] + (bounds[1] - bounds[0]) * fraction


def crop_suitability(seed: int, x: int, y: int, mode: str = "seeded-v1") -> float:
    levels = tuning(mode).crop_levels
    region = (x // CROP_REGION_TILES, y // CROP_REGION_TILES)
    index = int(_unit(seed, "crop", *region) * len(levels))
    return levels[index]


def regrowth_factor(seed: int) -> float:
    return _between(REGROWTH_FACTOR_RANGE, _unit(seed, "regrowth"))


def winter_regrowth_factor(seed: int) -> float:
    return _between(WINTER_REGROWTH_FACTOR_RANGE, _unit(seed, "winter"))


def year_shocks(seed: int, season_length_ticks: int, year: int, mode: str = "seeded-v1") -> tuple[Shock, ...]:
    shocks = []
    year_start = year * SEASONS_PER_YEAR * season_length_ticks
    for name, first_season, seasons in SHOCK_WINDOWS:
        window = seasons * season_length_ticks
        duration = max(1, round(window * _between(tuning(mode).shock_duration_fraction[name], _unit(seed, name, year, "length"))))
        offset = int(_unit(seed, name, year, "start") * (window - duration + 1))
        start = year_start + first_season * season_length_ticks + offset
        shocks.append(Shock(name, start, start + duration))
    return tuple(shocks)


def active_shock(seed: int, season_length_ticks: int, tick: int, mode: str = "seeded-v1") -> str | None:
    year = tick // (SEASONS_PER_YEAR * season_length_ticks)
    for shock in year_shocks(seed, season_length_ticks, year, mode):
        if shock.start_tick <= tick < shock.end_tick:
            return shock.name
    return None


def soil_quality(seed: int, terrains: list[list[str]]) -> list[list[float]]:
    """Farm output multiplier per tile: richer near water, poorer beside mountains.

    A seeded nudge per 4x4 area adds local variation, so the land is a strong
    hint but not a complete answer.
    """
    height, width = len(terrains), len(terrains[0])
    cells = [(x, y) for y in range(height) for x in range(width)]

    def near(x: int, y: int, terrain: str, reach: int) -> bool:
        return any(terrains[ty][tx] == terrain and abs(tx - x) + abs(ty - y) <= reach for tx, ty in cells)

    grid = []
    for y in range(height):
        row = []
        for x in range(width):
            score = int(near(x, y, "water", SOIL_WATER_RANGE)) - int(near(x, y, "mountain", SOIL_MOUNTAIN_RANGE))
            nudge = _unit(seed, "soil", x // CROP_REGION_TILES, y // CROP_REGION_TILES)
            score += -1 if nudge < 0.25 else 1 if nudge >= 0.75 else 0
            row.append(SOIL_LEVELS[max(-1, min(1, score))])
        grid.append(row)
    return grid
