# Security Policy

## Supported Versions

PRIMER is an open-source tool currently under active development. Security fixes are applied to the latest version on the `main` branch.

| Version | Supported |
|---------|-----------|
| latest (main) | ✓ |
| older commits | ✗ |

## Threat Model

PRIMER runs untrusted agent code inside hermetically isolated Docker containers. Key security properties:

- **Egress enforcement** — eval containers operate with an internal egress proxy. When `egress_enforced: true`, outbound traffic from the agent is blocked at the container network layer. This prevents agents from exfiltrating data or calling home during evaluation.
- **API keys as `SecretStr`** — all credentials are stored via pydantic-settings as `SecretStr` and never appear in logs, `repr()` output, or exported data.
- **No secrets in exports** — `primer export` writes only evaluation metrics and summary data. No keys, tokens, or internal paths appear in the JSON output or the static dashboard.
- **Pre-commit secret scanning** — `.pre-commit-config.yaml` runs `detect-secrets` on every commit. A known-safe baseline is at `.secrets.baseline`.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report security issues privately:

1. Email **msrichakrakanwa23@ifheindia.org** with subject line `[PRIMER Security]`.
2. Include: a description of the vulnerability, steps to reproduce, affected versions, and any potential impact.
3. You will receive a response within 72 hours.
4. Once confirmed, a fix will be prepared and a public advisory will be issued after the patch is available.

## Out of Scope

The following are not considered security vulnerabilities for this project:

- Vulnerabilities in the agent or LLM provider being evaluated (that is the subject of evaluation, not a PRIMER flaw)
- Issues requiring physical access to the host machine
- Social engineering attacks
- Rate limiting or denial-of-service against third-party APIs
