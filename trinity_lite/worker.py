"""Worker loop for Trinity Lite."""

from __future__ import annotations

import atexit
import errno
import os
import signal
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any

from .adapters import AdapterError, build_adapter, load_specs
from .bus import TrinityBus

# ---------------------------------------------------------------------------
# Stop-flag pattern (Huey standard) — signal handlers ONLY set flags
# ---------------------------------------------------------------------------

_stop_flag: threading.Event = threading.Event()
"""Set by SIGTERM (immediate) or SIGINT (graceful — finish current task)."""


def _signal_handler(signum: int, frame: Any) -> None:  # pragma: no cover — signal integration
    reason = signal.Signals(signum).name
    if signum == signal.SIGTERM:
        print(f"[worker] received {reason} — shutting down", file=sys.stderr, flush=True)
        _stop_flag.set()
    elif signum == signal.SIGINT:
        print(f"[worker] received {reason} — finishing current task then exiting", file=sys.stderr, flush=True)
        _stop_flag.set()


def _install_signal_handlers() -> None:
    """Install POSIX signal handlers.  Idempotent — safe to call multiple times."""
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)


# ---------------------------------------------------------------------------
# PID file management
# ---------------------------------------------------------------------------

_PID_DIR = Path.home() / ".trinity" / "workers"


def _default_pid_path(agent: str) -> Path:
    """Return the default PID file path for a given agent."""
    return _PID_DIR / f"{agent}.pid"


def _acquire_pid_file(pid_path: Path) -> None:
    """Atomically create + lock a PID file.

    Raises RuntimeError if another daemon is already running for this agent.
    Cleans up stale PID files (process no longer exists).
    """
    # Ensure parent directory exists
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fd = os.open(str(pid_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        # PID file exists — check if process is still alive
        fd = _check_existing_pid(pid_path)
        if fd is None:
            # Stale — recreate after removing
            pid_path.unlink(missing_ok=True)
            fd = os.open(str(pid_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)

    with os.fdopen(fd, "w") as f:
        f.write(str(os.getpid()))

    # Register cleanup
    atexit.register(_cleanup_pid_file, pid_path)


def _check_existing_pid(pid_path: Path) -> int | None:
    """Check whether the PID stored in *pid_path* corresponds to a live process.

    Returns None if the PID file is stale (process gone), otherwise raises
    RuntimeError for a live duplicate daemon.
    """
    try:
        raw = pid_path.read_text().strip()
    except OSError:
        return None

    if not raw:
        return None

    try:
        pid = int(raw)
    except ValueError:
        return None

    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return None
        if exc.errno == errno.EPERM:
            raise RuntimeError(
                f"Worker daemon for agent is already running (PID {pid} exists). "
                f"PID file: {pid_path}"
            ) from None
        raise
    else:
        raise RuntimeError(
            f"Worker daemon for agent is already running (PID {pid}). "
            f"Remove {pid_path} if this is stale."
        )


def _cleanup_pid_file(pid_path: Path) -> None:
    """Remove the PID file on exit (registered via atexit)."""
    try:
        pid_path.unlink(missing_ok=True)
    except OSError:
        pass


def _read_pid_file(pid_path: Path) -> int | None:
    """Read the PID from a PID file, returning None if unreadable/corrupt."""
    try:
        raw = pid_path.read_text().strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Core worker functions
# ---------------------------------------------------------------------------


def run_once(
    agent: str,
    bus: TrinityBus,
    agents_path: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any] | None:
    task = bus.task_for_worker(agent, task_id=task_id)
    if task is None:
        return None
    specs = load_specs(agents_path)
    spec = specs.get(agent)
    if spec is None:
        return bus.finish_worker(task["id"], error=f"agent not configured: {agent}")
    try:
        result = build_adapter(spec).run(task)
        return bus.finish_worker(task["id"], result=result)
    except (KeyboardInterrupt, SystemExit, MemoryError):
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        return bus.finish_worker(task["id"], error=f"{exc}\n{tb}")


def run_loop(
    agent: str,
    bus: TrinityBus,
    agents_path: str | None = None,
    poll_seconds: float = 2.0,
    pid_file: str | Path | None = None,
) -> int:
    """Run the worker loop continuously until a stop signal is received.

    Args:
        agent: The agent id to process tasks for.
        bus: The TrinityBus instance.
        agents_path: Path to agents configuration JSON.
        poll_seconds: Sleep duration between polls when no task is available.
        pid_file: Optional path to the PID lock file.  When provided, the PID
            file is acquired before entering the loop and cleaned up on exit.

    Returns:
        Exit code: 0 on clean shutdown, 1 if pid lock acquisition fails.
    """
    if pid_file is not None:
        pid_path = Path(pid_file)
        try:
            _acquire_pid_file(pid_path)
        except RuntimeError as exc:
            print(f"[worker] {exc}", file=sys.stderr, flush=True)
            return 1

    _install_signal_handlers()

    while not _stop_flag.is_set():
        handled = run_once(agent, bus, agents_path)
        if handled is None and not _stop_flag.is_set():
            time.sleep(poll_seconds)

    print("[worker] daemon stopped", file=sys.stderr, flush=True)
    return 0
