"""Rule-based trainer: no external calls. Used for tests, as a fallback, and as the coach
when no LLM is available. Works for either side."""

from __future__ import annotations

import random

from app.agents.base import Decision
from app.domain.battle import (
    STAT_FOR_EFFECT,
    BattlePokemon,
    BattleState,
    ItemAction,
    MoveAction,
    Side,
    SwitchAction,
    expected_damage,
    opposite,
)
from app.domain.items import ITEMS
from app.domain.moves import Move, MoveCategory, StatusEffect


def _best_hit(attacker: BattlePokemon, defender: BattlePokemon) -> float:
    return max(
        (
            expected_damage(attacker, defender, m)
            for m in attacker.moves
            if m.category is not MoveCategory.STATUS
        ),
        default=0.0,
    )


class HeuristicAgent:
    name = "heuristic"

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    async def choose_action(
        self, state: BattleState, position: int = 0, side: Side = "opponent"
    ) -> Decision:
        foe_side = opposite(side)
        me = state.active(side, position)
        foes = [(p, state.active(foe_side, p)) for p in state.living_positions(foe_side)]
        usable = me.usable_move_indices() or [0]
        speaker = state.trainer.name if side == "opponent" else "Coach"

        # Score every (move, target) pair.
        best_score, best_idx, best_target = float("-inf"), usable[0], None
        for i in usable:
            move = me.moves[i]
            if move.category is MoveCategory.STATUS:
                ref = foes[0][1] if foes else me
                score, target = self._status_score(me, ref, move), None
                if score > best_score:
                    best_score, best_idx, best_target = score, i, target
                continue
            for pos, foe in foes:
                dmg = expected_damage(me, foe, move)
                score = min(dmg, foe.current_hp) + (5 if dmg >= foe.current_hp else 0)
                score += move.priority * 3
                if score > best_score:
                    best_score, best_idx, best_target = score, i, pos

        incoming_threat = max((_best_hit(foe, me) for _, foe in foes), default=0.0)
        strongest_foe_hp = max((foe.current_hp for _, foe in foes), default=0)

        # Player only: a healing item when we'd otherwise faint and we can survive after it.
        if side == "player" and incoming_threat >= me.current_hp and best_score < strongest_foe_hp:
            for key, count in state.player_items.items():
                item = ITEMS[key]
                heal = me.max_hp - me.current_hp if item.heal == 0 else item.heal
                if count > 0 and me.current_hp + heal > incoming_threat:
                    return Decision(
                        ItemAction("item", key),
                        f"{speaker}: use a {item.name} on {me.name}!",
                        f"{me.name} would faint to the foe's best hit; {item.name} keeps it "
                        "alive for another exchange.",
                        self.name,
                    )

        # Switch if the matchup is hopeless and a bench-mate does clearly better.
        if incoming_threat >= me.current_hp and best_score < strongest_foe_hp:
            for slot in state.available_switches(side):
                cand = state.team(side)[slot]
                cand_best = max((_best_hit(cand, foe) for _, foe in foes), default=0.0)
                cand_threat = max((_best_hit(foe, cand) for _, foe in foes), default=0.0)
                if cand_best > best_score and cand_threat < cand.current_hp:
                    return Decision(
                        SwitchAction("switch", slot),
                        f"{speaker}: {me.name}, come back! Go, {cand.name}!",
                        f"{me.name} would be knocked out; {cand.name} has a better matchup.",
                        self.name,
                    )

        move = me.moves[best_idx]
        target_name = (
            f" on {state.active(foe_side, best_target).name}" if best_target is not None else ""
        )
        return Decision(
            MoveAction("move", best_idx, best_target),
            f"{speaker}: {me.name}, use {move.name}{target_name}!",
            f"Highest expected value among usable moves (score {best_score:.0f}).",
            self.name,
        )

    async def choose_replacement(
        self,
        state: BattleState,
        position: int = 0,
        exclude: frozenset[int] = frozenset(),
        side: Side = "opponent",
    ) -> Decision:
        foe_side = opposite(side)
        foes = [state.active(foe_side, p) for p in state.living_positions(foe_side)]
        best_slot, best_score = None, float("-inf")
        for slot in state.available_switches(side):
            if slot in exclude:
                continue
            cand = state.team(side)[slot]
            offense = max((_best_hit(cand, foe) for foe in foes), default=0.0)
            threat = max((_best_hit(foe, cand) for foe in foes), default=0.0)
            score = offense - 0.5 * threat + cand.current_hp * 0.1
            if score > best_score:
                best_slot, best_score = slot, score
        if best_slot is None:
            raise ValueError("No replacement available")
        cand = state.team(side)[best_slot]
        speaker = state.trainer.name if side == "opponent" else "Coach"
        return Decision(
            SwitchAction("switch", best_slot),
            f"{speaker}: Go, {cand.name}!",
            "Best offense-to-risk ratio among the remaining team.",
            self.name,
        )

    async def advise(self, state: BattleState, position: int = 0) -> Decision:
        """Recommend an action for the player's Pokémon at ``position``."""
        if state.active(("player"), position).fainted:
            return await self.choose_replacement(state, position, side="player")
        return await self.choose_action(state, position, side="player")

    @staticmethod
    def _status_score(me: BattlePokemon, foe: BattlePokemon, move: Move) -> float:
        """Value of a status move relative to damage numbers (foe HP units)."""
        if move.effect is StatusEffect.HEAL:
            return foe.max_hp * 0.5 if me.hp_fraction < 0.45 else 0.0
        stat = STAT_FOR_EFFECT.get(move.effect) if move.effect else None
        if stat is None:
            return 0.0
        stage = me.stages[stat]
        if stage >= 6:
            return 0.0  # can't go higher
        # Setting up early is worth about a third of a KO, less the more we've already boosted.
        if me.hp_fraction > 0.7:
            return foe.max_hp * 0.35 * max(0.0, (4 - stage) / 4)
        return 0.0
