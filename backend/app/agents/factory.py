from __future__ import annotations

import logging

from app.agents.base import OpponentAgent
from app.agents.claude import ClaudeAgent
from app.agents.claude_code import ClaudeCodeAgent
from app.agents.heuristic import HeuristicAgent
from app.config import AgentChoice, Settings

log = logging.getLogger(__name__)


def resolve_agent_choice(settings: Settings) -> AgentChoice:
    """Turn ``auto`` into a concrete choice based on what is available."""
    if settings.opponent_agent != "auto":
        return settings.opponent_agent
    if settings.anthropic_api_key:
        return "claude"
    if ClaudeCodeAgent.available(settings):
        return "claude_code"
    return "heuristic"


def build_agent(settings: Settings) -> OpponentAgent:
    choice = resolve_agent_choice(settings)
    if choice == "claude":
        if not settings.anthropic_api_key:
            raise RuntimeError("OPPONENT_AGENT=claude requires ANTHROPIC_API_KEY")
        log.info(
            "Opposing trainer: Claude API (%s, effort=%s)",
            settings.opponent_model,
            settings.opponent_effort,
        )
        return ClaudeAgent(settings)
    if choice == "claude_code":
        if not ClaudeCodeAgent.available(settings):
            raise RuntimeError(
                f"OPPONENT_AGENT=claude_code but '{settings.claude_code_bin}' was not found on PATH"
            )
        log.info(
            "Opposing trainer: Claude Code CLI (%s)", settings.opponent_model or "CLI default model"
        )
        return ClaudeCodeAgent(settings)
    log.warning("Opposing trainer: heuristic agent (no API key and no Claude Code CLI found)")
    return HeuristicAgent()
