# GitHub import security and limitations

RepoPilot imports code into a **local analysis workspace**. A public repository URL or its contents must not be treated as trusted merely because it came from GitHub.

## Accepted input

The `POST /api/analyze` endpoint accepts only a direct, credential-free HTTPS repository URL:

```text
https://github.com/<owner>/<repo>
https://github.com/<owner>/<repo>.git
```

`www.github.com` is accepted and canonicalized to `github.com`. Plain HTTP, embedded usernames or passwords, explicit ports, query strings, fragments, nested paths, encoded slash characters and paths that are not repository names are rejected. This deliberately excludes branch/commit URLs, GitHub Enterprise instances, SSH, git:// and local-file imports.

## Clone isolation

A canonicalized GitHub HTTPS URL is passed to the installed trusted Git executable as a **structured argv**, never through a shell. Host Git environment overrides, global/system Git configuration, credential helpers, hooks, filesystem monitors and unsafe file/ext transports are disabled for cloning. Interactive prompts are disabled, so imports cannot unexpectedly request local GitHub credentials. Git's stderr is not returned to API callers because it can include local paths or remote-server details.

A 12-hex-character import directory is **reserved atomically** before Git executes. If a generated ID collides with an existing import, that existing directory is never overwritten or removed. On clone errors or timeouts, only the directory successfully reserved by the current invocation is cleaned up. ZIP ingestion and delete/retention workflows have separate safeguards.

## Boundaries not yet covered

- RepoPilot is a local developer tool. **It is not authenticated, multi-tenant or ready for untrusted public hosting.**
- HTTPS does not verify repository contents. Imported source may contain prompt injections intended to mislead a local LLM; model output is untrusted analysis.
- Git and the TLS stack still execute with backend privileges. This is environment hardening, **not a process sandbox**.
- Git clone has a 90-second timeout and its **persisted output** is subject to the [shared storage budget](import-storage-budget.md). A clone can still consume excessive **transient disk, bandwidth or IO** before its final size is measured and rolled back. There is no hard peak-transfer quota or isolated worker budget.
- Existing local imports need independent review; hardening future Git clones is not retrospective sanitization.
- The local Ollama integration has additional trust boundaries requiring review before Internet exposure.

## Reproducible, network-free tests

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_repository_safety -v
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
```

Adversarial tests inject Git config overrides, credential helpers and dynamic-loader variables and verify the subprocess excludes them. Other tests simulate clone failure, 90-second timeouts and random-ID collisions; existing imported files must survive.

These are regression tests of defined boundaries, **not a comprehensive security audit**.
