import random

import pytest

from app.domain.battle import (
    EMPTY,
    BattleEngine,
    BattleFormat,
    BattlePokemon,
    BattleState,
    MoveAction,
    Phase,
    Stat,
    SwitchAction,
    compute_damage,
    hp_at_level,
    stat_at_level,
)
from app.domain.moves import Move, MoveCategory
from app.domain.trainers import get_trainer
from app.domain.types import PokemonType


def _state(repo, player_ids, opp_ids, seed=7, fmt=BattleFormat.SINGLE):
    st = BattleState.new(
        id="test",
        trainer=get_trainer("brock"),
        player_team=[BattlePokemon.from_record(repo.get(i), 50) for i in player_ids],
        opponent_team=[BattlePokemon.from_record(repo.get(i), 50) for i in opp_ids],
        format=fmt,
        agent_name="heuristic",
    )
    engine = BattleEngine(random.Random(seed))
    engine.start(st)
    return st, engine


def test_level_50_stat_formulas():
    assert hp_at_level(35, 50) == 110  # Pikachu
    assert stat_at_level(55, 50) == 75  # Pikachu attack


def test_damage_respects_type_chart(repo):
    blastoise = BattlePokemon.from_record(repo.get(9), 50)
    charizard = BattlePokemon.from_record(repo.get(6), 50)
    surf = next(m for m in blastoise.moves if m.name == "Surf")
    res = compute_damage(
        blastoise, charizard, surf, random.Random(0), force_roll=1.0, force_crit=False
    )
    assert res.effectiveness == 2.0
    assert res.damage > charizard.max_hp * 0.5


def test_immunity_deals_zero(repo):
    gengar = BattlePokemon.from_record(repo.get(94), 50)
    snorlax = BattlePokemon.from_record(repo.get(143), 50)
    body_slam = Move("Body Slam", PokemonType.NORMAL, MoveCategory.PHYSICAL, 85, 100, 15)
    res = compute_damage(
        snorlax, gengar, body_slam, random.Random(0), force_roll=1.0, force_crit=False
    )
    assert res.effectiveness == 0 and res.damage == 0


def test_turn_order_by_speed(repo):
    st, engine = _state(repo, [25], [143])  # Pikachu (fast) vs Snorlax (slow)
    events = engine.run_turn(st, {0: MoveAction("move", 1)}, {0: MoveAction("move", 1)})
    move_events = [e for e in events if e.type == "move"]
    assert move_events[0].side == "player"


def test_priority_beats_speed(repo):
    st, engine = _state(repo, [143], [25])  # Snorlax vs Pikachu
    quick = next(i for i, m in enumerate(st.player_team[0].moves) if m.priority > 0)
    events = engine.run_turn(st, {0: MoveAction("move", quick)}, {0: MoveAction("move", 1)})
    move_events = [e for e in events if e.type == "move"]
    assert move_events[0].side == "player"


def test_status_move_raises_stage(repo):
    st, engine = _state(repo, [68], [74])
    machamp = st.player_team[0]
    idx = next((i for i, m in enumerate(machamp.moves) if m.category is MoveCategory.STATUS), None)
    if idx is None:
        pytest.skip("no status move")
    engine.run_turn(st, {0: MoveAction("move", idx)}, {0: MoveAction("move", 1)})
    assert any(v > 0 for v in machamp.stages.values())


def test_switching_and_forced_replacement(repo):
    st, engine = _state(repo, [129, 6], [6])  # Magikarp then Charizard vs Charizard
    engine.run_turn(st, {0: SwitchAction("switch", 1)}, {0: MoveAction("move", 1)})
    assert st.player_active == [1]
    engine.run_turn(st, {0: SwitchAction("switch", 0)}, {0: MoveAction("move", 0)})
    for _ in range(10):
        if st.phase is not Phase.CHOOSE_ACTION:
            break
        engine.run_turn(st, {0: MoveAction("move", 1)}, {0: MoveAction("move", 0)})
    assert st.phase is Phase.PLAYER_MUST_SWITCH
    assert engine.positions_needing_replacement(st, "player") == [0]
    with pytest.raises(ValueError):
        engine.run_turn(st, {0: MoveAction("move", 0)}, {0: MoveAction("move", 0)})
    engine.replace_fainted(st, "player", 0, 1)
    assert st.phase is Phase.CHOOSE_ACTION and st.active("player").name == "Charizard"


def test_battle_ends_with_winner(repo):
    st, engine = _state(repo, [150], [129])  # Mewtwo vs Magikarp
    while st.phase is Phase.CHOOSE_ACTION:
        engine.run_turn(st, {0: MoveAction("move", 0)}, {0: MoveAction("move", 1)})
    assert st.phase is Phase.FINISHED and st.winner == "player"
    assert st.log[-1].type == "battle_end"


def test_pp_is_consumed(repo):
    st, engine = _state(repo, [25], [143])
    before = st.player_team[0].pp[1]
    engine.run_turn(st, {0: MoveAction("move", 1)}, {0: MoveAction("move", 1)})
    assert st.player_team[0].pp[1] == before - 1


def test_effective_stat_stage_multiplier(repo):
    p = BattlePokemon.from_record(repo.get(25), 50)
    base = p.effective_stat(Stat.ATTACK)
    p.stages[Stat.ATTACK] = 2
    assert p.effective_stat(Stat.ATTACK) == base * 2


def test_damage_events_carry_target(repo):
    st, engine = _state(repo, [25], [143])
    events = engine.run_turn(st, {0: MoveAction("move", 1)}, {0: MoveAction("move", 1)})
    dmg = [e for e in events if e.type == "damage"]
    assert dmg and all(e.target_side and e.target_slot is not None for e in dmg)
    assert dmg[0].side == "player" and dmg[0].target_side == "opponent"


# ---- doubles ---------------------------------------------------------------


def test_double_battle_starts_with_two_per_side(repo):
    st, _ = _state(repo, [6, 25, 143], [9, 3], fmt=BattleFormat.DOUBLE)
    assert st.player_active == [0, 1] and st.opponent_active == [0, 1]
    assert st.bench("player") == [2] and st.bench("opponent") == []
    assert sum(1 for e in st.log if e.type == "switch") == 4


def test_double_requires_action_per_position(repo):
    st, engine = _state(repo, [6, 25], [9, 3], fmt=BattleFormat.DOUBLE)
    with pytest.raises(ValueError, match="one action for each active position"):
        engine.run_turn(
            st, {0: MoveAction("move", 1)}, {0: MoveAction("move", 1), 1: MoveAction("move", 1)}
        )


def test_double_targets_are_honoured(repo):
    st, engine = _state(repo, [6, 25], [9, 3], fmt=BattleFormat.DOUBLE)  # vs Blastoise, Venusaur
    events = engine.run_turn(
        st,
        {
            0: MoveAction("move", 1, 1),
            1: MoveAction("move", 1, 0),
        },  # Charizard->Venusaur, Pikachu->Blastoise
        {0: MoveAction("move", 3), 1: MoveAction("move", 3)},  # opponents use status moves
    )
    hits = {e.pokemon: e for e in events if e.type == "damage" and e.side == "player"}
    if "Venusaur" in hits:
        assert (
            hits["Venusaur"].target_position == 1 and hits["Venusaur"].move_type == PokemonType.FIRE
        )
    if "Blastoise" in hits:
        assert hits["Blastoise"].target_position == 0


def test_double_redirects_when_target_fainted(repo):
    st, engine = _state(
        repo, [150, 6], [129, 129], fmt=BattleFormat.DOUBLE
    )  # Mewtwo + Charizard vs 2 Magikarp
    events = engine.run_turn(
        st,
        {0: MoveAction("move", 0, 0), 1: MoveAction("move", 0, 0)},  # both aim at Magikarp #0
        {0: MoveAction("move", 1, 0), 1: MoveAction("move", 1, 0)},
    )
    dmg = [e for e in events if e.type == "damage" and e.side == "player" and e.damage > 0]
    assert {e.target_position for e in dmg} == {0, 1}  # second attack was redirected
    assert st.phase is Phase.FINISHED and st.winner == "player"


def test_double_empty_position_when_bench_exhausted(repo):
    st, engine = _state(repo, [150, 6], [129, 129, 129], fmt=BattleFormat.DOUBLE)
    engine.run_turn(
        st,
        {0: MoveAction("move", 0, 0), 1: MoveAction("move", 0, 1)},
        {0: MoveAction("move", 1, 0), 1: MoveAction("move", 1, 0)},
    )
    # Both Magikarp fainted; only one replacement exists, so one position stays fillable
    # and the other becomes empty.
    needed = engine.positions_needing_replacement(st, "opponent")
    assert len(needed) == 1
    other = 1 - needed[0]
    assert st.opponent_active[other] == EMPTY
    engine.replace_fainted(st, "opponent", needed[0], 2)
    assert st.living_positions("opponent") == [needed[0]]


def test_double_player_replacement_flow(repo):
    st, engine = _state(repo, [129, 129, 6], [150, 150], fmt=BattleFormat.DOUBLE)
    engine.run_turn(
        st,
        {0: MoveAction("move", 1, 0), 1: MoveAction("move", 1, 0)},
        {0: MoveAction("move", 0, 0), 1: MoveAction("move", 0, 1)},
    )
    assert st.phase is Phase.PLAYER_MUST_SWITCH
    needed = engine.positions_needing_replacement(st, "player")
    assert len(needed) == 1  # only Charizard left on the bench
    engine.replace_fainted(st, "player", needed[0], 2)
    assert st.phase is Phase.CHOOSE_ACTION
    assert st.living_positions("player") == [needed[0]]
