"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.factory import build_agent
from app.api import battles, pokemon, trainers
from app.config import Settings, get_settings
from app.data.loader import load_pokemon_csv
from app.data.repository import PokemonRepository
from app.schemas import HealthOut
from app.services.battle_service import BattleService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

API_PREFIX = "/api"

DESCRIPTION = """
Battle simulator over the Kaggle **Complete Pokémon Dataset** (801 Pokémon) with an
LLM-driven opposing trainer.

* **pokemon** – browse the Pokédex, stats, weaknesses and generated movesets.
* **trainers** – the roster of opponents you can challenge.
* **battles** – start a single (1v1) or double (2v2) battle and play it turn by turn.
  In doubles each opponent Pokémon is driven by its own agent decision.
* **meta** – health and which agent is active (`claude_code`, `claude` or `heuristic`).
"""

TAGS = [
    {"name": "pokemon", "description": "Pokédex data from the Kaggle dataset."},
    {"name": "trainers", "description": "Opposing trainers, their types and difficulty."},
    {"name": "battles", "description": "Create battles and play turns."},
    {"name": "meta", "description": "Service status."},
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repo = PokemonRepository(load_pokemon_csv(settings.pokemon_csv_path))
        agent = build_agent(settings)
        app.state.settings = settings
        app.state.repository = repo
        app.state.battle_service = BattleService(repo, agent, settings)
        yield

    app = FastAPI(
        title="Pokémon Battle API",
        description=DESCRIPTION,
        version="0.2.0",
        openapi_tags=TAGS,
        lifespan=lifespan,
        # Served under /api so the nginx frontend proxies them too:
        #   Swagger UI  -> /api/docs      ReDoc -> /api/redoc      schema -> /api/openapi.json
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(pokemon.router, prefix=API_PREFIX)
    app.include_router(pokemon.types_router, prefix=API_PREFIX)
    app.include_router(trainers.router, prefix=API_PREFIX)
    app.include_router(battles.router, prefix=API_PREFIX)

    @app.get(f"{API_PREFIX}/health", response_model=HealthOut, tags=["meta"], summary="Health")
    def health() -> HealthOut:
        agent_name = app.state.battle_service.agent_name
        return HealthOut(
            status="ok",
            pokemon_loaded=len(app.state.repository),
            opponent_agent=agent_name,
            model=settings.model_for(agent_name),
        )

    return app


app = create_app()
