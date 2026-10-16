# Local-only API trust boundary

RepoPilot is a developer application, **not an authenticated public service**. Its routes can import code, query local Ollama, inspect imported source and delete imported workspaces. CORS does not authenticate requests and cannot protect these operations from non-browser clients.

## Fail-closed default

The FastAPI middleware checks the **actual ASGI client peer IP** with Python's standard-library `ipaddress` module. Only IPv4 and IPv6 loopback peers are accepted (including IPv4-mapped loopback addresses). Numeric private/LAN/container IPs and unknown host strings are rejected with HTTP 403, including for OpenAPI and health routes. Spoofed `Host`, `Forwarded`, `X-Forwarded-For` and `X-Real-IP` headers are not used to grant access.

Local development through `http://127.0.0.1` or `http://localhost` continues to work.

## Important remaining limitations

- **A loopback restriction is not authentication.** Another process or user on the same host may still call the API. This does not implement per-user authorization, account isolation, permissions, authentication or per-IP quotas.
- **Same-host reverse proxy danger:** A public reverse proxy forwarding to RepoPilot over loopback makes requests appear local. Do **not** expose a same-host proxy publicly without independently deployed authentication and authorization. Likewise, SSH tunnels and forwarding tools can bridge external clients into loopback.
- Deployment should bind the API to `127.0.0.1`, not `0.0.0.0`, as a separate network-layer defense. The middleware is defense in depth, not a substitute for the bind address/firewall.
- Proxy middleware or ASGI servers that rewrite `scope.client` using forwarded headers must be configured carefully. Untrusted proxy headers can compromise this safeguard before the request reaches it.
- Local Ollama prompts may include source content. Do not send private source to providers you have not explicitly approved.
- Git cloning and ZIP extraction still require resource budgeting and external threat review.

## Test it without external services

```bash
PYTHONPATH=backend python -m unittest backend.tests.test_loopback_boundary -v
PYTHONPATH=backend python -m unittest discover -s backend/tests -v
```

The ASGI tests simulate real local and remote client peer IPs. They also spoof forwarded/host headers to ensure those strings cannot bypass the middleware. No network, credential or Ollama account is required for these regressions.
