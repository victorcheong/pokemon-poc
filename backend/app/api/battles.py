from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_battle_service
from app.domain.battle import Actions, BattleEngine, ItemAction, MoveAction, SwitchAction
from app.schemas import AdviceOut, AdviceRequest, BattleOut, CreateBattleRequest, TurnRequest
from app.services.battle_service import (
    BattleNotFoundError,
    BattleService,
    InvalidActionError,
    TurnResult,
)

router = APIRouter(prefix="/battles", tags=["battles"])


def _to_domain(req: TurnRequest) -> Actions:
    actions: Actions = {}
    for a in req.actions:
        if a.kind == "move":
            actions[a.position] = MoveAction("move", a.move_index, a.target_position)
        elif a.kind == "switch":
            actions[a.position] = SwitchAction("switch", a.slot)
        else:
            actions[a.position] = ItemAction("item", a.item)
    return actions


def _out(result: TurnResult) -> BattleOut:
    needed = BattleEngine().positions_needing_replacement(result.state, "player")
    return BattleOut.from_state(result.state, result.events, result.decisions, needed)


@router.post(
    "",
    response_model=BattleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Start a battle",
    description=(
        "Create a battle between your team and an opposing trainer. The trainer's team is "
        "generated to match your team's strength and their preferred types. "
        "`format: double` puts two Pokémon per side on the field."
    ),
    responses={422: {"description": "Invalid team, trainer or format"}},
)
def create_battle(
    body: CreateBattleRequest, service: Annotated[BattleService, Depends(get_battle_service)]
) -> BattleOut:
    try:
        result = service.create(body.team, body.trainer_id, body.format)
    except InvalidActionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(result)


@router.get(
    "/{battle_id}",
    response_model=BattleOut,
    summary="Get battle state",
    responses={404: {"description": "Unknown battle id"}},
)
def get_battle(
    battle_id: str, service: Annotated[BattleService, Depends(get_battle_service)]
) -> BattleOut:
    try:
        state = service.get(battle_id)
    except BattleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Battle not found") from exc
    return _out(TurnResult(state, [], []))


@router.post(
    "/{battle_id}/turn",
    response_model=BattleOut,
    summary="Play a turn",
    description=(
        "Submit your action(s). The opposing agent decides one action per active opponent "
        "Pokémon, the turn is resolved, and the resulting events are returned. "
        "When `phase` is `player_must_switch`, send switch actions for `positions_to_replace`."
    ),
    responses={
        404: {"description": "Unknown battle id"},
        409: {"description": "Action not allowed in the current phase or state"},
    },
)
async def take_turn(
    battle_id: str,
    body: TurnRequest,
    service: Annotated[BattleService, Depends(get_battle_service)],
) -> BattleOut:
    try:
        result = await service.take_turn(battle_id, _to_domain(body))
    except BattleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Battle not found") from exc
    except InvalidActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _out(result)


@router.post(
    "/{battle_id}/advice",
    response_model=AdviceOut,
    summary="Ask the coach",
    description=(
        "Have the agent recommend what one of *your* Pokémon should do this turn: a move "
        "(with target in doubles), a switch, or a bag item. The response includes an `action` "
        "object you can submit unchanged to the turn endpoint. Nothing is executed."
    ),
    responses={
        404: {"description": "Unknown battle id"},
        409: {"description": "Battle is over or the position cannot act"},
    },
)
async def get_advice(
    battle_id: str,
    body: AdviceRequest,
    service: Annotated[BattleService, Depends(get_battle_service)],
) -> AdviceOut:
    try:
        decision = await service.advise(battle_id, body.position)
        state = service.get(battle_id)
    except BattleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Battle not found") from exc
    except InvalidActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AdviceOut.from_decision(state, body.position, decision)
