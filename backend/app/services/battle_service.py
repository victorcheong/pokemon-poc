"""Orchestrates battle creation, turns and the opposing agent(s). Battles live in memory."""

from __future__ import annotations

import asyncio
import random
import uuid
from collections import OrderedDict
from dataclasses import dataclass

from app.agents.base import Decision, OpponentAgent
from app.config import Settings
from app.data.models import PokemonRecord
from app.data.repository import PokemonRepository
from app.domain.battle import (
    Actions,
    BattleEngine,
    BattleEvent,
    BattleFormat,
    BattlePokemon,
    BattleState,
    Phase,
    SwitchAction,
)
from app.domain.trainers import TRAINERS, Trainer, get_trainer


class BattleNotFoundError(LookupError):
    pass


class InvalidActionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OpponentDecision:
    position: int
    pokemon: str
    decision: Decision


@dataclass(frozen=True, slots=True)
class TurnResult:
    state: BattleState
    events: list[BattleEvent]
    decisions: list[OpponentDecision]


class BattleService:
    def __init__(
        self,
        repo: PokemonRepository,
        agent: OpponentAgent,
        settings: Settings,
        *,
        max_battles: int = 500,
        rng: random.Random | None = None,
    ):
        self._repo = repo
        self._agent = agent
        self._settings = settings
        self._battles: OrderedDict[str, BattleState] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}
        self._max = max_battles
        self._rng = rng or random.Random()

    @property
    def agent_name(self) -> str:
        return self._agent.name

    # ---- lifecycle ---------------------------------------------------------

    def create(
        self, player_ids: list[int], trainer_id: str | None, fmt: BattleFormat
    ) -> TurnResult:
        if not player_ids:
            raise InvalidActionError("Choose at least one Pokémon")
        if fmt is BattleFormat.DOUBLE and len(player_ids) < 2:
            raise InvalidActionError("A double battle needs at least two Pokémon")
        if len(player_ids) > self._settings.max_team_size:
            raise InvalidActionError(f"Team size is limited to {self._settings.max_team_size}")
        if len(set(player_ids)) != len(player_ids):
            raise InvalidActionError("Duplicate Pokémon in team")
        try:
            records = self._repo.get_many(player_ids)
        except KeyError as exc:
            raise InvalidActionError(f"Unknown Pokémon id {exc.args[0]}") from exc

        trainer = get_trainer(trainer_id) if trainer_id else self._rng.choice(TRAINERS)
        if trainer is None:
            raise InvalidActionError(f"Unknown trainer {trainer_id}")

        level = self._settings.battle_level
        state = BattleState.new(
            id=uuid.uuid4().hex[:12],
            trainer=trainer,
            player_team=[BattlePokemon.from_record(r, level) for r in records],
            opponent_team=[
                BattlePokemon.from_record(r, level)
                for r in self._opponent_records(trainer, records)
            ],
            format=fmt,
            agent_name=self._agent.name,
        )
        BattleEngine(self._rng).start(state)
        self._store(state)
        return TurnResult(state, list(state.log), [])

    async def advise(self, battle_id: str, position: int) -> Decision:
        """Ask the coach agent what the player's Pokémon at ``position`` should do."""
        state = self.get(battle_id)
        if state.phase is Phase.FINISHED:
            raise InvalidActionError("This battle is over")
        if (
            not (0 <= position < state.format.positions)
            or state.active_at("player", position) is None
        ):
            raise InvalidActionError(f"No Pokémon at position {position}")
        if state.phase is Phase.PLAYER_MUST_SWITCH and not state.active("player", position).fainted:
            raise InvalidActionError("Advice is for the position that must be replaced")
        return await self._agent.advise(state, position)

    def get(self, battle_id: str) -> BattleState:
        state = self._battles.get(battle_id)
        if state is None:
            raise BattleNotFoundError(battle_id)
        return state

    async def take_turn(self, battle_id: str, player_actions: Actions) -> TurnResult:
        state = self.get(battle_id)
        async with self._lock(battle_id):
            engine = BattleEngine(self._rng)
            if state.phase is Phase.FINISHED:
                raise InvalidActionError("This battle is over")

            if state.phase is Phase.PLAYER_MUST_SWITCH:
                return self._handle_player_replacements(state, engine, player_actions)

            # One agent decision per active opponent Pokémon, taken concurrently.
            positions = state.living_positions("opponent")
            decisions = await asyncio.gather(
                *(self._agent.choose_action(state, pos) for pos in positions)
            )
            opponent_actions: Actions = {
                pos: d.action for pos, d in zip(positions, decisions, strict=True)
            }
            self._dedupe_switches(state, opponent_actions, decisions)
            log_decisions = [
                OpponentDecision(pos, state.active("opponent", pos).name, d)
                for pos, d in zip(positions, decisions, strict=True)
            ]
            try:
                events = engine.run_turn(state, player_actions, opponent_actions)
            except ValueError as exc:
                raise InvalidActionError(str(exc)) from exc

            # The opponent fills fainted positions immediately (the agent chooses each).
            if state.phase is not Phase.FINISHED:
                events += await self._opponent_replacements(state, engine, log_decisions)
            return TurnResult(state, events, log_decisions)

    # ---- helpers -----------------------------------------------------------

    def _handle_player_replacements(
        self, state: BattleState, engine: BattleEngine, actions: Actions
    ) -> TurnResult:
        needed = engine.positions_needing_replacement(state, "player")
        if not actions or any(not isinstance(a, SwitchAction) for a in actions.values()):
            raise InvalidActionError(
                f"Your Pokémon fainted - send a switch for position(s) {needed}"
            )
        events: list[BattleEvent] = []
        for pos, action in sorted(actions.items()):
            if pos not in needed:
                raise InvalidActionError(f"Position {pos} does not need a replacement")
            assert isinstance(action, SwitchAction)
            try:
                events += engine.replace_fainted(state, "player", pos, action.slot)
            except ValueError as exc:
                raise InvalidActionError(str(exc)) from exc
        return TurnResult(state, events, [])

    async def _opponent_replacements(
        self, state: BattleState, engine: BattleEngine, decisions: list[OpponentDecision]
    ) -> list[BattleEvent]:
        events: list[BattleEvent] = []
        used: set[int] = set()
        for pos in engine.positions_needing_replacement(state, "opponent"):
            fainted_name = state.active("opponent", pos).name
            decision = await self._agent.choose_replacement(state, pos, frozenset(used))
            assert isinstance(decision.action, SwitchAction)
            used.add(decision.action.slot)
            events += engine.replace_fainted(state, "opponent", pos, decision.action.slot)
            decisions.append(OpponentDecision(pos, fainted_name, decision))
        return events

    @staticmethod
    def _dedupe_switches(state: BattleState, actions: Actions, decisions: list[Decision]) -> None:
        """Two independent agents may both pick the same bench slot; keep the first."""
        seen: set[int] = set()
        for pos in sorted(actions):
            action = actions[pos]
            if isinstance(action, SwitchAction):
                if action.slot in seen:
                    # Fall back to the first usable move for this position.
                    me = state.active("opponent", pos)
                    from app.domain.battle import MoveAction  # local import to avoid cycle noise

                    idx = (me.usable_move_indices() or [0])[0]
                    actions[pos] = MoveAction("move", idx, None)
                else:
                    seen.add(action.slot)

    def _opponent_records(self, trainer: Trainer, player_records: list[PokemonRecord]):
        avg_total = sum(r.base_total for r in player_records) / len(player_records)
        # Difficulty nudges the opponent's strength relative to the player's team.
        target = int(avg_total + (trainer.difficulty - 3) * 25)
        return self._repo.pick_team(
            self._rng,
            size=len(player_records),
            preferred_types=trainer.preferred_types,
            target_base_total=target,
            allow_legendary=trainer.allow_legendary,
            exclude=[r.pokedex_number for r in player_records],
        )

    def _store(self, state: BattleState) -> None:
        self._battles[state.id] = state
        self._locks[state.id] = asyncio.Lock()
        while len(self._battles) > self._max:
            old_id, _ = self._battles.popitem(last=False)
            self._locks.pop(old_id, None)

    def _lock(self, battle_id: str) -> asyncio.Lock:
        return self._locks.setdefault(battle_id, asyncio.Lock())
