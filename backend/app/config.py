"""Application settings, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent

AgentChoice = Literal["auto", "heuristic", "claude", "claude_code"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pokemon_csv_path: Path = Field(default=BACKEND_ROOT / "data" / "pokemon.csv")

    # Which brain plays the opposing trainer.
    #   auto        -> claude if ANTHROPIC_API_KEY is set, else claude_code if the CLI is
    #                  installed, else heuristic
    #   claude      -> Anthropic Messages API (needs ANTHROPIC_API_KEY)
    #   claude_code -> `claude -p` CLI using your Claude subscription login
    #   heuristic   -> built-in rule-based trainer, no LLM
    opponent_agent: AgentChoice = "auto"
    anthropic_api_key: str | None = None
    # The one model every LLM call in the app uses (API and Claude Code CLI paths alike).
    # Claude Haiku 4.5 is the cheapest model.
    opponent_model: str = "claude-haiku-4-5"
    opponent_effort: str = "low"  # only sent to models that support it
    opponent_timeout_seconds: float = 90.0
    claude_code_bin: str = "claude"

    def model_for(self, agent_name: str) -> str | None:
        """The model a given agent uses, for the health endpoint."""
        return self.opponent_model if agent_name in ("claude", "claude_code") else None

    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    battle_level: int = 50
    max_team_size: int = 4  # doubles: 2 on the field + 2 on the bench

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
