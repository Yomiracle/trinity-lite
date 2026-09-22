"""Detect local agent CLIs and generate a safe starter agents config.

This module supports the five-minute onboarding path: probe PATH for
supported agent CLIs, then write an ``agents.local.json`` that runs
detected CLIs in command mode and keeps everything else on mock agents.

Safety rules:

- Commands are JSON arrays only; Trinity Lite executes them with
  ``shell=False``.
- No credentials, API keys, tokens, or private paths are ever written.
- An existing config is never overwritten unless ``force=True``.
- When no supported CLI is found, the generated config is mock-only and
  still fully usable.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

# Supported agent CLI presets. Each entry maps the Trinity Lite agent id to
# the executable probed on PATH and the safe command template aligned with
# docs/REAL_AGENTS.md and examples/agents.command.example.json.
AGENT_CLI_PRESETS: dict[str, dict[str, Any]] = {
    "codex": {
        "executable": "codex",
        "command": ["codex", "exec", "-C", "{cwd}", "{prompt}"],
    },
    "claude_code": {
        "executable": "claude",
        "command": ["claude", "-p", "{prompt}"],
    },
    "hermes": {
        "executable": "hermes",
        "command": ["hermes", "-z", "{prompt}"],
    },
}

DEFAULT_TIMEOUT = 1800
DEFAULT_CONFIG_NAME = "agents.local.json"


def detect_agent_clis() -> dict[str, str | None]:
    """Probe PATH for supported agent CLI executables.

    Returns a mapping of agent id to the resolved executable path, or None
    when the executable is not on PATH.
    """
    found: dict[str, str | None] = {}
    for agent_id, preset in AGENT_CLI_PRESETS.items():
        found[agent_id] = shutil.which(preset["executable"])
    return found


def build_starter_config(detected: dict[str, str | None]) -> dict[str, Any]:
    """Build an agents config from detection results.

    Detected CLIs become command-mode agents with safe JSON-array commands;
    undetected presets stay in mock mode so the bus works out of the box.
    """
    agents: dict[str, Any] = {}
    for agent_id, preset in AGENT_CLI_PRESETS.items():
        if detected.get(agent_id):
            agents[agent_id] = {
                "mode": "command",
                "command": list(preset["command"]),
                "timeout": DEFAULT_TIMEOUT,
            }
        else:
            agents[agent_id] = {
                "mode": "mock",
                "timeout": DEFAULT_TIMEOUT,
            }
    return {"agents": agents}


def run_init(out_path: str | None = None, force: bool = False) -> dict[str, Any]:
    """Detect agent CLIs and write a starter config.

    Returns a stable JSON-serializable result describing what was detected
    and what was written. Never raises for a missing CLI; a mock-only
    config is a successful outcome.
    """
    target = Path(out_path) if out_path else Path.cwd() / DEFAULT_CONFIG_NAME
    detected = detect_agent_clis()
    found = sorted(agent for agent, exe in detected.items() if exe)
    missing = sorted(agent for agent, exe in detected.items() if not exe)

    result: dict[str, Any] = {
        "config_path": str(target),
        "detected": [
            {"agent": agent, "executable": detected[agent]} for agent in found
        ],
        "missing": missing,
        "mock_only": not found,
        "forced": bool(force),
        "written": False,
        "skipped": False,
    }

    if target.exists() and not force:
        result["skipped"] = True
        result["reason"] = f"exists: {target} (use --force to overwrite)"
        return result

    config = build_starter_config(detected)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result["written"] = True
    return result
