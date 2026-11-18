# Security Policy

## Supported versions

Security fixes apply to the latest `1.x` release and the current `main` branch.

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
- The real-agent path runs the bounded Browser Use dependency against repository-owned fixtures;
  v1 does not execute arbitrary third-party agent commands.
- The optional Hronaut MCP command connects only to an `http://` loopback endpoint of an already
  running Hronaut app. Its bearer credential, if any, comes from `HRONAUT_MCP_TOKEN` or
  `HRONAUT_MCP_TOKEN_FILE`, and its model key from `DEEPSEEK_API_KEY` or `OPENROUTER_API_KEY` (or
  hidden input); resume keys and credentials are redacted from reports and traces.
- Generated evidence must not contain credentials or browser session data.
