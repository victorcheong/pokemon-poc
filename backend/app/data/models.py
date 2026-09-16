"""Typed representation of one row of the Kaggle 'Complete Pokemon Dataset'."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.types import PokemonType


@dataclass(frozen=True, slots=True)
class PokemonRecord:
    pokedex_number: int
    name: str
    japanese_name: str
    classification: str
    type1: PokemonType
    type2: PokemonType | None
    hp: int
    attack: int
    defense: int
    sp_attack: int
    sp_defense: int
    speed: int
    base_total: int
    height_m: float | None
    weight_kg: float | None
    generation: int
    is_legendary: bool
    capture_rate: int | None
    abilities: tuple[str, ...] = field(default_factory=tuple)
    # Defensive multipliers keyed by attacking type, straight from the against_* columns.
    against: dict[PokemonType, float] = field(default_factory=dict)

    @property
    def types(self) -> tuple[PokemonType, ...]:
        return (self.type1,) if self.type2 is None else (self.type1, self.type2)

    def effectiveness_against(self, attacking_type: PokemonType) -> float:
        return self.against.get(attacking_type, 1.0)
