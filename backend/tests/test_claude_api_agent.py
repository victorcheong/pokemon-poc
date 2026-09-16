"""Exercises the Anthropic-API agent against a fake client (no network, no credits)."""

from __future__ import annotations

import json
import random
from types import SimpleNamespace

from app.agents import factory
from app.agents.claude import ClaudeAgent
from app.config import Settings
from app.domain.battle import (
    BattleEngine,
    BattleFormat,
    BattlePokemon,
    BattleState,
    MoveAction,
    SwitchAction,
)
from app.domain.trainers import get_trainer


def _state(repo, player_ids, opp_ids):
    st = BattleState.new(
        id="t",
        trainer=get_trainer("blaine"),
        player_team=[BattlePokemon.from_record(repo.get(i), 50) for i in player_ids],
        opponent_team=[BattlePokemon.from_record(repo.get(i), 50) for i in opp_ids],
        format=BattleFormat.SINGLE,
        agent_name="claude",
    )
    BattleEngine(random.Random(1)).start(st)
    return st


class _FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _agent(response, model: str = "claude-haiku-4-5") -> tuple[ClaudeAgent, _FakeMessages]:
    settings = Settings(
        opponent_agent="claude",
        anthropic_api_key="sk-ant-test",
        opponent_effort="low",
        opponent_model=model,
    )
    agent = ClaudeAgent(settings)
    fake = _FakeMessages(response)
    # Both the plain and the beta namespace point at the same recorder.
    agent._client = SimpleNamespace(messages=fake, beta=SimpleNamespace(messages=fake))  # type: ignore[assignment]
    return agent, fake


def _response(payload: dict, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=json.dumps(payload))],
    )


async def test_api_agent_parses_structured_json(repo):
    agent, fake = _agent(
        _response(
            {
                "action": "move",
                "move_index": 0,
                "target_position": None,
                "switch_slot": None,
                "item": None,
                "taunt": "Feel the heat!",
                "reasoning": "Highest damage.",
            }
        )
    )
    decision = await agent.choose_action(_state(repo, [9], [6]))
    assert decision.source == "claude"
    assert decision.action == MoveAction("move", 0, None)
    assert decision.taunt == "Feel the heat!"

    call = fake.calls[0]
    assert call["model"] == "claude-haiku-4-5"
    assert call["output_config"]["format"]["type"] == "json_schema"
    # Haiku does not take effort or refusal fallbacks; they must not be sent.
    assert "effort" not in call["output_config"]
    assert "fallbacks" not in call and "betas" not in call
    assert "Blaine" in call["system"][0]["text"]  # persona reached the system prompt
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}


async def test_api_agent_sends_effort_and_fallbacks_for_opus(repo):
    agent, fake = _agent(
        _response(
            {
                "action": "move",
                "move_index": 0,
                "target_position": None,
                "switch_slot": None,
                "item": None,
                "taunt": "!",
                "reasoning": "r",
            }
        ),
        model="claude-opus-5",
    )
    await agent.choose_action(_state(repo, [9], [6]))
    call = fake.calls[0]
    assert call["output_config"]["effort"] == "low"
    assert call["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in call["betas"]


async def test_api_agent_coach_uses_coach_prompt(repo):
    agent, fake = _agent(
        _response(
            {
                "action": "switch",
                "move_index": None,
                "target_position": None,
                "switch_slot": 1,
                "item": None,
                "taunt": "Bring in the tank!",
                "reasoning": "Better matchup.",
            }
        )
    )
    decision = await agent.advise(_state(repo, [129, 9], [6]), 0)
    assert decision.action == SwitchAction("switch", 1)
    assert "coach" in fake.calls[0]["system"][0]["text"].lower()
    assert "Blaine" not in fake.calls[0]["system"][0]["text"]


async def test_api_agent_refusal_falls_back_to_heuristic(repo):
    agent, _ = _agent(_response({}, stop_reason="refusal"))
    decision = await agent.choose_action(_state(repo, [9], [6]))
    assert decision.source == "heuristic"


def test_factory_builds_api_agent_when_key_present():
    settings = Settings(opponent_agent="auto", anthropic_api_key="sk-ant-test")
    assert factory.resolve_agent_choice(settings) == "claude"
    assert isinstance(factory.build_agent(settings), ClaudeAgent)


def test_blank_key_in_env_means_no_api_agent(monkeypatch):
    monkeypatch.setattr(factory.ClaudeCodeAgent, "available", staticmethod(lambda _s: False))
    settings = Settings(opponent_agent="auto", anthropic_api_key="")
    assert factory.resolve_agent_choice(settings) == "heuristic"
