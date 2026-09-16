"""Template for LLM-backed trainers: briefing -> model -> validated action, with fallback."""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from app.agents.base import Decision
from app.agents.briefing import build_briefing
from app.agents.decision import (
    ACTION_INSTRUCTION,
    COACH_INSTRUCTION,
    COACH_PROMPT,
    COACH_REPLACEMENT_INSTRUCTION,
    REPLACEMENT_INSTRUCTION,
    SYSTEM_PROMPT,
    TrainerDecision,
    decision_to_action,
    trainer_persona,
)
from app.agents.heuristic import HeuristicAgent
from app.domain.battle import BattleState, Side

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"</?[A-Za-z_][\w-]*\s*/?>")


def clean_text(text: str, limit: int) -> str:
    """Strip stray XML/HTML-style tags and anything after a closing tag that smaller models
    occasionally leak into free-text fields, then trim and cap the length."""
    text = text.split("</", 1)[0]
    text = _TAG_RE.sub("", text)
    return " ".join(text.split())[:limit]


class LLMTrainerAgent(ABC):
    name: str = "llm"

    def __init__(self, fallback: HeuristicAgent | None = None):
        self._fallback = fallback or HeuristicAgent()

    async def choose_action(self, state: BattleState, position: int = 0) -> Decision:
        briefing = build_briefing(state, position)
        return await self._decide(state, briefing, ACTION_INSTRUCTION, position=position)

    async def choose_replacement(
        self, state: BattleState, position: int = 0, exclude: frozenset[int] = frozenset()
    ) -> Decision:
        briefing = build_briefing(state, position, for_replacement=True)
        return await self._decide(
            state,
            briefing,
            REPLACEMENT_INSTRUCTION,
            position=position,
            replacement=True,
            exclude=exclude,
        )

    async def advise(self, state: BattleState, position: int = 0) -> Decision:
        if state.active("player", position).fainted:
            briefing = build_briefing(state, position, side="player", for_replacement=True)
            return await self._decide(
                state,
                briefing,
                COACH_REPLACEMENT_INSTRUCTION,
                position=position,
                replacement=True,
                side="player",
            )
        briefing = build_briefing(state, position, side="player")
        return await self._decide(
            state, briefing, COACH_INSTRUCTION, position=position, side="player"
        )

    @staticmethod
    def system_prompt(state: BattleState, side: Side) -> str:
        """Full system prompt for a decision: trainer persona, or the coach prompt."""
        if side == "player":
            return COACH_PROMPT
        return f"{SYSTEM_PROMPT}\n\n{trainer_persona(state.trainer)}"

    @abstractmethod
    async def ask(
        self, state: BattleState, briefing: str, instruction: str, side: Side = "opponent"
    ) -> TrainerDecision:
        """Query the model. Raise on any failure; the caller falls back to the heuristic."""

    async def _decide(
        self,
        state: BattleState,
        briefing: str,
        instruction: str,
        *,
        position: int,
        replacement: bool = False,
        exclude: frozenset[int] = frozenset(),
        side: Side = "opponent",
    ) -> Decision:
        try:
            parsed = await self.ask(state, briefing, instruction, side)
            action = decision_to_action(
                state,
                parsed,
                position=position,
                replacement=replacement,
                exclude=exclude,
                side=side,
            )
            return Decision(
                action, clean_text(parsed.taunt, 160), clean_text(parsed.reasoning, 600), self.name
            )
        except Exception as exc:  # noqa: BLE001 - a broken opponent must never stall the game
            log.warning(
                "%s agent failed (%s: %s); using heuristic fallback",
                self.name,
                type(exc).__name__,
                exc,
            )
        if replacement:
            return await self._fallback.choose_replacement(state, position, exclude, side)
        return await self._fallback.choose_action(state, position, side)
