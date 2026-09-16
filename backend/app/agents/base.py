"""Contract every opposing-trainer agent implements.

In a double battle the service calls the agent once per active opponent Pokémon
(``position`` 0 and 1) concurrently, so each Pokémon is driven by its own decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.battle import Action, BattleState


@dataclass(frozen=True, slots=True)
class Decision:
    action: Action
    taunt: str
    reasoning: str
    source: str  # which agent produced it (e.g. "claude", "claude_code", "heuristic")


class OpponentAgent(Protocol):
    name: str

    async def choose_action(self, state: BattleState, position: int = 0) -> Decision:
        """Pick a move (with target) or switch for the opponent Pokémon at ``position``."""

    async def choose_replacement(
        self, state: BattleState, position: int = 0, exclude: frozenset[int] = frozenset()
    ) -> Decision:
        """Pick a bench slot to fill ``position`` after a faint. ``exclude`` holds slots
        already promised to another position this turn."""

    async def advise(self, state: BattleState, position: int = 0) -> Decision:
        """Coach mode: recommend what the *player's* Pokémon at ``position`` should do."""
