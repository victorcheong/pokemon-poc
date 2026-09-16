"""Pokémon elemental types and the canonical UI colour for each."""

from __future__ import annotations

from enum import StrEnum


class PokemonType(StrEnum):
    NORMAL = "normal"
    FIRE = "fire"
    WATER = "water"
    GRASS = "grass"
    ELECTRIC = "electric"
    ICE = "ice"
    FIGHTING = "fighting"
    POISON = "poison"
    GROUND = "ground"
    FLYING = "flying"
    PSYCHIC = "psychic"
    BUG = "bug"
    ROCK = "rock"
    GHOST = "ghost"
    DRAGON = "dragon"
    DARK = "dark"
    STEEL = "steel"
    FAIRY = "fairy"


ALL_TYPES: tuple[PokemonType, ...] = tuple(PokemonType)

# Bulbapedia / Pokémon Stadium palette, used by the frontend for cards and moves.
TYPE_COLORS: dict[PokemonType, str] = {
    PokemonType.NORMAL: "#A8A878",
    PokemonType.FIRE: "#F08030",
    PokemonType.WATER: "#6890F0",
    PokemonType.GRASS: "#78C850",
    PokemonType.ELECTRIC: "#F8D030",
    PokemonType.ICE: "#98D8D8",
    PokemonType.FIGHTING: "#C03028",
    PokemonType.POISON: "#A040A0",
    PokemonType.GROUND: "#E0C068",
    PokemonType.FLYING: "#A890F0",
    PokemonType.PSYCHIC: "#F85888",
    PokemonType.BUG: "#A8B820",
    PokemonType.ROCK: "#B8A038",
    PokemonType.GHOST: "#705898",
    PokemonType.DRAGON: "#7038F8",
    PokemonType.DARK: "#705848",
    PokemonType.STEEL: "#B8B8D0",
    PokemonType.FAIRY: "#EE99AC",
}
