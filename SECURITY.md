# Security Policy

## Supported version

Security fixes are made against the current `main` branch.

## Reporting

Please avoid public disclosure of exploitable vulnerabilities or credentials. Include reproduction steps, affected inputs, impact, and sanitized logs when reporting a security issue.

## Security boundaries

RepoPilot accepts repository URLs and inspects source code. Reports are especially useful for:

- path traversal while cloning or browsing files;
- access to files outside the cloned repository;
- unsafe repository URL handling;
- command execution where only inspection is expected;
- cross-site scripting from repository content;
- prompt-injection paths that expose local files or secrets;
- accidental leakage of Ollama or environment configuration.

A cloned repository must be treated as untrusted data. RepoPilot's normal inspection flow should not execute code from that repository.

## Secrets

Do not commit API keys, tokens, local model credentials, or private repository contents.
