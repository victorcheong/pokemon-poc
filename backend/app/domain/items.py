"""Healing items the player can use from the Bag. Trainers don't use items."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Item:
    id: str
    name: str
    heal: int  # HP restored; 0 = restore to full
    description: str


ITEMS: dict[str, Item] = {
    "potion": Item("potion", "Potion", 60, "Restores 60 HP."),
    "hyper_potion": Item("hyper_potion", "Hyper Potion", 120, "Restores 120 HP."),
    "full_restore": Item("full_restore", "Full Restore", 0, "Fully restores HP."),
}

DEFAULT_BAG: dict[str, int] = {"potion": 2, "hyper_potion": 1, "full_restore": 1}
