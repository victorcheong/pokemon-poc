"""Claude-powered opposing trainer via the Claude Code CLI.

Uses ``claude -p`` (non-interactive mode) with ``--json-schema`` for structured output.
The CLI authenticates with the user's Claude subscription (``claude login``), so no API
key or prepaid credits are needed. Intended for local / personal use: it runs on the
machine (or container) where the CLI is installed and logged in.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile

from app.agents.decision import DECISION_SCHEMA, TrainerDecision
from app.agents.heuristic import HeuristicAgent
from app.agents.llm_base import LLMTrainerAgent
from app.config import Settings
from app.domain.battle import BattleState, Side

log = logging.getLogger(__name__)


class ClaudeCodeAgent(LLMTrainerAgent):
    name = "claude_code"

    def __init__(self, settings: Settings, fallback: HeuristicAgent | None = None):
        super().__init__(fallback)
        self._settings = settings
        self._bin = shutil.which(settings.claude_code_bin) or settings.claude_code_bin
        # Run the CLI from a scratch directory so it never picks up a project's CLAUDE.md.
        self._workdir = tempfile.mkdtemp(prefix="pokemon-trainer-")

    @staticmethod
    def available(settings: Settings) -> bool:
        return shutil.which(settings.claude_code_bin) is not None

    def _command(self, system: str, prompt: str) -> list[str]:
        cmd = [
            self._bin,
            "-p",
            prompt,
            "--system-prompt",
            system,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(DECISION_SCHEMA),
            "--tools",
            "",  # pure reasoning, no file/shell tools
            "--no-session-persistence",  # don't litter ~/.claude with battle sessions
            "--setting-sources",
            "",  # ignore user/project settings (hooks, MCP, model)
        ]
        cmd += ["--model", self._settings.opponent_model]
        return cmd

    async def ask(
        self, state: BattleState, briefing: str, instruction: str, side: Side = "opponent"
    ) -> TrainerDecision:
        system = self.system_prompt(state, side)
        prompt = f"{briefing}\n\n{instruction}"
        env = {
            **os.environ,
            "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            # The CLI turns extended thinking on by default; the briefing already contains
            # every number the model needs, and thinking made Haiku spend ~3k tokens and
            # 40+ seconds per decision. Off, a decision is ~600 tokens in under 10 seconds.
            "MAX_THINKING_TOKENS": "0",
        }
        proc = await asyncio.create_subprocess_exec(
            *self._command(system, prompt),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self._workdir,
            env=env,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout=self._settings.opponent_timeout_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            raise TimeoutError("claude CLI timed out") from None

        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited {proc.returncode}: {err.decode(errors='replace')[-400:]}"
            )

        payload = json.loads(out.decode())
        if payload.get("is_error"):
            raise RuntimeError(f"claude CLI error: {payload.get('result')}")

        structured = payload.get("structured_output")
        if structured is None:
            # Older CLIs put the JSON text in `result`.
            structured = json.loads(payload["result"])
        return TrainerDecision.model_validate(structured)
