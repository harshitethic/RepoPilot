"""Supervise untrusted Git clone subprocesses and inherited POSIX rlimits."""
import os
from pathlib import Path
import signal
import subprocess
import sys

LIMITED_EXEC = Path(__file__).with_name("limited_exec.py")
DEFAULT_CLONE_DEADLINE_SECONDS = 90
DEFAULT_CPU_SECONDS = 45
DEFAULT_MEMORY_MIB = 1024
DEFAULT_FILE_MIB = 256


def _setting(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        parsed = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Git clone resource configuration.") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError("Invalid Git clone resource configuration.")
    return parsed


def clone_limits() -> tuple[int, int, int]:
    """Per-process POSIX budgets. CPU time is not summed across descendants."""
    cpu = _setting("REPOPILOT_CLONE_CPU_SECONDS", DEFAULT_CPU_SECONDS, 1, 300)
    memory = _setting("REPOPILOT_CLONE_MEMORY_MIB", DEFAULT_MEMORY_MIB, 128, 4096)
    file_size = _setting("REPOPILOT_CLONE_FILE_MIB", DEFAULT_FILE_MIB, 1, 2048)
    return cpu, memory * 1024**2, file_size * 1024**2


def _kill_group(process: subprocess.Popen) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()


def run_guarded_git(argv, *, cwd, env, timeout=DEFAULT_CLONE_DEADLINE_SECONDS):
    """Run one command with no inherited terminal, output buffers or helpers.

    POSIX: new process session, inherited per-process rlimits for Git and its
    descendants; kill the entire process group on completion or timeout.
    Other OSes: only the direct process is supervised, without POSIX rlimits.
    """
    if os.name == "posix":
        cpu, memory, file_size = clone_limits()
        command = [
            sys.executable, "-I", str(LIMITED_EXEC),
            str(cpu), str(memory), str(file_size), *argv,
        ]
    else:
        # Windows lacks POSIX groups/resource limits; fail closed instead of
        # claiming that terminating git.exe also terminates its descendants.
        raise RuntimeError("Safely bounded Git imports require POSIX.")

    process = subprocess.Popen(
        command, cwd=cwd, env=env, shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        process.wait(timeout=timeout)
        return subprocess.CompletedProcess(argv, process.returncode)
    finally:
        # No Git child may outlive the import admission lock, even if Git
        # itself exits while a descendant continues running.
        try:
            _kill_group(process)
        finally:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
