"""In-memory repository over the loaded dataset."""

from __future__ import annotations

import random
from collections.abc import Iterable

from app.data.models import PokemonRecord
from app.domain.types import PokemonType


class PokemonRepository:
    def __init__(self, records: Iterable[PokemonRecord]):
        self._by_id: dict[int, PokemonRecord] = {r.pokedex_number: r for r in records}
        self._ordered: list[PokemonRecord] = sorted(
            self._by_id.values(), key=lambda r: r.pokedex_number
        )

    def __len__(self) -> int:
        return len(self._ordered)

    def all(self) -> list[PokemonRecord]:
        return list(self._ordered)

    def get(self, pokedex_number: int) -> PokemonRecord | None:
        return self._by_id.get(pokedex_number)

    def get_many(self, ids: Iterable[int]) -> list[PokemonRecord]:
        out: list[PokemonRecord] = []
        for i in ids:
            rec = self.get(i)
            if rec is None:
                raise KeyError(i)
            out.append(rec)
        return out

    def search(
        self,
        *,
        query: str | None = None,
        type_: PokemonType | None = None,
        generation: int | None = None,
        include_legendary: bool = True,
    ) -> list[PokemonRecord]:
        q = (query or "").strip().lower()
        results = []
        for r in self._ordered:
            if q and q not in r.name.lower() and q != str(r.pokedex_number):
                continue
            if type_ is not None and type_ not in r.types:
                continue
            if generation is not None and r.generation != generation:
                continue
            if not include_legendary and r.is_legendary:
                continue
            results.append(r)
        return results

    def pick_team(
        self,
        rng: random.Random,
        *,
        size: int,
        preferred_types: Iterable[PokemonType],
        target_base_total: int,
        allow_legendary: bool,
        exclude: Iterable[int] = (),
    ) -> list[PokemonRecord]:
        """Pick a themed team whose strength roughly matches ``target_base_total``."""
        preferred = set(preferred_types)
        excluded = set(exclude)
        window = 60
        pool: list[PokemonRecord] = []
        while len(pool) < size * 3 and window <= 400:
            pool = [
                r
                for r in self._ordered
                if r.pokedex_number not in excluded
                and (allow_legendary or not r.is_legendary)
                and (not preferred or preferred & set(r.types))
                and abs(r.base_total - target_base_total) <= window
            ]
            window += 40
        if len(pool) < size:  # fall back to any type
            pool = [
                r
                for r in self._ordered
                if r.pokedex_number not in excluded
                and (allow_legendary or not r.is_legendary)
                and abs(r.base_total - target_base_total) <= window
            ]
        chosen = rng.sample(pool, k=min(size, len(pool)))
        return chosen
