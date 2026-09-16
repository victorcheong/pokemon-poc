"""Exercises the Claude Code CLI agent against a fake `claude` binary (no network)."""

import json
import random
import stat
from pathlib import Path

import pytest

from app.agents import factory
from app.agents.claude_code import ClaudeCodeAgent
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
        trainer=get_trainer("lance"),
        player_team=[BattlePokemon.from_record(repo.get(i), 50) for i in player_ids],
        opponent_team=[BattlePokemon.from_record(repo.get(i), 50) for i in opp_ids],
        format=BattleFormat.SINGLE,
        agent_name="claude_code",
    )
    BattleEngine(random.Random(1)).start(st)
    return st


def _fake_cli(tmp_path: Path, body: str, exit_code: int = 0) -> Path:
    script = tmp_path / "claude"
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s' '{body}'\n"
        'printf \'%s\' "$@" > "$(dirname "$0")/args.txt"\n'
        'printf \'%s\' "$MAX_THINKING_TOKENS" > "$(dirname "$0")/env.txt"\n'
        f"exit {exit_code}\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _settings(tmp_path: Path, **kw) -> Settings:
    return Settings(claude_code_bin=str(tmp_path / "claude"), opponent_agent="claude_code", **kw)


async def test_uses_structured_output(repo, tmp_path):
    payload = json.dumps(
        {
            "is_error": False,
            "result": "ignored",
            "structured_output": {
                "action": "move",
                "move_index": 1,
                "target_position": None,
                "switch_slot": None,
                "taunt": "Feel the power of dragons!",
                "reasoning": "Best expected damage.",
            },
        }
    )
    _fake_cli(tmp_path, payload)
    agent = ClaudeCodeAgent(_settings(tmp_path))
    st = _state(repo, [6], [149])
    decision = await agent.choose_action(st)
    assert decision.source == "claude_code"
    assert decision.action == MoveAction("move", 1, None)
    assert decision.taunt == "Feel the power of dragons!"
    args = (tmp_path / "args.txt").read_text()
    assert "--json-schema" in args and "--output-format" in args
    assert "Lance" in args  # persona reached the system prompt
    assert "claude-haiku-4-5" in args  # CLI uses the same OPPONENT_MODEL as the API
    assert (tmp_path / "env.txt").read_text() == "0"  # extended thinking disabled


async def test_parses_result_when_no_structured_output(repo, tmp_path):
    inner = json.dumps(
        {
            "action": "switch",
            "move_index": None,
            "target_position": None,
            "switch_slot": 1,
            "taunt": "Go!",
            "reasoning": "r",
        }
    )
    payload = json.dumps({"is_error": False, "result": inner}).replace("'", "'\\''")
    _fake_cli(tmp_path, payload)
    agent = ClaudeCodeAgent(_settings(tmp_path))
    st = _state(repo, [6], [149, 130])
    decision = await agent.choose_action(st)
    assert decision.action == SwitchAction("switch", 1)


async def test_invalid_choice_falls_back_to_heuristic(repo, tmp_path):
    payload = json.dumps(
        {
            "is_error": False,
            "structured_output": {
                "action": "move",
                "move_index": 9,
                "target_position": None,
                "switch_slot": None,
                "taunt": "x",
                "reasoning": "y",
            },
        }
    )
    _fake_cli(tmp_path, payload)
    agent = ClaudeCodeAgent(_settings(tmp_path))
    decision = await agent.choose_action(_state(repo, [6], [149]))
    assert decision.source == "heuristic"


async def test_cli_failure_falls_back_to_heuristic(repo, tmp_path):
    _fake_cli(tmp_path, "boom", exit_code=1)
    agent = ClaudeCodeAgent(_settings(tmp_path))
    decision = await agent.choose_action(_state(repo, [6], [149]))
    assert decision.source == "heuristic"


async def test_replacement_goes_through_cli(repo, tmp_path):
    payload = json.dumps(
        {
            "is_error": False,
            "structured_output": {
                "action": "switch",
                "move_index": None,
                "target_position": None,
                "switch_slot": 1,
                "taunt": "Rise!",
                "reasoning": "r",
            },
        }
    )
    _fake_cli(tmp_path, payload)
    agent = ClaudeCodeAgent(_settings(tmp_path))
    st = _state(repo, [6], [149, 130])
    st.opponent_team[0].current_hp = 0
    decision = await agent.choose_replacement(st)
    assert decision.action == SwitchAction("switch", 1) and decision.source == "claude_code"


@pytest.mark.parametrize(
    ("api_key", "cli_present", "expected"),
    [
        ("sk-ant-x", True, "claude"),
        (None, True, "claude_code"),
        (None, False, "heuristic"),
    ],
)
def test_auto_agent_resolution(monkeypatch, api_key, cli_present, expected):
    monkeypatch.setattr(factory.ClaudeCodeAgent, "available", staticmethod(lambda _s: cli_present))
    settings = Settings(opponent_agent="auto", anthropic_api_key=api_key)
    assert factory.resolve_agent_choice(settings) == expected
