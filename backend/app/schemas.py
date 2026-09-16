"""Pydantic models exposed over HTTP (request validation + response serialisation).

These are the contract shown in the OpenAPI / Swagger docs at ``/api/docs``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agents.base import Decision
from app.data.models import PokemonRecord
from app.domain.battle import (
    BattleEvent,
    BattleFormat,
    BattlePokemon,
    BattleState,
    ItemAction,
    MoveAction,
    Phase,
    Stat,
    SwitchAction,
)
from app.domain.items import ITEMS
from app.domain.moves import Move, build_moveset
from app.domain.trainers import Trainer
from app.domain.types import TYPE_COLORS, PokemonType
from app.services.battle_service import OpponentDecision

SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"


class Sprites(BaseModel):
    artwork: str = Field(description="Official artwork PNG")
    front: str = Field(description="Animated front sprite (GIF)")
    back: str = Field(description="Animated back sprite (GIF)")
    icon: str = Field(description="Small static sprite")

    @classmethod
    def for_dex(cls, dex: int) -> Sprites:
        return cls(
            artwork=f"{SPRITE_BASE}/other/official-artwork/{dex}.png",
            front=f"{SPRITE_BASE}/other/showdown/{dex}.gif",
            back=f"{SPRITE_BASE}/other/showdown/back/{dex}.gif",
            icon=f"{SPRITE_BASE}/{dex}.png",
        )


class MoveOut(BaseModel):
    name: str
    type: PokemonType
    color: str = Field(description="Hex colour of the move's type, for the UI")
    category: Literal["physical", "special", "status"]
    power: int = Field(description="0 for status moves")
    accuracy: int = Field(description="Percentage; 0 means the move never misses")
    pp: int
    max_pp: int
    priority: int
    description: str

    @classmethod
    def from_move(cls, m: Move, pp: int | None = None) -> MoveOut:
        return cls(
            name=m.name,
            type=m.type,
            color=TYPE_COLORS[m.type],
            category=m.category.value,
            power=m.power,
            accuracy=m.accuracy,
            pp=m.pp if pp is None else pp,
            max_pp=m.pp,
            priority=m.priority,
            description=m.description,
        )


class PokemonSummary(BaseModel):
    id: int = Field(description="National Pokédex number")
    name: str
    types: list[PokemonType]
    colors: list[str]
    generation: int
    is_legendary: bool
    base_total: int
    sprites: Sprites

    @classmethod
    def from_record(cls, r: PokemonRecord) -> PokemonSummary:
        return cls(
            id=r.pokedex_number,
            name=r.name,
            types=list(r.types),
            colors=[TYPE_COLORS[t] for t in r.types],
            generation=r.generation,
            is_legendary=r.is_legendary,
            base_total=r.base_total,
            sprites=Sprites.for_dex(r.pokedex_number),
        )


class PokemonDetail(PokemonSummary):
    japanese_name: str
    classification: str
    abilities: list[str]
    stats: dict[str, int]
    height_m: float | None
    weight_kg: float | None
    weaknesses: list[PokemonType]
    resistances: list[PokemonType]
    immunities: list[PokemonType]
    moves: list[MoveOut] = Field(description="Generated four-move set used in battle")

    @classmethod
    def from_record(cls, r: PokemonRecord) -> PokemonDetail:
        base = PokemonSummary.from_record(r).model_dump()
        return cls(
            **base,
            japanese_name=r.japanese_name,
            classification=r.classification,
            abilities=list(r.abilities),
            stats={
                "hp": r.hp,
                "attack": r.attack,
                "defense": r.defense,
                "sp_attack": r.sp_attack,
                "sp_defense": r.sp_defense,
                "speed": r.speed,
            },
            height_m=r.height_m,
            weight_kg=r.weight_kg,
            weaknesses=[t for t, m in r.against.items() if m > 1],
            resistances=[t for t, m in r.against.items() if 0 < m < 1],
            immunities=[t for t, m in r.against.items() if m == 0],
            moves=[MoveOut.from_move(m) for m in build_moveset(r)],
        )


class PokemonPage(BaseModel):
    items: list[PokemonSummary]
    total: int = Field(description="Total matches before pagination")


class TrainerOut(BaseModel):
    id: str
    name: str
    title: str
    sprite_url: str
    preferred_types: list[PokemonType]
    difficulty: int = Field(ge=1, le=5)
    intro: str

    @classmethod
    def from_trainer(cls, t: Trainer) -> TrainerOut:
        return cls(
            id=t.id,
            name=t.name,
            title=t.title,
            sprite_url=t.sprite_url,
            preferred_types=list(t.preferred_types),
            difficulty=t.difficulty,
            intro=t.intro,
        )


class BattlePokemonOut(BaseModel):
    slot: int = Field(description="Index in the team list")
    id: int
    name: str
    types: list[PokemonType]
    colors: list[str]
    level: int
    max_hp: int
    current_hp: int
    fainted: bool
    stats: dict[str, int] = Field(description="Effective stats after stage modifiers")
    stages: dict[str, int]
    moves: list[MoveOut] = Field(description="Empty for opponent Pokémon (hidden)")
    sprites: Sprites

    @classmethod
    def from_battle_pokemon(
        cls, slot: int, p: BattlePokemon, *, reveal_moves: bool
    ) -> BattlePokemonOut:
        return cls(
            slot=slot,
            id=p.record.pokedex_number,
            name=p.name,
            types=list(p.record.types),
            colors=[TYPE_COLORS[t] for t in p.record.types],
            level=p.level,
            max_hp=p.max_hp,
            current_hp=p.current_hp,
            fainted=p.fainted,
            stats={s.value: p.effective_stat(s) for s in Stat},
            stages={s.value: v for s, v in p.stages.items()},
            moves=(
                [MoveOut.from_move(m, pp) for m, pp in zip(p.moves, p.pp, strict=True)]
                if reveal_moves
                else []
            ),
            sprites=Sprites.for_dex(p.record.pokedex_number),
        )


class EventOut(BaseModel):
    type: str
    side: Literal["player", "opponent"] | None = Field(description="Side that acted")
    text: str
    move: str | None = None
    move_type: PokemonType | None = None
    move_color: str | None = None
    damage: int = 0
    effectiveness: float | None = None
    critical: bool = False
    hp_after: int | None = None
    pokemon: str | None = None
    slot: int | None = None
    position: int | None = None
    target_side: Literal["player", "opponent"] | None = Field(
        default=None, description="Side of the Pokémon affected by this event"
    )
    target_slot: int | None = None
    target_position: int | None = None

    @classmethod
    def from_event(cls, e: BattleEvent) -> EventOut:
        return cls(
            type=e.type.value,
            side=e.side,
            text=e.text,
            move=e.move,
            move_type=e.move_type,
            move_color=TYPE_COLORS[e.move_type] if e.move_type else None,
            damage=e.damage,
            effectiveness=e.effectiveness,
            critical=e.critical,
            hp_after=e.hp_after,
            pokemon=e.pokemon,
            slot=e.slot,
            position=e.position,
            target_side=e.target_side,
            target_slot=e.target_slot,
            target_position=e.target_position,
        )


class OpponentDecisionOut(BaseModel):
    position: int = Field(description="Which opponent position this decision was for")
    pokemon: str
    taunt: str
    reasoning: str
    source: Literal["claude", "claude_code", "heuristic"] = Field(
        description="Which agent produced the decision"
    )

    @classmethod
    def from_decision(cls, d: OpponentDecision) -> OpponentDecisionOut:
        return cls(
            position=d.position,
            pokemon=d.pokemon,
            taunt=d.decision.taunt,
            reasoning=d.decision.reasoning,
            source=d.decision.source,
        )


class ItemOut(BaseModel):
    id: str
    name: str
    description: str
    count: int


class BattleOut(BaseModel):
    id: str
    format: BattleFormat
    turn: int
    phase: Phase
    winner: Literal["player", "opponent"] | None
    trainer: TrainerOut
    agent: str = Field(description="Agent configured for the opponent")
    player_team: list[BattlePokemonOut]
    opponent_team: list[BattlePokemonOut]
    player_active: list[int] = Field(description="Team slot per position; -1 = empty")
    opponent_active: list[int]
    positions_to_replace: list[int] = Field(
        description="Player positions that must receive a switch (phase player_must_switch)"
    )
    player_items: list[ItemOut] = Field(description="The player's bag")
    events: list[EventOut] = Field(description="Events produced by the latest request only")
    opponent_decisions: list[OpponentDecisionOut] = Field(
        description="One entry per opponent Pokémon that acted (or was sent out) this request"
    )

    @classmethod
    def from_state(
        cls,
        s: BattleState,
        events: list[BattleEvent],
        decisions: list[OpponentDecision],
        positions_to_replace: list[int],
    ) -> BattleOut:
        return cls(
            id=s.id,
            format=s.format,
            turn=s.turn,
            phase=s.phase,
            winner=s.winner,
            trainer=TrainerOut.from_trainer(s.trainer),
            agent=s.agent_name,
            player_team=[
                BattlePokemonOut.from_battle_pokemon(i, p, reveal_moves=True)
                for i, p in enumerate(s.player_team)
            ],
            opponent_team=[
                BattlePokemonOut.from_battle_pokemon(i, p, reveal_moves=False)
                for i, p in enumerate(s.opponent_team)
            ],
            player_active=list(s.player_active),
            opponent_active=list(s.opponent_active),
            positions_to_replace=positions_to_replace,
            player_items=[
                ItemOut(id=k, name=ITEMS[k].name, description=ITEMS[k].description, count=n)
                for k, n in s.player_items.items()
            ],
            events=[EventOut.from_event(e) for e in events],
            opponent_decisions=[OpponentDecisionOut.from_decision(d) for d in decisions],
        )


# ---- requests ------------------------------------------------------------


class CreateBattleRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"team": [6, 25], "trainer_id": "misty", "format": "single"},
                {"team": [6, 25, 143, 9], "trainer_id": "cynthia", "format": "double"},
            ]
        }
    )

    team: Annotated[
        list[int], Field(min_length=1, max_length=6, description="Pokédex numbers, in order")
    ]
    trainer_id: str | None = Field(default=None, description="Omit for a random trainer")
    format: BattleFormat = Field(
        default=BattleFormat.SINGLE, description="single = 1v1, double = 2v2 (needs 2+ Pokémon)"
    )


class MoveActionIn(BaseModel):
    kind: Literal["move"]
    position: int = Field(default=0, ge=0, le=1, description="Which of your active Pokémon acts")
    move_index: Annotated[int, Field(ge=0, le=3)]
    target_position: int | None = Field(
        default=None, ge=0, le=1, description="Foe position to hit (doubles only)"
    )


class SwitchActionIn(BaseModel):
    kind: Literal["switch"]
    position: int = Field(default=0, ge=0, le=1, description="Which active position switches")
    slot: Annotated[int, Field(ge=0, le=5, description="Bench slot to bring in")]


class ItemActionIn(BaseModel):
    kind: Literal["item"]
    position: int = Field(default=0, ge=0, le=1, description="Which active Pokémon receives it")
    item: str = Field(description="Item id from the bag, e.g. 'potion'")


ActionIn = Annotated[MoveActionIn | SwitchActionIn | ItemActionIn, Field(discriminator="kind")]


class TurnRequest(BaseModel):
    """One action per active player Pokémon.

    Singles: send ``actions`` with one entry (or the shorthand ``action``).
    Doubles: send one entry for each living position, e.g. position 0 and 1.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"action": {"kind": "move", "move_index": 0}},
                {"action": {"kind": "item", "item": "potion"}},
                {
                    "actions": [
                        {"kind": "move", "position": 0, "move_index": 1, "target_position": 1},
                        {"kind": "switch", "position": 1, "slot": 2},
                    ]
                },
            ]
        }
    )

    action: ActionIn | None = Field(default=None, description="Shorthand for a single action")
    actions: list[ActionIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _merge(self) -> TurnRequest:
        if self.action is not None:
            self.actions = [self.action, *self.actions]
            self.action = None
        if not self.actions:
            raise ValueError("Provide 'action' or a non-empty 'actions' list")
        positions = [a.position for a in self.actions]
        if len(set(positions)) != len(positions):
            raise ValueError("Each position may only act once per turn")
        return self


class AdviceRequest(BaseModel):
    position: int = Field(default=0, ge=0, le=1, description="Which of your Pokémon to advise")


class AdviceOut(BaseModel):
    """The coach's recommendation, ready to submit as a turn action."""

    position: int
    pokemon: str
    action: ActionIn = Field(description="Submit this in POST /battles/{id}/turn to follow it")
    summary: str = Field(description="Human-readable action, e.g. 'Flamethrower → Venusaur'")
    coach_line: str
    reasoning: str
    source: Literal["claude", "claude_code", "heuristic"]

    @classmethod
    def from_decision(cls, state: BattleState, position: int, d: Decision) -> AdviceOut:
        me = state.active("player", position)
        a = d.action
        if isinstance(a, MoveAction):
            action = MoveActionIn(
                kind="move",
                position=position,
                move_index=a.move_index,
                target_position=a.target_position,
            )
            summary = me.moves[a.move_index].name
            if a.target_position is not None and state.format.positions > 1:
                summary += f" → {state.active('opponent', a.target_position).name}"
        elif isinstance(a, SwitchAction):
            action = SwitchActionIn(kind="switch", position=position, slot=a.slot)
            summary = f"Switch to {state.player_team[a.slot].name}"
        else:
            assert isinstance(a, ItemAction)
            action = ItemActionIn(kind="item", position=position, item=a.item)
            summary = f"Use {ITEMS[a.item].name} on {me.name}"
        return cls(
            position=position,
            pokemon=me.name,
            action=action,
            summary=summary,
            coach_line=d.taunt,
            reasoning=d.reasoning,
            source=d.source,
        )


class TypeInfo(BaseModel):
    type: PokemonType
    color: str


class HealthOut(BaseModel):
    status: str
    pokemon_loaded: int
    opponent_agent: Literal["claude", "claude_code", "heuristic"]
    model: str | None
