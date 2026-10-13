# Repository import trust boundaries

RepoPilot imports untrusted repositories. The application should never execute imported source files merely to answer a user's codebase questions.

## Implemented defenses

- Accept public GitHub repository URLs only with exactly two path segments.
- Give each imported ZIP or clone an unpredictable repository ID; check IDs before reading them.
- Cap ZIP compressed size, declared uncompressed size, and entry count. Refuse unsafe paths.
- Use a random temporary ZIP file per upload, preventing concurrent requests from overwriting each other.
- Skip symlinks, Git internals, dependencies and oversized source files while indexing. A malicious Git symlink cannot direct the indexer outside the imported tree.
- Avoid publishing raw ZIP-analysis server exceptions to clients.
- Include repository-ingestion regression checks in CI.

## Remaining deployment work

This is a local development tool, not a hardened multi-tenant internet service. Public deployments need authenticated quotas, isolated resources, timeouts, cleanup of old imported repositories, and monitoring. Uploaded repositories and prompt context are untrusted data and can include prompt-injection text.

Run: PYTHONPATH=backend python -m unittest discover -s backend/tests -v
