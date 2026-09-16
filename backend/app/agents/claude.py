"""Claude-powered opposing trainer via the Anthropic Messages API.

One call per decision with structured outputs (JSON schema) and prompt caching on the
system prompt. Model-dependent extras are only sent where the model supports them:
``effort`` (Opus 4.5+, Sonnet 5, Fable) and server-side refusal fallbacks (Opus 5 / Fable).
The default model is Claude Haiku 4.5, the cheapest option. Requires ``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import anthropic

from app.agents.decision import DECISION_SCHEMA, TrainerDecision
from app.agents.heuristic import HeuristicAgent
from app.agents.llm_base import LLMTrainerAgent
from app.config import Settings
from app.domain.battle import BattleState, Side


def supports_effort(model: str) -> bool:
    """`output_config.effort` is accepted by Opus 4.5+, Sonnet 5 and the Fable family."""
    m = model.lower()
    return any(k in m for k in ("opus", "sonnet-5", "fable", "mythos"))


def supports_fallbacks(model: str) -> bool:
    """Server-side refusal fallbacks exist for Opus 5 and the Fable/Mythos tier."""
    m = model.lower()
    return any(k in m for k in ("opus-5", "fable", "mythos"))


class ClaudeAgent(LLMTrainerAgent):
    name = "claude"

    def __init__(self, settings: Settings, fallback: HeuristicAgent | None = None):
        super().__init__(fallback)
        self._settings = settings
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.opponent_timeout_seconds,
            max_retries=1,
        )

    async def ask(
        self, state: BattleState, briefing: str, instruction: str, side: Side = "opponent"
    ) -> TrainerDecision:
        system = [
            {
                "type": "text",
                "text": self.system_prompt(state, side),
                "cache_control": {"type": "ephemeral"},
            }
        ]
        model = self._settings.opponent_model
        output_config: dict = {"format": {"type": "json_schema", "schema": DECISION_SCHEMA}}
        if supports_effort(model):
            output_config["effort"] = self._settings.opponent_effort
        kwargs: dict = {
            "model": model,
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": f"{briefing}\n\n{instruction}"}],
            "output_config": output_config,
        }
        if supports_fallbacks(model):
            response = await self._client.beta.messages.create(
                **kwargs, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        else:
            response = await self._client.messages.create(**kwargs)
        if response.stop_reason == "refusal":
            raise ValueError("model refused the request")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise ValueError("no text block in response")
        return TrainerDecision.model_validate_json(text)
