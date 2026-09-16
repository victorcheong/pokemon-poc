"""CSV loading for the Kaggle dataset (https://www.kaggle.com/datasets/rounakbanik/pokemon).

The parser is deliberately defensive: the source CSV has a few quirks
(the ``classfication`` typo, ``capture_rate`` containing a non-numeric value for
Minior, blank ``type2`` and ``weight_kg`` cells).
"""

from __future__ import annotations

import ast
import csv
import logging
from pathlib import Path

from app.data.models import PokemonRecord
from app.domain.types import ALL_TYPES, PokemonType

log = logging.getLogger(__name__)

# Dataset column suffixes differ slightly from canonical type names.
_AGAINST_COLUMN_FOR_TYPE: dict[PokemonType, str] = {
    **{t: f"against_{t.value}" for t in ALL_TYPES},
    PokemonType.FIGHTING: "against_fight",
}


def _int(value: str, default: int | None = None) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_abilities(raw: str) -> tuple[str, ...]:
    try:
        parsed = ast.literal_eval(raw)
        return tuple(str(a) for a in parsed)
    except (ValueError, SyntaxError):
        return ()


def _parse_type(raw: str | None) -> PokemonType | None:
    if not raw:
        return None
    try:
        return PokemonType(raw.strip().lower())
    except ValueError:
        return None


def parse_row(row: dict[str, str]) -> PokemonRecord:
    type1 = _parse_type(row.get("type1"))
    if type1 is None:
        raise ValueError(f"Row {row.get('name')!r} has no valid type1")

    against: dict[PokemonType, float] = {}
    for t, col in _AGAINST_COLUMN_FOR_TYPE.items():
        mult = _float(row.get(col, ""))
        against[t] = mult if mult is not None else 1.0

    return PokemonRecord(
        pokedex_number=_int(row["pokedex_number"]) or 0,
        name=row["name"].strip(),
        japanese_name=row.get("japanese_name", "").strip(),
        classification=row.get("classfication", row.get("classification", "")).strip(),
        type1=type1,
        type2=_parse_type(row.get("type2")),
        hp=_int(row["hp"]) or 1,
        attack=_int(row["attack"]) or 1,
        defense=_int(row["defense"]) or 1,
        sp_attack=_int(row["sp_attack"]) or 1,
        sp_defense=_int(row["sp_defense"]) or 1,
        speed=_int(row["speed"]) or 1,
        base_total=_int(row["base_total"]) or 0,
        height_m=_float(row.get("height_m", "")),
        weight_kg=_float(row.get("weight_kg", "")),
        generation=_int(row.get("generation", "1")) or 1,
        is_legendary=(_int(row.get("is_legendary", "0")) or 0) == 1,
        capture_rate=_int(row.get("capture_rate", "")),
        abilities=_parse_abilities(row.get("abilities", "")),
        against=against,
    )


def load_pokemon_csv(path: Path) -> list[PokemonRecord]:
    if not path.exists():
        raise FileNotFoundError(
            f"Pokémon dataset not found at {path}. Download pokemon.csv from "
            "https://www.kaggle.com/datasets/rounakbanik/pokemon and place it there."
        )
    records: list[PokemonRecord] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                records.append(parse_row(row))
            except (KeyError, ValueError) as exc:
                log.warning("Skipping malformed row %s: %s", row.get("name"), exc)
    records.sort(key=lambda r: r.pokedex_number)
    log.info("Loaded %d Pokémon from %s", len(records), path)
    return records
