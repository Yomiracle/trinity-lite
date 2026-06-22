"""Agent adapters for Trinity Lite workers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import string_list


@dataclass
class AgentSpec:
    agent_id: str
    mode: str = "mock"
    command: list[str] | None = None
    timeout: int = 1800
    roles: list[str] | None = None
    capabilities: list[str] | None = None
    priority: int = 0


class AdapterError(RuntimeError):
    """Raised when an agent adapter fails."""


class BaseAdapter:
    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec

    def run(self, task: dict[str, Any]) -> str:
        raise NotImplementedError


class MockAdapter(BaseAdapter):
    def run(self, task: dict[str, Any]) -> str:
        prompt = task["prompt"].strip().splitlines()[0][:120]
        return (
            f"[mock:{self.spec.agent_id}] completed task {task['id']} "
            f"({task.get('task_type') or 'unspecified'}): {prompt}"
        )


class CommandAdapter(BaseAdapter):
    def run(self, task: dict[str, Any]) -> str:
        if not self.spec.command:
            raise AdapterError(f"agent {self.spec.agent_id} has no command")
        command = [self._format_arg(arg, task) for arg in self.spec.command]
        executable = command[0]
        if shutil.which(executable) is None and not Path(executable).exists():
            raise AdapterError(f"executable not found for {self.spec.agent_id}: {executable}")
        uses_prompt_placeholder = any("{prompt}" in arg for arg in self.spec.command)
        completed = subprocess.run(
            command,
            cwd=task["cwd"],
            input=None if uses_prompt_placeholder else task["prompt"],
            text=True,
            capture_output=True,
            timeout=self.spec.timeout,
            shell=False,
            check=False,
        )
        output = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            detail = stderr or output or f"exit code {completed.returncode}"
            raise AdapterError(f"{self.spec.agent_id} failed: {detail}")
        return output or stderr or f"{self.spec.agent_id} completed without output"

    _RE_PLACEHOLDERS = re.compile(r'\{(prompt|cwd|task_id|task_type)\}')

    @staticmethod
    def _format_arg(arg: str, task: dict[str, Any]) -> str:
        replacements = {
            "prompt": task["prompt"],
            "cwd": task["cwd"],
            "task_id": task["id"],
            "task_type": task.get("task_type") or "",
        }
        return CommandAdapter._RE_PLACEHOLDERS.sub(lambda m: replacements.get(m.group(1), m.group(0)), arg)


def default_specs() -> dict[str, AgentSpec]:
    return {
        "codex": AgentSpec(
            agent_id="codex",
            roles=["primary_engineer"],
            capabilities=[
                "architecture_design",
                "code_edit",
                "documentation",
                "project_audit",
                "test_run",
            ],
            priority=80,
        ),
        "claude_code": AgentSpec(
            agent_id="claude_code",
            roles=["reviewer"],
            capabilities=["code_review", "risk_check", "source_scan"],
            priority=70,
        ),
        "hermes": AgentSpec(
            agent_id="hermes",
            roles=["orchestrator", "acceptance"],
            capabilities=["acceptance", "orchestration", "verification"],
            priority=60,
        ),
    }


def load_specs(path: str | os.PathLike[str] | None = None) -> dict[str, AgentSpec]:
    if path is None:
        return default_specs()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    specs: dict[str, AgentSpec] = {}
    for agent_id, raw in data.get("agents", {}).items():
        specs[agent_id] = AgentSpec(
            agent_id=agent_id,
            mode=raw.get("mode", "mock"),
            command=raw.get("command"),
            timeout=int(raw.get("timeout", 1800)),
            roles=string_list(raw.get("roles")),
            capabilities=string_list(raw.get("capabilities")),
            priority=int(raw.get("priority", 0)),
        )
    return specs or default_specs()


def build_adapter(spec: AgentSpec) -> BaseAdapter:
    if spec.mode == "mock":
        return MockAdapter(spec)
    if spec.mode == "command":
        return CommandAdapter(spec)
    raise AdapterError(f"unknown adapter mode for {spec.agent_id}: {spec.mode}")
