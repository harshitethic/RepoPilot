# Git clone subprocess limits and descendant cleanup

RepoPilot imports public GitHub repositories on a trusted local developer
machine. Limits on concurrent imports and persisted repositories do not stop
one clone from consuming excessive CPU, transient disk space, or process-tree
resources before returning. The original 90-second subprocess wait also did
not explicitly supervise Git's descendants.

## Enforced POSIX controls

The Git command now runs in a fresh process session under a small,
isolated Python launcher. The launcher applies operating-system limits
**before** replacing itself with Git. This avoids Python preexec_fn,
which is unsafe to use from a multithreaded API server.

| Control | Environment setting | Default | Enforcement |
| --- | --- | --- | --- |
| Wall-clock clone deadline | fixed | 90 seconds | Parent process supervisor |
| CPU time per OS process | REPOPILOT_CLONE_CPU_SECONDS | 45 seconds | POSIX RLIMIT_CPU |
| Maximum individual output-file size | REPOPILOT_CLONE_FILE_MIB | 256 MiB | POSIX RLIMIT_FSIZE |
| Virtual address-space size | REPOPILOT_CLONE_MEMORY_MIB | 1024 MiB | **Linux only**, RLIMIT_AS |
| Core dump size | fixed | zero | POSIX RLIMIT_CORE |

The configurable CPU range is 1–300 seconds; memory range is 128–4096
MiB; individual-file range is 1–2048 MiB. Invalid settings fail closed.
The existing separate cumulative persisted-storage budget and import
concurrency limit remain in effect.

Git and its child processes inherit the resource limits. The parent
supervisor terminates the **entire dedicated process group** after completion
or timeout, and reaps the direct child before releasing the import lock.
Git is launched with stdin, stdout and stderr redirected away from the API:
untrusted stderr cannot grow an in-memory buffer or be returned as a secret
bearing error. Failed imports delete only their freshly reserved workspace.

On macOS, RLIMIT_AS is **not used**, because virtual-address-space limits
frequently have a zero inherited hard limit and can break ordinary process
startup. macOS still receives process-group cleanup, wall deadlines,
RLIMIT_CPU, RLIMIT_FSIZE and disabled core dumps. Windows Git imports now
fail closed because this supervisor cannot guarantee Windows descendant
cleanup and POSIX limits. ZIP uploads are unaffected.

## Reproduce

From the project root after installing backend test dependencies:

    PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_clone_process_supervision.py -v
    PYTHONPATH=backend python -m unittest discover -s backend/tests -v

The real subprocess tests check launching the Git executable, clean
success and nonzero exits, redacted stderr, CPU-bound termination,
per-file size enforcement, invalid-config rejection, and a separate
descendant that would write a marker after a timeout but must be killed
with its process group. Linux runs an additional allocation test to
verify its address-space budget. No real GitHub credentials or user
repositories are used for these tests.

## Deliberate limitations

- **RLIMIT_CPU is per process**, not a cumulative CPU-time budget across
  a process tree. RLIMIT_FSIZE caps each file, not the total disk usage.
- RLIMIT_AS constrains virtual address space, not total RSS across all Git
  subprocesses, and is not enforced on macOS.
- A network transfer can consume traffic before timeout, and the ASGI
  server itself, ZIP extraction and local Ollama are *not* confined by
  these clone-specific rlimits.
- These are POSIX process-level safeguards, **not** an isolated container,
  filesystem quota, per-user authorization model or multi-tenant sandbox.
  Administrators still need cgroups/container process-group memory and
  CPU budgets, filesystem-level quotas, network restrictions and monitoring
  for hostile deployments.

Do not present this as production-grade untrusted-code execution isolation:
RepoPilot indexes source files but should never execute imported source.
