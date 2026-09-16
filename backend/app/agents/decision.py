"""Shared decision contract for LLM-backed trainers (API and Claude Code CLI)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.battle import Action, BattleState, ItemAction, MoveAction, Side, SwitchAction
from app.domain.items import ITEMS
from app.domain.trainers import Trainer


class TrainerDecision(BaseModel):
    """The JSON object the model must return each turn."""

    action: Literal["move", "switch", "item"]
    move_index: int | None = Field(
        default=None, description="Index of the move to use (0-3) when action is 'move'."
    )
    target_position: int | None = Field(
        default=None,
        description="Foe position to hit (0 or 1) in a double battle; null in singles.",
    )
    switch_slot: int | None = Field(
        default=None, description="Team slot to switch to when action is 'switch'."
    )
    item: str | None = Field(
        default=None, description="Bag item id when action is 'item' (player/coach only)."
    )
    taunt: str = Field(
        description="One short in-character line said out loud to the challenger (max 120 chars)."
    )
    reasoning: str = Field(description="One or two sentences on why this is the best play.")


DECISION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["move", "switch", "item"]},
        "move_index": {"type": ["integer", "null"]},
        "target_position": {"type": ["integer", "null"]},
        "switch_slot": {"type": ["integer", "null"]},
        "item": {"type": ["string", "null"]},
        "taunt": {"type": "string"},
        "reasoning": {"type": "string"},
    },
    "required": [
        "action",
        "move_index",
        "target_position",
        "switch_slot",
        "item",
        "taunt",
        "reasoning",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are an expert Pokémon trainer playing a battle against a challenger.
You control ONE Pokémon on the OPPONENT side (in a double battle your partner Pokémon is
decided separately, so coordinate by reading the briefing rather than assuming its move).
Each turn you receive a briefing with exact HP, stats, type effectiveness and expected
damage numbers for every option. Choose the action that maximises your chance of winning
the whole battle, not just this turn:
- Prefer moves that knock a foe out this turn.
- Weigh accuracy: a 70% move that KOs is often worse than a 100% move that nearly does.
- In doubles pick the target_position that gives the best result (finish weakened foes,
  remove the biggest threat).
- Set up with stat boosts only when you can afford to take a hit.
- Switch when your Pokémon would faint before doing meaningful damage and a team-mate
  has a clearly better matchup; switching costs you the turn.
- Heal only when it keeps you alive for a favourable trade.

Stay in character as the trainer described below. The "taunt" is spoken aloud to the
challenger, so keep it short, vivid and consistent with the personality. Never reveal
the exact numbers from the briefing in the taunt.

Be decisive: the briefing already contains the numbers, so do not deliberate at length.
Keep "reasoning" to at most two short sentences."""

COACH_PROMPT = """You are a friendly, expert Pokémon battle coach advising the CHALLENGER (the
human player). You receive a briefing from the player's point of view with exact HP, stats,
type effectiveness and expected damage for every option, plus the player's bag. Recommend
the single best action for the Pokémon named in the briefing:
- Prefer moves that knock a foe out this turn; weigh accuracy honestly.
- In doubles choose the target_position that helps most.
- Recommend a bag item ('item' with the item id) only when it prevents a faint and the
  Pokémon can still win the exchange afterwards; using an item costs the turn.
- Recommend a switch when the current matchup is hopeless and a bench-mate is clearly better.
- Do not reveal the foe's exact move names; you may describe them by type and strength.

Write the "taunt" field as one short, encouraging coaching line (max 120 chars) and the
"reasoning" as two short, plain sentences the player can act on. Be decisive: the
briefing already contains the numbers, so do not deliberate at length."""

ACTION_INSTRUCTION = (
    "Decide this Pokémon's action for the turn. Reply with action 'move', a move_index and "
    "(in doubles) a target_position, or action 'switch' and a switch_slot from your bench."
)
COACH_INSTRUCTION = (
    "What should this Pokémon do this turn? Reply with action 'move' (move_index and, in "
    "doubles, target_position), 'switch' (switch_slot) or 'item' (item id from the bag)."
)
COACH_REPLACEMENT_INSTRUCTION = (
    "This Pokémon fainted. Which bench Pokémon should the player send out? Reply with action "
    "'switch' and the switch_slot."
)
REPLACEMENT_INSTRUCTION = (
    "This Pokémon fainted. Choose which bench Pokémon to send out in its place: "
    "reply with action 'switch' and the switch_slot."
)


def trainer_persona(trainer: Trainer) -> str:
    return f"TRAINER: {trainer.name}, {trainer.title}.\nPERSONALITY: {trainer.personality}"


def decision_to_action(
    state: BattleState,
    parsed: TrainerDecision,
    *,
    position: int,
    replacement: bool,
    exclude: frozenset[int] = frozenset(),
    side: Side = "opponent",
) -> Action:
    """Validate the model's choice against the real battle state."""
    foe_side: Side = "player" if side == "opponent" else "opponent"
    if parsed.action == "switch" or replacement:
        slot = parsed.switch_slot
        if slot is None or slot not in state.available_switches(side) or slot in exclude:
            raise ValueError(f"invalid switch slot {slot}")
        return SwitchAction("switch", slot)
    if parsed.action == "item":
        if side != "player":
            raise ValueError("trainers cannot use items")
        item = parsed.item
        if item not in ITEMS or state.player_items.get(item, 0) <= 0:
            raise ValueError(f"invalid item {item}")
        return ItemAction("item", item)
    idx = parsed.move_index
    active = state.active(side, position)
    if idx is None or idx not in active.usable_move_indices():
        raise ValueError(f"invalid move index {idx}")
    target = parsed.target_position
    living = state.living_positions(foe_side)
    if target is not None and target not in living:
        target = None  # engine redirects to a living foe
    return MoveAction("move", idx, target)
