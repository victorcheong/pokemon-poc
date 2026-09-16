"""FastAPI dependency wiring. Singletons are created once at startup in ``main``."""

from __future__ import annotations

from fastapi import Request

from app.data.repository import PokemonRepository
from app.services.battle_service import BattleService


def get_repository(request: Request) -> PokemonRepository:
    return request.app.state.repository


def get_battle_service(request: Request) -> BattleService:
    return request.app.state.battle_service
