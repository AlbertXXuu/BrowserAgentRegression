# Security Policy

## Supported versions

Browser Agent Regression is pre-release Phase 0 software. Security fixes apply to the current
`main` branch only.

## Reporting a vulnerability

Do not open a public issue for a vulnerability involving credential exposure, unsafe fixture
serving, or command execution. Use GitHub's private vulnerability reporting for this repository
when available, or contact the repository owner privately through the contact method listed on
their GitHub profile.

Never attach API keys, session cookies, private URLs, or unredacted agent traces to an issue.

## Current trust boundary

- Packaged fixtures bind to `127.0.0.1`, not a public network interface.
- Deterministic tests require no model credential.
- The optional DeepSeek command accepts a key only from `DEEPSEEK_API_KEY` or hidden interactive
  input; it does not place the key in command arguments or evidence.
- The real-agent path runs the pinned Browser Use dependency against repository-owned fixtures;
  Phase 0 does not execute arbitrary third-party agent commands.
- Generated evidence must not contain credentials or browser session data.
