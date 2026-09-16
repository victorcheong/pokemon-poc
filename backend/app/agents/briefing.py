"""Turn the battle state into a compact briefing from one side's point of view.

Used both for the opposing trainer (``side="opponent"``) and for the coach that advises
the player (``side="player"``).
"""

from __future__ import annotations

from app.domain.battle import BattlePokemon, BattleState, Side, Stat, expected_damage, opposite
from app.domain.items import ITEMS
from app.domain.moves import MoveCategory


def _types(p: BattlePokemon) -> str:
    return "/".join(t.value.title() for t in p.record.types)


def _stages(p: BattlePokemon) -> str:
    parts = [f"{s.value}{'+' if v > 0 else ''}{v}" for s, v in p.stages.items() if v]
    return ", ".join(parts) if parts else "none"


def _best_hit(attacker: BattlePokemon, defender: BattlePokemon) -> float:
    return max(
        (
            expected_damage(attacker, defender, m)
            for m in attacker.moves
            if m.category is not MoveCategory.STATUS
        ),
        default=0.0,
    )


def describe_pokemon(p: BattlePokemon) -> str:
    return (
        f"{p.name} ({_types(p)}) HP {p.current_hp}/{p.max_hp} "
        f"Atk {p.effective_stat(Stat.ATTACK)} Def {p.effective_stat(Stat.DEFENSE)} "
        f"SpA {p.effective_stat(Stat.SP_ATTACK)} SpD {p.effective_stat(Stat.SP_DEFENSE)} "
        f"Spe {p.effective_stat(Stat.SPEED)}; stat stages: {_stages(p)}"
    )


def describe_moves(attacker: BattlePokemon, foes: list[tuple[int, BattlePokemon]]) -> str:
    """One line per move; damaging moves show expected damage against every foe position."""
    lines = []
    for i, (move, pp) in enumerate(zip(attacker.moves, attacker.pp, strict=True)):
        if move.category is MoveCategory.STATUS:
            detail = f"status: {move.description}"
        else:
            parts = []
            for pos, foe in foes:
                eff = foe.record.effectiveness_against(move.type)
                exp = expected_damage(attacker, foe, move)
                pct = 100 * exp / foe.max_hp if foe.max_hp else 0
                parts.append(
                    f"vs target {pos} {foe.name}: x{eff:g}, ~{exp:.0f} dmg (~{pct:.0f}% HP)"
                )
            detail = (
                f"{move.category.value} power {move.power} acc {move.accuracy or 100}%; "
                + "; ".join(parts)
            )
        prio = f" priority +{move.priority}" if move.priority else ""
        lines.append(
            f"  [{i}] {move.name} ({move.type.value.title()}{prio}) PP {pp}/{move.pp} - {detail}"
        )
    return "\n".join(lines)


def build_briefing(
    state: BattleState,
    position: int = 0,
    *,
    side: Side = "opponent",
    for_replacement: bool = False,
) -> str:
    foe_side = opposite(side)
    me = state.active(side, position)
    foes = [(p, state.active(foe_side, p)) for p in state.living_positions(foe_side)]
    partner = next(
        ((p, state.active(side, p)) for p in state.living_positions(side) if p != position),
        None,
    )

    bench = []
    for slot in state.bench(side):
        p = state.team(side)[slot]
        best = max((_best_hit(p, foe) for _, foe in foes), default=0.0)
        threat = max((_best_hit(foe, p) for _, foe in foes), default=0.0)
        bench.append(
            f"  [slot {slot}] {p.name} ({_types(p)}) HP {p.current_hp}/{p.max_hp}; "
            f"best hit on a foe ~{best:.0f}, foes' best hit on it ~{threat:.0f}"
        )

    recent = "\n".join(f"  - {e.text}" for e in state.log[-8:]) or "  (battle just started)"
    fmt = "DOUBLE battle (2 Pokémon per side)" if state.format.positions == 2 else "single battle"

    sections = [f"Turn {state.turn + 1}. This is a {fmt}."]
    you = f"YOUR POKÉMON (position {position}): {describe_pokemon(me)}"
    if for_replacement:
        you += " (FAINTED - you must replace it)"
    sections.append(you)
    if partner is not None:
        sections.append(
            f"YOUR PARTNER (position {partner[0]}, controlled separately): "
            f"{describe_pokemon(partner[1])}"
        )
    for pos, foe in foes:
        sections.append(f"FOE at target position {pos}: {describe_pokemon(foe)}")
        sections.append(f"  Its known moves:\n{describe_moves(foe, [(position, me)])}")
    if not for_replacement:
        sections.append(f"Your Pokémon's moves:\n{describe_moves(me, foes)}")
    sections.append("Your bench:\n" + ("\n".join(bench) if bench else "  (no other Pokémon)"))
    if side == "player" and not for_replacement:
        bag = ", ".join(
            f"{ITEMS[k].name} x{n} ({ITEMS[k].description})"
            for k, n in state.player_items.items()
            if n > 0
        )
        sections.append(
            "Your bag (using an item takes the turn, heals before any move lands): "
            + (bag or "empty")
        )
    alive = sum(1 for p in state.team(foe_side) if not p.fainted)
    sections.append(
        f"Foe's remaining team: {alive}/{len(state.team(foe_side))} Pokémon able to battle."
    )
    sections.append(f"Recent events:\n{recent}")
    return "\n\n".join(sections)
