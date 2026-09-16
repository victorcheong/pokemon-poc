from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.domain.trainers import TRAINERS, get_trainer
from app.schemas import TrainerOut

router = APIRouter(prefix="/trainers", tags=["trainers"])


@router.get("", response_model=list[TrainerOut], summary="List trainers")
def list_trainers() -> list[TrainerOut]:
    return [TrainerOut.from_trainer(t) for t in TRAINERS]


@router.get(
    "/{trainer_id}",
    response_model=TrainerOut,
    summary="Trainer details",
    responses={404: {"description": "Unknown trainer id"}},
)
def get_trainer_route(trainer_id: str) -> TrainerOut:
    trainer = get_trainer(trainer_id)
    if trainer is None:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return TrainerOut.from_trainer(trainer)
