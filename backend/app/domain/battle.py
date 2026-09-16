"""Turn-based battle engine supporting single (1v1) and double (2v2) battles.

Rules (a faithful simplification of the main-series games):

* Every Pokémon is level 50 with perfect IVs and no EVs.
* Damage uses the standard formula with STAB, type effectiveness taken from the
  dataset's ``against_*`` columns, a 1/24 critical-hit chance and a 0.85–1.0 roll.
* Stat stages range from -6 to +6 and follow the usual (2+n)/2 multipliers.
* Each side has one (single) or two (double) active *positions*. A turn consists of
  one action per occupied position. Switches resolve first, then moves in order of
  priority, then Speed (ties broken randomly).
* In doubles a damaging move names a target position on the opposing side. If that
  target has fainted the move is redirected to the remaining foe.
* When a Pokémon faints, its side fills the position from the bench before the next
  turn; that replacement does not cost the other side a turn.

The engine is pure: it mutates a :class:`BattleState` and appends
:class:`BattleEvent` records, but performs no I/O.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from app.data.models import PokemonRecord
from app.domain.items import DEFAULT_BAG, ITEMS
from app.domain.moves import Move, MoveCategory, StatusEffect, build_moveset
from app.domain.trainers import Trainer
from app.domain.types import PokemonType

Side = Literal["player", "opponent"]

EMPTY = -1  # marks an active position with no Pokémon in it

STAGE_MULTIPLIERS: dict[int, float] = {
    -6: 2 / 8,
    -5: 2 / 7,
    -4: 2 / 6,
    -3: 2 / 5,
    -2: 2 / 4,
    -1: 2 / 3,
    0: 1.0,
    1: 3 / 2,
    2: 4 / 2,
    3: 5 / 2,
    4: 6 / 2,
    5: 7 / 2,
    6: 8 / 2,
}

CRIT_CHANCE = 1 / 24
CRIT_MULTIPLIER = 1.5
STAB_MULTIPLIER = 1.5


class BattleFormat(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"

    @property
    def positions(self) -> int:
        return 2 if self is BattleFormat.DOUBLE else 1


class Stat(StrEnum):
    ATTACK = "attack"
    DEFENSE = "defense"
    SP_ATTACK = "sp_attack"
    SP_DEFENSE = "sp_defense"
    SPEED = "speed"


STAT_FOR_EFFECT: dict[StatusEffect, Stat] = {
    StatusEffect.BOOST_ATTACK: Stat.ATTACK,
    StatusEffect.BOOST_DEFENSE: Stat.DEFENSE,
    StatusEffect.BOOST_SP_ATTACK: Stat.SP_ATTACK,
    StatusEffect.BOOST_SP_DEFENSE: Stat.SP_DEFENSE,
    StatusEffect.BOOST_SPEED: Stat.SPEED,
}

_STAT_LABEL: dict[Stat, str] = {
    Stat.ATTACK: "Attack",
    Stat.DEFENSE: "Defense",
    Stat.SP_ATTACK: "Sp. Atk",
    Stat.SP_DEFENSE: "Sp. Def",
    Stat.SPEED: "Speed",
}


def hp_at_level(base: int, level: int) -> int:
    return math.floor((2 * base + 31) * level / 100) + level + 10


def stat_at_level(base: int, level: int) -> int:
    return math.floor((2 * base + 31) * level / 100) + 5


def opposite(side: Side) -> Side:
    return "opponent" if side == "player" else "player"


@dataclass(slots=True)
class BattlePokemon:
    """A Pokémon instance inside a battle: base record + runtime state."""

    record: PokemonRecord
    level: int
    max_hp: int
    current_hp: int
    stats: dict[Stat, int]
    moves: list[Move]
    pp: list[int]
    stages: dict[Stat, int] = field(default_factory=lambda: {s: 0 for s in Stat})

    @classmethod
    def from_record(cls, record: PokemonRecord, level: int) -> BattlePokemon:
        moves = build_moveset(record)
        max_hp = hp_at_level(record.hp, level)
        return cls(
            record=record,
            level=level,
            max_hp=max_hp,
            current_hp=max_hp,
            stats={
                Stat.ATTACK: stat_at_level(record.attack, level),
                Stat.DEFENSE: stat_at_level(record.defense, level),
                Stat.SP_ATTACK: stat_at_level(record.sp_attack, level),
                Stat.SP_DEFENSE: stat_at_level(record.sp_defense, level),
                Stat.SPEED: stat_at_level(record.speed, level),
            },
            moves=moves,
            pp=[m.pp for m in moves],
        )

    @property
    def name(self) -> str:
        return self.record.name

    @property
    def fainted(self) -> bool:
        return self.current_hp <= 0

    @property
    def hp_fraction(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp else 0.0

    def effective_stat(self, stat: Stat) -> int:
        return max(1, math.floor(self.stats[stat] * STAGE_MULTIPLIERS[self.stages[stat]]))

    def usable_move_indices(self) -> list[int]:
        return [i for i, remaining in enumerate(self.pp) if remaining > 0]

    def reset_stages(self) -> None:
        for s in Stat:
            self.stages[s] = 0


# ---- actions ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MoveAction:
    kind: Literal["move"]
    move_index: int
    target_position: int | None = None  # opposing position; None = auto (singles)


@dataclass(frozen=True, slots=True)
class SwitchAction:
    kind: Literal["switch"]
    slot: int


@dataclass(frozen=True, slots=True)
class ItemAction:
    kind: Literal["item"]
    item: str  # key into app.domain.items.ITEMS; used on the Pokémon at this position


Action = MoveAction | SwitchAction | ItemAction
Actions = dict[int, Action]  # position -> action


# ---- events ----------------------------------------------------------------


class EventType(StrEnum):
    ITEM = "item"
    SWITCH = "switch"
    MOVE = "move"
    DAMAGE = "damage"
    MISS = "miss"
    STAT_CHANGE = "stat_change"
    HEAL = "heal"
    FAINT = "faint"
    TEXT = "text"
    BATTLE_END = "battle_end"


@dataclass(slots=True)
class BattleEvent:
    type: EventType
    side: Side | None
    text: str
    move: str | None = None
    move_type: PokemonType | None = None
    damage: int = 0
    effectiveness: float | None = None
    critical: bool = False
    hp_after: int | None = None
    pokemon: str | None = None
    slot: int | None = None
    position: int | None = None
    # Who was affected by a damage/heal/faint/switch event.
    target_side: Side | None = None
    target_slot: int | None = None
    target_position: int | None = None


class Phase(StrEnum):
    CHOOSE_ACTION = "choose_action"
    PLAYER_MUST_SWITCH = "player_must_switch"
    FINISHED = "finished"


# ---- state -----------------------------------------------------------------


@dataclass(slots=True)
class BattleState:
    id: str
    trainer: Trainer
    player_team: list[BattlePokemon]
    opponent_team: list[BattlePokemon]
    format: BattleFormat = BattleFormat.SINGLE
    player_active: list[int] = field(default_factory=lambda: [0])
    opponent_active: list[int] = field(default_factory=lambda: [0])
    turn: int = 0
    phase: Phase = Phase.CHOOSE_ACTION
    winner: Side | None = None
    log: list[BattleEvent] = field(default_factory=list)
    agent_name: str = "heuristic"
    player_items: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_BAG))

    @classmethod
    def new(
        cls,
        *,
        id: str,  # noqa: A002
        trainer: Trainer,
        player_team: list[BattlePokemon],
        opponent_team: list[BattlePokemon],
        format: BattleFormat,  # noqa: A002
        agent_name: str,
    ) -> BattleState:
        n = format.positions
        return cls(
            id=id,
            trainer=trainer,
            player_team=player_team,
            opponent_team=opponent_team,
            format=format,
            player_active=[i if i < len(player_team) else EMPTY for i in range(n)],
            opponent_active=[i if i < len(opponent_team) else EMPTY for i in range(n)],
            agent_name=agent_name,
        )

    # -- lookups --

    def team(self, side: Side) -> list[BattlePokemon]:
        return self.player_team if side == "player" else self.opponent_team

    def active_slots(self, side: Side) -> list[int]:
        return self.player_active if side == "player" else self.opponent_active

    def slot_at(self, side: Side, position: int) -> int:
        return self.active_slots(side)[position]

    def active(self, side: Side, position: int = 0) -> BattlePokemon:
        slot = self.slot_at(side, position)
        if slot == EMPTY:
            raise ValueError(f"{side} position {position} is empty")
        return self.team(side)[slot]

    def active_at(self, side: Side, position: int) -> BattlePokemon | None:
        slot = self.slot_at(side, position)
        return None if slot == EMPTY else self.team(side)[slot]

    def occupied_positions(self, side: Side) -> list[int]:
        return [p for p, s in enumerate(self.active_slots(side)) if s != EMPTY]

    def living_positions(self, side: Side) -> list[int]:
        return [p for p in self.occupied_positions(side) if not self.active(side, p).fainted]

    def fainted_positions(self, side: Side) -> list[int]:
        return [p for p in self.occupied_positions(side) if self.active(side, p).fainted]

    def bench(self, side: Side) -> list[int]:
        """Team slots not currently on the field and able to battle."""
        on_field = set(self.active_slots(side))
        return [i for i, p in enumerate(self.team(side)) if i not in on_field and not p.fainted]

    def available_switches(self, side: Side) -> list[int]:
        return self.bench(side)

    def has_living(self, side: Side) -> bool:
        return any(not p.fainted for p in self.team(side))

    def position_of_slot(self, side: Side, slot: int) -> int | None:
        slots = self.active_slots(side)
        return slots.index(slot) if slot in slots else None


# ---- damage ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DamageResult:
    damage: int
    effectiveness: float
    critical: bool


def compute_damage(
    attacker: BattlePokemon,
    defender: BattlePokemon,
    move: Move,
    rng: random.Random,
    *,
    force_roll: float | None = None,
    force_crit: bool | None = None,
) -> DamageResult:
    """Standard main-series damage formula."""
    if move.category is MoveCategory.STATUS or move.power <= 0:
        return DamageResult(0, 1.0, False)

    if move.category is MoveCategory.PHYSICAL:
        atk_stat, def_stat = Stat.ATTACK, Stat.DEFENSE
    else:
        atk_stat, def_stat = Stat.SP_ATTACK, Stat.SP_DEFENSE

    critical = (rng.random() < CRIT_CHANCE) if force_crit is None else force_crit
    # Critical hits ignore the attacker's negative stages and the defender's positive ones.
    atk_stage = max(attacker.stages[atk_stat], 0) if critical else attacker.stages[atk_stat]
    def_stage = min(defender.stages[def_stat], 0) if critical else defender.stages[def_stat]
    attack = max(1, math.floor(attacker.stats[atk_stat] * STAGE_MULTIPLIERS[atk_stage]))
    defense = max(1, math.floor(defender.stats[def_stat] * STAGE_MULTIPLIERS[def_stage]))

    level = attacker.level
    base = (
        math.floor(math.floor(math.floor(2 * level / 5 + 2) * move.power * attack / defense) / 50)
        + 2
    )

    effectiveness = defender.record.effectiveness_against(move.type)
    stab = STAB_MULTIPLIER if move.type in attacker.record.types else 1.0
    roll = rng.uniform(0.85, 1.0) if force_roll is None else force_roll

    damage = base
    damage = math.floor(damage * (CRIT_MULTIPLIER if critical else 1.0))
    damage = math.floor(damage * roll)
    damage = math.floor(damage * stab)
    damage = math.floor(damage * effectiveness)
    if effectiveness > 0:
        damage = max(1, damage)
    return DamageResult(damage, effectiveness, critical)


def expected_damage(attacker: BattlePokemon, defender: BattlePokemon, move: Move) -> float:
    """Accuracy-weighted average damage; used by the heuristic agent and the LLM briefing."""
    if move.category is MoveCategory.STATUS:
        return 0.0
    res = compute_damage(
        attacker, defender, move, random.Random(0), force_roll=0.925, force_crit=False
    )
    accuracy = 1.0 if move.accuracy == 0 else move.accuracy / 100
    return res.damage * accuracy


# ---- engine ----------------------------------------------------------------


class BattleEngine:
    """Applies actions to a :class:`BattleState`."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    # ---- public API ------------------------------------------------------

    def start(self, state: BattleState) -> None:
        kind = "double" if state.format is BattleFormat.DOUBLE else "single"
        state.log.append(
            BattleEvent(EventType.TEXT, None, f"{state.trainer.name} wants a {kind} battle!")
        )
        for pos in state.occupied_positions("opponent"):
            self._send_out(state, "opponent", pos, state.slot_at("opponent", pos), initial=True)
        for pos in state.occupied_positions("player"):
            self._send_out(state, "player", pos, state.slot_at("player", pos), initial=True)

    def run_turn(
        self, state: BattleState, player_actions: Actions, opponent_actions: Actions
    ) -> list[BattleEvent]:
        """Resolve one full turn. Returns the events generated by this turn."""
        if state.phase is not Phase.CHOOSE_ACTION:
            raise ValueError(f"Cannot take a turn while phase is {state.phase}")
        self._validate(state, "player", player_actions)
        self._validate(state, "opponent", opponent_actions)

        start_len = len(state.log)
        state.turn += 1
        state.log.append(BattleEvent(EventType.TEXT, None, f"Turn {state.turn}"))

        # Switches happen before any move.
        for side, actions in (("player", player_actions), ("opponent", opponent_actions)):
            for pos, action in sorted(actions.items()):
                if isinstance(action, SwitchAction):
                    self._send_out(state, side, pos, action.slot)

        # Items are used next (they always go before moves, as in the games).
        for pos, action in sorted(player_actions.items()):
            if isinstance(action, ItemAction):
                self._use_item(state, pos, action)

        movers: list[tuple[Side, int, MoveAction]] = [
            (side, pos, action)
            for side, actions in (("player", player_actions), ("opponent", opponent_actions))
            for pos, action in actions.items()
            if isinstance(action, MoveAction)
        ]
        movers.sort(key=lambda m: self._turn_order_key(state, m[0], m[1], m[2]), reverse=True)

        for side, pos, action in movers:
            attacker = state.active_at(side, pos)
            if attacker is None or attacker.fainted:
                continue
            self._use_move(state, side, pos, action)
            if state.winner is not None:
                break

        self._after_turn(state)
        return state.log[start_len:]

    def replace_fainted(
        self, state: BattleState, side: Side, position: int, slot: int
    ) -> list[BattleEvent]:
        """Send out a replacement into a fainted position. Free action, no turn is consumed."""
        team = state.team(side)
        if not (0 <= slot < len(team)) or team[slot].fainted:
            raise ValueError("Invalid replacement slot")
        if slot in state.active_slots(side):
            raise ValueError(f"{team[slot].name} is already on the field")
        current = state.active_at(side, position)
        if current is not None and not current.fainted:
            raise ValueError("That position's Pokémon has not fainted")
        start_len = len(state.log)
        self._send_out(state, side, position, slot)
        if side == "player" and not self._player_needs_switch(state):
            state.phase = Phase.CHOOSE_ACTION
        return state.log[start_len:]

    def positions_needing_replacement(self, state: BattleState, side: Side) -> list[int]:
        """Fainted positions that can still be filled from the bench (bench-limited)."""
        fainted = state.fainted_positions(side)
        return fainted[: len(state.bench(side))]

    # ---- internals -------------------------------------------------------

    def _validate(self, state: BattleState, side: Side, actions: Actions) -> None:
        living = state.living_positions(side)
        if sorted(actions) != living:
            raise ValueError(
                f"{side}: expected one action for each active position {living}, "
                f"got {sorted(actions)}"
            )
        switch_targets: list[int] = []
        for pos, action in actions.items():
            active = state.active(side, pos)
            if isinstance(action, MoveAction):
                if not (0 <= action.move_index < len(active.moves)):
                    raise ValueError(f"{side}: move index out of range")
                if active.pp[action.move_index] <= 0:
                    raise ValueError(
                        f"{side}: no PP left for {active.moves[action.move_index].name}"
                    )
                if action.target_position is not None and not (
                    0 <= action.target_position < state.format.positions
                ):
                    raise ValueError(f"{side}: target position out of range")
            elif isinstance(action, SwitchAction):
                if action.slot not in state.available_switches(side):
                    raise ValueError(f"{side}: cannot switch to slot {action.slot}")
                if action.slot in switch_targets:
                    raise ValueError(f"{side}: two Pokémon cannot switch to the same slot")
                switch_targets.append(action.slot)
            elif isinstance(action, ItemAction):
                if side != "player":
                    raise ValueError("Only the player has a bag")
                if action.item not in ITEMS:
                    raise ValueError(f"Unknown item {action.item}")
                if state.player_items.get(action.item, 0) <= 0:
                    raise ValueError(f"No {ITEMS[action.item].name} left")
                if active.current_hp >= active.max_hp:
                    raise ValueError(f"{active.name}'s HP is already full")
            else:  # pragma: no cover - defensive
                raise ValueError("Unknown action")
        items = [a.item for a in actions.values() if isinstance(a, ItemAction)]
        for item in set(items):
            if items.count(item) > state.player_items.get(item, 0):
                raise ValueError(f"Not enough {ITEMS[item].name} for both Pokémon")

    def _turn_order_key(
        self, state: BattleState, side: Side, pos: int, action: MoveAction
    ) -> tuple[int, int, float]:
        attacker = state.active(side, pos)
        move = attacker.moves[action.move_index]
        return (move.priority, attacker.effective_stat(Stat.SPEED), self.rng.random())

    def _owner(self, state: BattleState, side: Side) -> str:
        return "You" if side == "player" else state.trainer.name

    def _send_out(
        self, state: BattleState, side: Side, position: int, slot: int, *, initial: bool = False
    ) -> None:
        team = state.team(side)
        slots = state.active_slots(side)
        previous = state.active_at(side, position)
        if (
            not initial
            and previous is not None
            and previous is not team[slot]
            and not previous.fainted
        ):
            previous.reset_stages()
            state.log.append(
                BattleEvent(
                    EventType.TEXT, side, f"{self._owner(state, side)} withdrew {previous.name}!"
                )
            )
        slots[position] = slot
        incoming = team[slot]
        incoming.reset_stages()
        state.log.append(
            BattleEvent(
                EventType.SWITCH,
                side,
                f"{self._owner(state, side)} sent out {incoming.name}!",
                pokemon=incoming.name,
                slot=slot,
                position=position,
                hp_after=incoming.current_hp,
                target_side=side,
                target_slot=slot,
                target_position=position,
            )
        )

    def _use_item(self, state: BattleState, pos: int, action: ItemAction) -> None:
        item = ITEMS[action.item]
        target = state.active("player", pos)
        state.player_items[action.item] -= 1
        healed = (
            target.max_hp - target.current_hp
            if item.heal == 0
            else min(item.heal, target.max_hp - target.current_hp)
        )
        target.current_hp += healed
        state.log.append(
            BattleEvent(
                EventType.ITEM,
                "player",
                f"You used a {item.name} on {target.name}!",
                pokemon=target.name,
                position=pos,
            )
        )
        state.log.append(
            BattleEvent(
                EventType.HEAL,
                "player",
                f"{target.name} regained {healed} HP!",
                damage=-healed,
                hp_after=target.current_hp,
                pokemon=target.name,
                target_side="player",
                target_slot=state.slot_at("player", pos),
                target_position=pos,
            )
        )

    def _resolve_target(
        self, state: BattleState, side: Side, action: MoveAction
    ) -> tuple[int, BattlePokemon] | None:
        foe_side = opposite(side)
        wanted = action.target_position
        if wanted is not None:
            target = state.active_at(foe_side, wanted)
            if target is not None and not target.fainted:
                return wanted, target
        # Redirect to any living foe (singles, or the chosen target already fainted).
        living = state.living_positions(foe_side)
        if not living:
            return None
        pos = living[0] if wanted is None or len(living) == 1 else self.rng.choice(living)
        return pos, state.active(foe_side, pos)

    def _use_move(self, state: BattleState, side: Side, pos: int, action: MoveAction) -> None:
        attacker = state.active(side, pos)
        move = attacker.moves[action.move_index]
        attacker.pp[action.move_index] = max(0, attacker.pp[action.move_index] - 1)

        state.log.append(
            BattleEvent(
                EventType.MOVE,
                side,
                f"{attacker.name} used {move.name}!",
                move=move.name,
                move_type=move.type,
                pokemon=attacker.name,
                slot=state.slot_at(side, pos),
                position=pos,
            )
        )

        if move.category is MoveCategory.STATUS:
            self._apply_status_move(state, side, pos, attacker, move)
            return

        resolved = self._resolve_target(state, side, action)
        if resolved is None:
            state.log.append(BattleEvent(EventType.TEXT, side, "But there was no target..."))
            return
        target_pos, defender = resolved
        foe_side = opposite(side)
        target_slot = state.slot_at(foe_side, target_pos)

        if move.accuracy and self.rng.random() * 100 >= move.accuracy:
            state.log.append(
                BattleEvent(
                    EventType.MISS, side, f"{attacker.name}'s attack missed!", move=move.name
                )
            )
            return

        result = compute_damage(attacker, defender, move, self.rng)
        if result.effectiveness == 0:
            state.log.append(
                BattleEvent(
                    EventType.DAMAGE,
                    side,
                    f"It doesn't affect {defender.name}...",
                    move=move.name,
                    move_type=move.type,
                    damage=0,
                    effectiveness=0.0,
                    hp_after=defender.current_hp,
                    pokemon=defender.name,
                    target_side=foe_side,
                    target_slot=target_slot,
                    target_position=target_pos,
                )
            )
            return

        defender.current_hp = max(0, defender.current_hp - result.damage)
        state.log.append(
            BattleEvent(
                EventType.DAMAGE,
                side,
                f"{defender.name} took {result.damage} damage.",
                move=move.name,
                move_type=move.type,
                damage=result.damage,
                effectiveness=result.effectiveness,
                critical=result.critical,
                hp_after=defender.current_hp,
                pokemon=defender.name,
                target_side=foe_side,
                target_slot=target_slot,
                target_position=target_pos,
            )
        )
        if result.critical:
            state.log.append(BattleEvent(EventType.TEXT, side, "A critical hit!"))
        if result.effectiveness > 1:
            state.log.append(BattleEvent(EventType.TEXT, side, "It's super effective!"))
        elif result.effectiveness < 1:
            state.log.append(BattleEvent(EventType.TEXT, side, "It's not very effective..."))

        if defender.fainted:
            self._handle_faint(state, foe_side, target_pos)

    def _apply_status_move(
        self, state: BattleState, side: Side, pos: int, user: BattlePokemon, move: Move
    ) -> None:
        slot = state.slot_at(side, pos)
        if move.effect is StatusEffect.HEAL:
            if user.current_hp >= user.max_hp:
                state.log.append(
                    BattleEvent(EventType.TEXT, side, f"{user.name}'s HP is already full!")
                )
                return
            healed = min(user.max_hp - user.current_hp, math.ceil(user.max_hp / 2))
            user.current_hp += healed
            state.log.append(
                BattleEvent(
                    EventType.HEAL,
                    side,
                    f"{user.name} regained {healed} HP!",
                    damage=-healed,
                    hp_after=user.current_hp,
                    pokemon=user.name,
                    target_side=side,
                    target_slot=slot,
                    target_position=pos,
                )
            )
            return

        stat = STAT_FOR_EFFECT.get(move.effect) if move.effect else None
        if stat is None:
            return
        before = user.stages[stat]
        user.stages[stat] = max(-6, min(6, before + move.effect_stages))
        delta = user.stages[stat] - before
        label = _STAT_LABEL[stat]
        if delta == 0:
            text = f"{user.name}'s {label} won't go any higher!"
        elif delta >= 2:
            text = f"{user.name}'s {label} rose sharply!"
        else:
            text = f"{user.name}'s {label} rose!"
        state.log.append(
            BattleEvent(
                EventType.STAT_CHANGE,
                side,
                text,
                pokemon=user.name,
                target_side=side,
                target_slot=slot,
                target_position=pos,
            )
        )

    def _handle_faint(self, state: BattleState, side: Side, position: int) -> None:
        fainted = state.active(side, position)
        state.log.append(
            BattleEvent(
                EventType.FAINT,
                side,
                f"{fainted.name} fainted!",
                pokemon=fainted.name,
                hp_after=0,
                target_side=side,
                target_slot=state.slot_at(side, position),
                target_position=position,
            )
        )
        if not state.has_living(side):
            state.winner = opposite(side)
            state.phase = Phase.FINISHED
            if state.winner == "player":
                text = f"You defeated {state.trainer.name}!"
            else:
                text = f"You were defeated by {state.trainer.name}..."
            state.log.append(BattleEvent(EventType.BATTLE_END, state.winner, text))

    def _player_needs_switch(self, state: BattleState) -> bool:
        return bool(self.positions_needing_replacement(state, "player"))

    def _after_turn(self, state: BattleState) -> None:
        if state.phase is Phase.FINISHED:
            return
        # Fainted Pokémon with no bench replacement simply leave an empty position.
        for side in ("player", "opponent"):
            fillable = set(self.positions_needing_replacement(state, side))
            for pos in state.fainted_positions(side):
                if pos not in fillable:
                    state.active_slots(side)[pos] = EMPTY
        state.phase = (
            Phase.PLAYER_MUST_SWITCH if self._player_needs_switch(state) else Phase.CHOOSE_ACTION
        )
