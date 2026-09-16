"""Move definitions and deterministic moveset generation.

The Kaggle dataset has no move data, so each Pokémon receives a four-move set
derived from its typing and stat profile: two STAB moves from its primary type,
one from its secondary type (or Normal coverage), and one status move suited to
its stats. Generation is seeded by Pokédex number so a Pokémon always gets the
same moves.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum

from app.data.models import PokemonRecord
from app.domain.types import PokemonType


class MoveCategory(StrEnum):
    PHYSICAL = "physical"
    SPECIAL = "special"
    STATUS = "status"


class StatusEffect(StrEnum):
    """Self-targeting effects for status moves."""

    BOOST_ATTACK = "boost_attack"
    BOOST_DEFENSE = "boost_defense"
    BOOST_SP_ATTACK = "boost_sp_attack"
    BOOST_SP_DEFENSE = "boost_sp_defense"
    BOOST_SPEED = "boost_speed"
    HEAL = "heal"


@dataclass(frozen=True, slots=True)
class Move:
    name: str
    type: PokemonType
    category: MoveCategory
    power: int
    accuracy: int  # percentage; 0 = never misses
    pp: int
    priority: int = 0
    effect: StatusEffect | None = None
    effect_stages: int = 0
    description: str = ""


# (physical strong, physical reliable, special strong, special reliable)
_TYPE_MOVES: dict[PokemonType, tuple[Move, Move, Move, Move]] = {
    PokemonType.NORMAL: (
        Move("Giga Impact", PokemonType.NORMAL, MoveCategory.PHYSICAL, 150, 90, 5),
        Move("Body Slam", PokemonType.NORMAL, MoveCategory.PHYSICAL, 85, 100, 15),
        Move("Hyper Beam", PokemonType.NORMAL, MoveCategory.SPECIAL, 150, 90, 5),
        Move("Hyper Voice", PokemonType.NORMAL, MoveCategory.SPECIAL, 90, 100, 10),
    ),
    PokemonType.FIRE: (
        Move("Flare Blitz", PokemonType.FIRE, MoveCategory.PHYSICAL, 120, 100, 15),
        Move("Fire Punch", PokemonType.FIRE, MoveCategory.PHYSICAL, 75, 100, 15),
        Move("Fire Blast", PokemonType.FIRE, MoveCategory.SPECIAL, 110, 85, 5),
        Move("Flamethrower", PokemonType.FIRE, MoveCategory.SPECIAL, 90, 100, 15),
    ),
    PokemonType.WATER: (
        Move("Liquidation", PokemonType.WATER, MoveCategory.PHYSICAL, 85, 100, 10),
        Move("Waterfall", PokemonType.WATER, MoveCategory.PHYSICAL, 80, 100, 15),
        Move("Hydro Pump", PokemonType.WATER, MoveCategory.SPECIAL, 110, 80, 5),
        Move("Surf", PokemonType.WATER, MoveCategory.SPECIAL, 90, 100, 15),
    ),
    PokemonType.GRASS: (
        Move("Wood Hammer", PokemonType.GRASS, MoveCategory.PHYSICAL, 120, 100, 15),
        Move("Leaf Blade", PokemonType.GRASS, MoveCategory.PHYSICAL, 90, 100, 15),
        Move("Leaf Storm", PokemonType.GRASS, MoveCategory.SPECIAL, 130, 90, 5),
        Move("Energy Ball", PokemonType.GRASS, MoveCategory.SPECIAL, 90, 100, 10),
    ),
    PokemonType.ELECTRIC: (
        Move("Volt Tackle", PokemonType.ELECTRIC, MoveCategory.PHYSICAL, 120, 100, 15),
        Move("Wild Charge", PokemonType.ELECTRIC, MoveCategory.PHYSICAL, 90, 100, 15),
        Move("Thunder", PokemonType.ELECTRIC, MoveCategory.SPECIAL, 110, 70, 10),
        Move("Thunderbolt", PokemonType.ELECTRIC, MoveCategory.SPECIAL, 90, 100, 15),
    ),
    PokemonType.ICE: (
        Move("Icicle Crash", PokemonType.ICE, MoveCategory.PHYSICAL, 85, 90, 10),
        Move("Ice Punch", PokemonType.ICE, MoveCategory.PHYSICAL, 75, 100, 15),
        Move("Blizzard", PokemonType.ICE, MoveCategory.SPECIAL, 110, 70, 5),
        Move("Ice Beam", PokemonType.ICE, MoveCategory.SPECIAL, 90, 100, 10),
    ),
    PokemonType.FIGHTING: (
        Move("Close Combat", PokemonType.FIGHTING, MoveCategory.PHYSICAL, 120, 100, 5),
        Move("Brick Break", PokemonType.FIGHTING, MoveCategory.PHYSICAL, 75, 100, 15),
        Move("Focus Blast", PokemonType.FIGHTING, MoveCategory.SPECIAL, 120, 70, 5),
        Move("Aura Sphere", PokemonType.FIGHTING, MoveCategory.SPECIAL, 80, 0, 20),
    ),
    PokemonType.POISON: (
        Move("Gunk Shot", PokemonType.POISON, MoveCategory.PHYSICAL, 120, 80, 5),
        Move("Poison Jab", PokemonType.POISON, MoveCategory.PHYSICAL, 80, 100, 20),
        Move("Sludge Wave", PokemonType.POISON, MoveCategory.SPECIAL, 95, 100, 10),
        Move("Sludge Bomb", PokemonType.POISON, MoveCategory.SPECIAL, 90, 100, 10),
    ),
    PokemonType.GROUND: (
        Move("Earthquake", PokemonType.GROUND, MoveCategory.PHYSICAL, 100, 100, 10),
        Move("Drill Run", PokemonType.GROUND, MoveCategory.PHYSICAL, 80, 95, 10),
        Move("Earth Power", PokemonType.GROUND, MoveCategory.SPECIAL, 90, 100, 10),
        Move("Mud Shot", PokemonType.GROUND, MoveCategory.SPECIAL, 55, 95, 15),
    ),
    PokemonType.FLYING: (
        Move("Brave Bird", PokemonType.FLYING, MoveCategory.PHYSICAL, 120, 100, 15),
        Move("Drill Peck", PokemonType.FLYING, MoveCategory.PHYSICAL, 80, 100, 20),
        Move("Hurricane", PokemonType.FLYING, MoveCategory.SPECIAL, 110, 70, 10),
        Move("Air Slash", PokemonType.FLYING, MoveCategory.SPECIAL, 75, 95, 15),
    ),
    PokemonType.PSYCHIC: (
        Move("Zen Headbutt", PokemonType.PSYCHIC, MoveCategory.PHYSICAL, 80, 90, 15),
        Move("Psycho Cut", PokemonType.PSYCHIC, MoveCategory.PHYSICAL, 70, 100, 20),
        Move("Psystrike", PokemonType.PSYCHIC, MoveCategory.SPECIAL, 100, 100, 10),
        Move("Psychic", PokemonType.PSYCHIC, MoveCategory.SPECIAL, 90, 100, 10),
    ),
    PokemonType.BUG: (
        Move("Megahorn", PokemonType.BUG, MoveCategory.PHYSICAL, 120, 85, 10),
        Move("X-Scissor", PokemonType.BUG, MoveCategory.PHYSICAL, 80, 100, 15),
        Move("Bug Buzz", PokemonType.BUG, MoveCategory.SPECIAL, 90, 100, 10),
        Move("Signal Beam", PokemonType.BUG, MoveCategory.SPECIAL, 75, 100, 15),
    ),
    PokemonType.ROCK: (
        Move("Head Smash", PokemonType.ROCK, MoveCategory.PHYSICAL, 150, 80, 5),
        Move("Rock Slide", PokemonType.ROCK, MoveCategory.PHYSICAL, 75, 90, 10),
        Move("Power Gem", PokemonType.ROCK, MoveCategory.SPECIAL, 80, 100, 20),
        Move("Ancient Power", PokemonType.ROCK, MoveCategory.SPECIAL, 60, 100, 5),
    ),
    PokemonType.GHOST: (
        Move("Phantom Force", PokemonType.GHOST, MoveCategory.PHYSICAL, 90, 100, 10),
        Move("Shadow Claw", PokemonType.GHOST, MoveCategory.PHYSICAL, 70, 100, 15),
        Move("Shadow Ball", PokemonType.GHOST, MoveCategory.SPECIAL, 80, 100, 15),
        Move("Hex", PokemonType.GHOST, MoveCategory.SPECIAL, 65, 100, 10),
    ),
    PokemonType.DRAGON: (
        Move("Outrage", PokemonType.DRAGON, MoveCategory.PHYSICAL, 120, 100, 10),
        Move("Dragon Claw", PokemonType.DRAGON, MoveCategory.PHYSICAL, 80, 100, 15),
        Move("Draco Meteor", PokemonType.DRAGON, MoveCategory.SPECIAL, 130, 90, 5),
        Move("Dragon Pulse", PokemonType.DRAGON, MoveCategory.SPECIAL, 85, 100, 10),
    ),
    PokemonType.DARK: (
        Move("Foul Play", PokemonType.DARK, MoveCategory.PHYSICAL, 95, 100, 15),
        Move("Crunch", PokemonType.DARK, MoveCategory.PHYSICAL, 80, 100, 15),
        Move("Dark Pulse", PokemonType.DARK, MoveCategory.SPECIAL, 80, 100, 15),
        Move("Snarl", PokemonType.DARK, MoveCategory.SPECIAL, 55, 95, 15),
    ),
    PokemonType.STEEL: (
        Move("Meteor Mash", PokemonType.STEEL, MoveCategory.PHYSICAL, 90, 90, 10),
        Move("Iron Head", PokemonType.STEEL, MoveCategory.PHYSICAL, 80, 100, 15),
        Move("Steel Beam", PokemonType.STEEL, MoveCategory.SPECIAL, 140, 95, 5),
        Move("Flash Cannon", PokemonType.STEEL, MoveCategory.SPECIAL, 80, 100, 10),
    ),
    PokemonType.FAIRY: (
        Move("Play Rough", PokemonType.FAIRY, MoveCategory.PHYSICAL, 90, 90, 10),
        Move("Spirit Break", PokemonType.FAIRY, MoveCategory.PHYSICAL, 75, 100, 15),
        Move("Moonblast", PokemonType.FAIRY, MoveCategory.SPECIAL, 95, 100, 15),
        Move("Dazzling Gleam", PokemonType.FAIRY, MoveCategory.SPECIAL, 80, 100, 10),
    ),
}

QUICK_ATTACK = Move(
    "Quick Attack",
    PokemonType.NORMAL,
    MoveCategory.PHYSICAL,
    40,
    100,
    30,
    priority=1,
    description="Always strikes first.",
)

_STATUS_MOVES: dict[StatusEffect, Move] = {
    StatusEffect.BOOST_ATTACK: Move(
        "Swords Dance",
        PokemonType.NORMAL,
        MoveCategory.STATUS,
        0,
        0,
        20,
        effect=StatusEffect.BOOST_ATTACK,
        effect_stages=2,
        description="Sharply raises Attack.",
    ),
    StatusEffect.BOOST_SP_ATTACK: Move(
        "Nasty Plot",
        PokemonType.DARK,
        MoveCategory.STATUS,
        0,
        0,
        20,
        effect=StatusEffect.BOOST_SP_ATTACK,
        effect_stages=2,
        description="Sharply raises Sp. Atk.",
    ),
    StatusEffect.BOOST_DEFENSE: Move(
        "Iron Defense",
        PokemonType.STEEL,
        MoveCategory.STATUS,
        0,
        0,
        15,
        effect=StatusEffect.BOOST_DEFENSE,
        effect_stages=2,
        description="Sharply raises Defense.",
    ),
    StatusEffect.BOOST_SP_DEFENSE: Move(
        "Amnesia",
        PokemonType.PSYCHIC,
        MoveCategory.STATUS,
        0,
        0,
        20,
        effect=StatusEffect.BOOST_SP_DEFENSE,
        effect_stages=2,
        description="Sharply raises Sp. Def.",
    ),
    StatusEffect.BOOST_SPEED: Move(
        "Agility",
        PokemonType.PSYCHIC,
        MoveCategory.STATUS,
        0,
        0,
        30,
        effect=StatusEffect.BOOST_SPEED,
        effect_stages=2,
        description="Sharply raises Speed.",
    ),
    StatusEffect.HEAL: Move(
        "Recover",
        PokemonType.NORMAL,
        MoveCategory.STATUS,
        0,
        0,
        10,
        effect=StatusEffect.HEAL,
        description="Restores half of max HP.",
    ),
}


def _attacking_moves(record: PokemonRecord, type_: PokemonType) -> tuple[Move, Move]:
    strong_phys, reliable_phys, strong_spec, reliable_spec = _TYPE_MOVES[type_]
    if record.attack >= record.sp_attack:
        return strong_phys, reliable_phys
    return strong_spec, reliable_spec


def _status_move(record: PokemonRecord, rng: random.Random) -> Move:
    bulk = record.hp + record.defense + record.sp_defense
    offense = max(record.attack, record.sp_attack)
    candidates: list[StatusEffect] = []
    if bulk > offense * 2.2:
        candidates.append(StatusEffect.HEAL)
    if record.attack >= record.sp_attack:
        candidates.append(StatusEffect.BOOST_ATTACK)
    else:
        candidates.append(StatusEffect.BOOST_SP_ATTACK)
    if record.speed < 70:
        candidates.append(StatusEffect.BOOST_SPEED)
    if record.defense < record.sp_defense:
        candidates.append(StatusEffect.BOOST_DEFENSE)
    else:
        candidates.append(StatusEffect.BOOST_SP_DEFENSE)
    return _STATUS_MOVES[rng.choice(candidates)]


def build_moveset(record: PokemonRecord) -> list[Move]:
    """Return four moves for ``record``. Deterministic per Pokédex number."""
    rng = random.Random(record.pokedex_number * 7919)
    strong, reliable = _attacking_moves(record, record.type1)
    moves: list[Move] = [strong, reliable]

    if record.type2 is not None:
        moves.append(_attacking_moves(record, record.type2)[1])
    elif record.speed >= 90:
        moves.append(QUICK_ATTACK)
    else:
        moves.append(_attacking_moves(record, PokemonType.NORMAL)[1])

    moves.append(_status_move(record, rng))

    # De-duplicate by name (e.g. Normal/Flying would otherwise repeat Body Slam).
    seen: set[str] = set()
    unique: list[Move] = []
    for m in moves:
        if m.name not in seen:
            seen.add(m.name)
            unique.append(m)
    while len(unique) < 4:
        filler = QUICK_ATTACK if QUICK_ATTACK.name not in seen else _STATUS_MOVES[StatusEffect.HEAL]
        seen.add(filler.name)
        unique.append(filler)
    return unique[:4]
