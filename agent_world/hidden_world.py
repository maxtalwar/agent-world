"""Seed-derived hidden facts and shocks for hidden-world experiments.

Everything here is a pure function of the seed, computed by hashing rather than
drawn from the engine RNG. Agent actions, checkpoint resumes, and other random
draws therefore cannot shift it, so models on one seed face the same world.
"""
import hashlib
from dataclasses import dataclass

# seeded-v1 is the full v9 world; the others isolate one half for ablations.
HIDDEN_WORLD_MODES = {"off", "seeded-v1", "facts-v1", "shocks-v1"}
HIDDEN_FACT_MODES = {"seeded-v1", "facts-v1"}
SHOCK_MODES = {"seeded-v1", "shocks-v1"}
# Suitability varies by region, so one farm is evidence about its neighbors.
CROP_REGION_TILES = 4
CROP_SUITABILITY_LEVELS = (0.5, 1.0, 1.5)
REGROWTH_FACTOR_RANGE = (0.7, 1.2)
# Winter severity scales winter regrowth only; exposure damage stays public.
WINTER_REGROWTH_FACTOR_RANGE = (0.3, 1.0)
SEASONS_PER_YEAR = 4
SHOCK_EFFECTS: dict[str, dict[str, float]] = {
    "drought": {"regen": 0.4, "farm": 0.5},
    "blight": {"regen": 1.0, "farm": 0.25},
    "cold_snap": {"regen": 0.0, "farm": 0.25},
}
# Each shock strikes once a year: a start season and a duration in seasons.
SHOCK_WINDOWS = (("drought", 0, 2), ("blight", 2, 1), ("cold_snap", 3, 1))
SHOCK_DURATION_FRACTION = (0.3, 0.5)


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


def crop_suitability(seed: int, x: int, y: int) -> float:
    region = (x // CROP_REGION_TILES, y // CROP_REGION_TILES)
    index = int(_unit(seed, "crop", *region) * len(CROP_SUITABILITY_LEVELS))
    return CROP_SUITABILITY_LEVELS[index]


def regrowth_factor(seed: int) -> float:
    return _between(REGROWTH_FACTOR_RANGE, _unit(seed, "regrowth"))


def winter_regrowth_factor(seed: int) -> float:
    return _between(WINTER_REGROWTH_FACTOR_RANGE, _unit(seed, "winter"))


def year_shocks(seed: int, season_length_ticks: int, year: int) -> tuple[Shock, ...]:
    shocks = []
    year_start = year * SEASONS_PER_YEAR * season_length_ticks
    for name, first_season, seasons in SHOCK_WINDOWS:
        window = seasons * season_length_ticks
        duration = max(1, round(window * _between(SHOCK_DURATION_FRACTION, _unit(seed, name, year, "length"))))
        offset = int(_unit(seed, name, year, "start") * (window - duration + 1))
        start = year_start + first_season * season_length_ticks + offset
        shocks.append(Shock(name, start, start + duration))
    return tuple(shocks)


def active_shock(seed: int, season_length_ticks: int, tick: int) -> str | None:
    year = tick // (SEASONS_PER_YEAR * season_length_ticks)
    for shock in year_shocks(seed, season_length_ticks, year):
        if shock.start_tick <= tick < shock.end_tick:
            return shock.name
    return None
