from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from app.agents.heuristic import HeuristicAgent
from app.config import BACKEND_ROOT, Settings
from app.data.loader import load_pokemon_csv
from app.data.repository import PokemonRepository
from app.main import create_app
from app.services.battle_service import BattleService


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        opponent_agent="heuristic",
        anthropic_api_key=None,
        pokemon_csv_path=BACKEND_ROOT / "data" / "pokemon.csv",
    )


@pytest.fixture(scope="session")
def repo(settings: Settings) -> PokemonRepository:
    return PokemonRepository(load_pokemon_csv(settings.pokemon_csv_path))


@pytest.fixture
def service(repo: PokemonRepository, settings: Settings) -> BattleService:
    rng = random.Random(1234)
    return BattleService(repo, HeuristicAgent(rng), settings, rng=rng)


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings)) as c:
        yield c
