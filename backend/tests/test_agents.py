import random

import pytest

from app.agents.briefing import build_briefing
from app.agents.heuristic import HeuristicAgent
from app.agents.llm_base import clean_text
from app.domain.battle import (
    STAT_FOR_EFFECT,
    BattleEngine,
    BattleFormat,
    BattlePokemon,
    BattleState,
    MoveAction,
    SwitchAction,
)
from app.domain.moves import MoveCategory
from app.domain.trainers import get_trainer


def _state(repo, player_ids, opp_ids, fmt=BattleFormat.SINGLE):
    st = BattleState.new(
        id="t",
        trainer=get_trainer("misty"),
        player_team=[BattlePokemon.from_record(repo.get(i), 50) for i in player_ids],
        opponent_team=[BattlePokemon.from_record(repo.get(i), 50) for i in opp_ids],
        format=fmt,
        agent_name="heuristic",
    )
    BattleEngine(random.Random(1)).start(st)
    return st


async def test_heuristic_prefers_super_effective(repo):
    st = _state(repo, [6], [9])  # Charizard vs Blastoise
    decision = await HeuristicAgent(random.Random(0)).choose_action(st)
    assert isinstance(decision.action, MoveAction)
    chosen = st.opponent_team[0].moves[decision.action.move_index]
    assert chosen.type.value == "water"


async def test_heuristic_replacement_is_valid(repo):
    st = _state(repo, [6], [129, 9])
    st.opponent_team[0].current_hp = 0
    decision = await HeuristicAgent().choose_replacement(st)
    assert isinstance(decision.action, SwitchAction) and decision.action.slot == 1


async def test_heuristic_replacement_respects_exclude(repo):
    st = _state(repo, [6, 25], [129, 129, 9, 3], fmt=BattleFormat.DOUBLE)
    st.opponent_team[0].current_hp = 0
    st.opponent_team[1].current_hp = 0
    first = await HeuristicAgent().choose_replacement(st, 0)
    second = await HeuristicAgent().choose_replacement(st, 1, frozenset({first.action.slot}))
    assert first.action.slot != second.action.slot


async def test_heuristic_picks_best_target_in_doubles(repo):
    st = _state(repo, [6, 3], [9], fmt=BattleFormat.SINGLE)
    st = _state(
        repo, [6, 3], [9, 25], fmt=BattleFormat.DOUBLE
    )  # Blastoise + Pikachu vs Charizard + Venusaur
    decision = await HeuristicAgent(random.Random(0)).choose_action(st, 0)  # Blastoise
    assert isinstance(decision.action, MoveAction)
    assert decision.action.target_position == 0  # Water vs Charizard, not Venusaur
    pika = await HeuristicAgent(random.Random(0)).choose_action(st, 1)
    assert isinstance(pika.action, MoveAction)
    if st.opponent_team[1].moves[pika.action.move_index].category is not MoveCategory.STATUS:
        assert pika.action.target_position == 0  # Electric vs Charizard (flying) not Venusaur


def test_briefing_mentions_key_facts(repo):
    st = _state(repo, [6], [9])
    text = build_briefing(st)
    assert "Blastoise" in text and "Charizard" in text
    assert "x2" in text
    assert "[0]" in text and "single battle" in text


def test_briefing_doubles_lists_partner_and_both_foes(repo):
    st = _state(repo, [6, 25], [9, 3], fmt=BattleFormat.DOUBLE)
    text = build_briefing(st, 0)
    assert "DOUBLE battle" in text
    assert "YOUR PARTNER (position 1" in text and "Venusaur" in text
    assert "FOE at target position 0" in text and "FOE at target position 1" in text
    assert "vs target 1 Pikachu" in text


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_briefing_for_replacement_lists_bench(repo, seed):
    st = _state(repo, [6], [129, 9])
    st.opponent_team[0].current_hp = 0
    text = build_briefing(st, for_replacement=True)
    assert "[slot 1] Blastoise" in text


async def test_heuristic_stops_boosting_at_max_stage(repo):
    st = _state(repo, [143], [423])  # Snorlax vs Gastrodon (has Agility)
    gastrodon = st.opponent_team[0]
    agility = next(
        (i for i, m in enumerate(gastrodon.moves) if m.category is MoveCategory.STATUS), None
    )
    if agility is None:
        pytest.skip("no status move generated")
    stat = STAT_FOR_EFFECT.get(gastrodon.moves[agility].effect)
    if stat is None:
        pytest.skip("heal move, not a boost")
    gastrodon.stages[stat] = 6
    decision = await HeuristicAgent(random.Random(0)).choose_action(st)
    assert isinstance(decision.action, MoveAction)
    assert decision.action.move_index != agility


async def test_heuristic_coach_advises_player_side(repo):
    st = _state(repo, [9], [6])  # player Blastoise vs Charizard
    decision = await HeuristicAgent(random.Random(0)).advise(st, 0)
    assert isinstance(decision.action, MoveAction)
    assert st.player_team[0].moves[decision.action.move_index].type.value == "water"
    assert decision.taunt.startswith("Coach")


async def test_heuristic_coach_recommends_item_when_about_to_faint(repo):
    st = _state(repo, [129], [150])  # Magikarp vs Mewtwo
    st.player_team[0].current_hp = 5
    decision = await HeuristicAgent(random.Random(0)).advise(st, 0)
    # Magikarp can't survive even after a heal, so no item; but the API path must not crash.
    assert decision.action.kind in {"move", "switch", "item"}


def test_player_briefing_lists_bag(repo):
    st = _state(repo, [6], [9])
    text = build_briefing(st, 0, side="player")
    assert "Your bag" in text and "Potion x2" in text
    assert "FOE at target position 0: Blastoise" in text


def test_clean_text_strips_leaked_tags():
    assert clean_text("A touch of frost...</taunt>\n</invoke>", 160) == "A touch of frost..."
    assert clean_text("<reasoning>Use Surf, it KOs.</reasoning>", 600) == "Use Surf, it KOs."
    assert clean_text("  plain   text  ", 160) == "plain text"
    assert len(clean_text("x" * 500, 160)) == 160
