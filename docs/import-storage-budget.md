# Aggregate import storage: admission and rollback

RepoPilot is a **trusted local** codebase explorer, not a disk-quota-enforced
multi-tenant service. A repository-count limit (default 100) and per-ZIP
compressed/decompressed file size limits already exist. They do **not** bound
the sum of all retained imports.

## Persistent storage budget

- REPOPILOT_MAX_STORAGE_BYTES defaults to 2147483648 (2 GiB).
  It accepts integer byte values from 1 to 1 TiB; invalid settings fail closed.
- REPOPILOT_MAX_REPOSITORIES continues to default to 100.
- Both limits are checked **inside the same cross-process file lock**, stored
  beside the import directory. ZIP extraction, Git cloning, inventory, cleanup
  and deletion serialize against this lock.
- The scanner totals regular-file *logical* sizes within recognized repository
  directories, including cloned .git object files. It does not follow
  symlinks out of the workspace. It is not a disk-block usage metric.
- ZIP contents are preflighted, then rejected before workspace creation if
  their declared uncompressed sizes exceed the remaining budget. ZIP streaming
  still checks actual bytes written and post-extraction usage. Failures roll
  back only the current import.
- Git clones cannot know their final size up front. After Git completes (or
  fails/times out), RepoPilot checks the full persistent import total. If it
  exceeds the quota, the newly created import is removed. Earlier imports
  survive.

The lock is intended for **local processes sharing the same filesystem and
same configured import directory**. Do not delete its lock file while backend
processes are running. An external tool that writes directly into imports
without using RepoPilot's lock can bypass this admission mechanism.

## Reproduce

From the repository root, install backend test dependencies and run:

    PYTHONPATH=backend python -m unittest discover -s backend/tests -p test_aggregate_import_budget.py -v
    PYTHONPATH=backend python -m unittest discover -s backend/tests -v

The tests use disposable directories, no remote Git clones or external LLM
calls. They verify rejection before ZIP reservation, exact-fit imports,
capacity reclaimed after deletion, preservation of pre-existing files when a
simulated Git clone exceeds budget, and thread/process races admitting at
most one import when only one slot remains.

## Important limitations

**A Git clone can exceed the remaining quota temporarily** during download,
object unpacking and checkout. The 90-second Git timeout is not a bytes/sec,
peak-storage, CPU or network budget. Upload staging files outside the import
directory are not included in persistent import totals. A malicious or buggy
client can still saturate temporary storage or local resources through
concurrent requests. Synchronous ZIP extraction runs in a worker thread
so it does not hold the async HTTP event loop. Multipart requests now have
[early ASGI body admission](request-body-admission.md), but this does not
bound concurrent connections, reverse-proxy/server buffering, or worker-level
resource consumption. This change is **not** a production-grade filesystem
quota, authentication, or process sandbox.

Before deploying to untrusted users, add storage-level quotas, per-client
authentication and rate limits, hard worker-level resource isolation, and
observable cleanup/alerting.
