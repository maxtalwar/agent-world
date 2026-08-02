"""Hand-authored terrain maps for Agent World."""

from __future__ import annotations

from collections import Counter
from typing import Mapping

from agent_world.models import Position, Tile, WorldConfig
from agent_world.rules import TERRAIN_RULES


TERRAIN_GLYPHS = {
    ".": "plains",
    "F": "forest",
    "M": "mountain",
    "W": "water",
}

TERRAIN_SYMBOLS = {terrain: glyph for glyph, terrain in TERRAIN_GLYPHS.items()}

# A fixed 16x16 world with coherent geography:
# - west coast / ocean edge
# - northwestern and riverside forests
# - central river feeding a lake
# - eastern mountain range
# - central and southern plains for settlement
STANDARD_MAP_16 = [
    "WWFFFFFFFMMMMMMM",
    "WWFFFFFFMMMMMMMM",
    "WFFFFFFFMMMMMMMM",
    "WFFFFFF..MMMMMM.",
    "WFFFFF....MMMM..",
    "WFFFF.....WMMM..",
    "WFFF.....WWWMM..",
    "WFF......WWW....",
    "WF....FF.WW.....",
    "W......M.W......",
    "W...............",
    "W............FFF",
    "WW..........FFFF",
    "WWW.......FFFFFF",
    "WWWW.....FFFFFFF",
    "WWWWW...FFFFFFFF",
]

# A fixed 32x32 world with named geographic regions:
# - the Northern Range, split by the Highpass at x16-17
# - the Northwest Coast forests
# - the river, flowing from springs at x14-15,y7 through the central lake to
#   the southern delta
# - NORTH FORD at y10 and SOUTH FORD at y21, the river's only crossings
# - the Heartland plains basin east of the river
# - the Barrens in the far east, deliberately waterless and woodless marginal land
# - the South Shore basin in the southwest
# - the Great Forest in the southeast
STANDARD_MAP_32 = [
    "WWFFFFFFMMMMMMMM..MMMMMMMMMFF...",
    "WWFFFFFMMMMMMMMM..MMMMMMMMMFFF..",
    "WFFFFF.MMMMMMMMM..MMMMMMMM..FF..",
    "WFFFF..MMMMMMMM...MMMMMMM....FF.",
    "WFFF...MMMMMMM....MMMMMM....FFF.",
    "WWFF...MMMMMM.....MMMMM..FF.....",
    "WWF....MMMMM..M...MMMM..........",
    "WW.....MMMM...WW...MMM..........",
    "WW.....MMMFF..WW....MM..........",
    "W......MMFF...WW....M...........",
    "W......FF.......................",
    "W.....FFF.....WW.......M........",
    "WW....FF......WW................",
    "WWW..........WWWWW..............",
    "WWWW........WWWWWWW.....FF......",
    "WWW.........WWWWWWW.....FF......",
    "WW..........WWWWWW..............",
    "WW...........WWWWW..............",
    "W..............WW...............",
    "W..............WW...............",
    "W.....M........WW.........FF....",
    "W.....MM........................",
    "W..............WW........FFFF...",
    "WW.............WW......FFFFFF...",
    "WW.....F.......WW.......FFFFFF..",
    "W......FF......WW......FFFFFFFF.",
    "W......FF.....WWW.....FFFFFFFFF.",
    "WW......F.....WWW....FFFFFFFFFF.",
    "WWW..........WWWW..FFFFFFFFFFFFF",
    "WWWW.........WWWW.FFFFFFFFFFFFFF",
    "WWWWW.........WWWWW.FFFFFFFFFFFF",
    "WWWWWWWW....WWWWWWWWFFFFFFFFFFFF",
]


SPECIALIST_PROFILES: tuple[dict[str, object], ...] = (
    {
        "specialty": "farmer",
        "terrain": "plains",
        "anchor": Position(6, 10),
        "skill": "farming",
        "endowment": {"fiber": 2},
        "need_multipliers": {"water": 1.5},
    },
    {
        "specialty": "forester",
        "terrain": "forest",
        "anchor": Position(2, 2),
        "skill": "woodcraft",
        "endowment": {"wood": 2},
        "need_multipliers": {"energy": 1.5},
    },
    {
        "specialty": "miner",
        "terrain": "mountain",
        "anchor": Position(12, 2),
        "skill": "mining",
        "endowment": {"ore": 1},
        "need_multipliers": {"food": 2.0},
    },
    {
        "specialty": "fisher",
        "terrain": "coast",
        "anchor": Position(1, 10),
        "skill": "fishing",
        "endowment": {"food": 2},
        "need_multipliers": {"energy": 1.5},
    },
    {
        "specialty": "artisan",
        "terrain": "plains",
        "anchor": Position(11, 11),
        "skill": "crafting",
        "endowment": {"fiber": 2},
        "need_multipliers": {"water": 1.5},
    },
)

SPECIALIST_ANCHORS: dict[tuple[int, int], tuple[Position, ...]] = {
    (16, 16): (
        Position(6, 10),
        Position(2, 2),
        Position(12, 2),
        Position(1, 10),
        Position(11, 11),
    ),
    (32, 32): (
        Position(20, 15),
        Position(26, 26),
        Position(10, 6),
        Position(4, 14),
        Position(13, 11),
    ),
}


def specialist_profile(offset: int, width: int = 16, height: int = 16) -> dict[str, object]:
    """Return a copy of the deterministic dispersed-treatment role profile."""

    profile_index = offset % len(SPECIALIST_PROFILES)
    profile = SPECIALIST_PROFILES[profile_index]
    anchors = SPECIALIST_ANCHORS.get((width, height))
    if anchors is None:
        raise ValueError("Specialist anchors support only 16x16 and 32x32 worlds.")
    return {
        **profile,
        "anchor": anchors[profile_index],
        "endowment": dict(profile.get("endowment", {})),
        "need_multipliers": dict(profile.get("need_multipliers", {})),
    }


def find_specialist_spawn(
    tiles: list[list[Tile]],
    config: WorldConfig,
    offset: int,
    occupied: set[Position] | None = None,
) -> Position:
    """Choose a role-appropriate, geographically dispersed passable start."""

    occupied = occupied or set()
    profile = specialist_profile(offset, config.width, config.height)
    anchor = profile["anchor"]
    wanted = str(profile["terrain"])
    candidates: list[Position] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            position = Position(x, y)
            if position in occupied or not TERRAIN_RULES[tile.terrain].passable:
                continue
            if wanted == "coast":
                if not _is_coastal(tiles, position, config):
                    continue
            elif tile.terrain != wanted:
                continue
            candidates.append(position)
    if not candidates:
        raise RuntimeError(f"No dispersed spawn is available for {profile['specialty']}")
    return min(candidates, key=lambda position: (position.distance_to(anchor), position.y, position.x))


def _is_coastal(tiles: list[list[Tile]], position: Position, config: WorldConfig) -> bool:
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        x, y = position.x + dx, position.y + dy
        if 0 <= x < config.width and 0 <= y < config.height and tiles[y][x].terrain == "water":
            return True
    return False


def build_standard_tiles(config: WorldConfig) -> list[list[Tile]]:
    size = (config.width, config.height)
    if size == (16, 16):
        rows = STANDARD_MAP_16
    elif size == (32, 32):
        rows = STANDARD_MAP_32
    else:
        raise ValueError("The standard handcrafted map supports only 16x16 and 32x32 worlds.")
    tiles = tiles_from_rows(rows, resource_base_multiplier=config.resource_base_multiplier)
    _apply_wild_resource_density(tiles, config)
    return tiles


def tiles_from_rows(rows: list[str], resource_base_multiplier: float = 1.0) -> list[list[Tile]]:
    tiles: list[list[Tile]] = []
    for row in rows:
        tile_row: list[Tile] = []
        for glyph in row:
            terrain = TERRAIN_GLYPHS[glyph]
            tile_row.append(
                Tile(
                    terrain=terrain,
                    resources=Counter(_scaled_resources(TERRAIN_RULES[terrain].base_resources, resource_base_multiplier)),
                )
            )
        tiles.append(tile_row)
    return tiles


def _scaled_resources(resources: Mapping[str, int], multiplier: float) -> dict[str, int]:
    scaled: dict[str, int] = {}
    for resource, quantity in dict(resources).items():
        if quantity <= 0 or multiplier <= 0:
            scaled[resource] = 0
        else:
            scaled[resource] = max(1, int(round(quantity * multiplier)))
    return scaled


def _apply_wild_resource_density(tiles: list[list[Tile]], config: WorldConfig) -> None:
    center_x = config.width // 2
    center_y = config.height // 2
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if (
                config.geography_mode == "shared_oasis"
                and _distance(x, y, center_x, center_y) <= config.starter_resource_radius
            ):
                continue
            _maybe_remove_resource(tile, "food", config.wild_food_density, x, y, config.seed, salt=17)
            _maybe_remove_resource(tile, "fiber", config.wild_fiber_density, x, y, config.seed, salt=29)


def _maybe_remove_resource(tile: Tile, resource: str, density: float, x: int, y: int, seed: int, salt: int) -> None:
    if tile.resources.get(resource, 0) <= 0:
        return
    if tile.terrain == "water":
        return
    if _stable_noise(x, y, seed, salt) > max(0.0, min(1.0, density)):
        tile.resources[resource] = 0


def _stable_noise(x: int, y: int, seed: int, salt: int) -> float:
    value = (x * 73_428_767) ^ (y * 912_931) ^ (seed * 19_349_663) ^ (salt * 83_492_791)
    value &= 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x85EB_CA6B) & 0xFFFFFFFF
    value ^= value >> 13
    value = (value * 0xC2B2_AE35) & 0xFFFFFFFF
    value ^= value >> 16
    return value / 0xFFFFFFFF


def _distance(x1: int, y1: int, x2: int, y2: int) -> int:
    return abs(x1 - x2) + abs(y1 - y2)


def render_tiles(tiles: list[list[Tile]]) -> str:
    return "\n".join("".join(TERRAIN_SYMBOLS[tile.terrain] for tile in row) for row in tiles)
