from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.data.repository import PokemonRepository
from app.dependencies import get_repository
from app.domain.types import TYPE_COLORS, PokemonType
from app.schemas import PokemonDetail, PokemonPage, PokemonSummary, TypeInfo

router = APIRouter(prefix="/pokemon", tags=["pokemon"])


@router.get("", response_model=PokemonPage, summary="Search the Pokédex")
def list_pokemon(
    repo: Annotated[PokemonRepository, Depends(get_repository)],
    q: Annotated[str | None, Query(description="Name or Pokédex number")] = None,
    type: Annotated[PokemonType | None, Query()] = None,  # noqa: A002 - matches query param name
    generation: Annotated[int | None, Query(ge=1, le=9)] = None,
    include_legendary: bool = True,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PokemonPage:
    results = repo.search(
        query=q, type_=type, generation=generation, include_legendary=include_legendary
    )
    page = results[offset : offset + limit]
    return PokemonPage(items=[PokemonSummary.from_record(r) for r in page], total=len(results))


@router.get(
    "/{pokedex_number}",
    response_model=PokemonDetail,
    summary="Pokémon details",
    responses={404: {"description": "Unknown Pokédex number"}},
)
def get_pokemon(
    pokedex_number: int, repo: Annotated[PokemonRepository, Depends(get_repository)]
) -> PokemonDetail:
    record = repo.get(pokedex_number)
    if record is None:
        raise HTTPException(status_code=404, detail="Pokémon not found")
    return PokemonDetail.from_record(record)


types_router = APIRouter(prefix="/types", tags=["pokemon"])


@types_router.get("", response_model=list[TypeInfo], summary="Type colours")
def list_types() -> list[TypeInfo]:
    return [TypeInfo(type=t, color=c) for t, c in TYPE_COLORS.items()]
