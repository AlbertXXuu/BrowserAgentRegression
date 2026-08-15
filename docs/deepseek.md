# Run Browser Use with DeepSeek

[简体中文](deepseek.zh-CN.md)

This optional path runs a real Browser Use agent against the same local fixtures and scores the
result with independent DOM checkpoints. It sends the task and Browser Use page representation to
the paid DeepSeek API. The deterministic `oracle` and `calibrate` commands remain offline and do
not need an API key.

## 1. Prerequisites

- Python 3.11–3.13
- A DeepSeek API key and sufficient account balance
- The current repository checkout

Create or manage keys in the [DeepSeek platform](https://platform.deepseek.com/api_keys). The
[official API documentation](https://api-docs.deepseek.com/) lists the current endpoint and
models. This project defaults to `deepseek-v4-flash`; `deepseek-v4-pro` is also accepted.

## 2. Install the optional agent dependencies

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,agent]"
python -m playwright install chromium
```

The `[agent]` extra is intentionally separate. Users running only deterministic calibration do
not install Browser Use or provider SDKs.

## 3. Start with one agent smoke attempt

Do not put the key on the command line. Run:

```powershell
browser-agent-regression deepseek `
  --task preferences.notifications.v1 `
  --variant clean `
  --runs 1 `
  --headed `
  --output deepseek-smoke.json
```

If `DEEPSEEK_API_KEY` is not already set, the CLI prints the key-management link and prompts:

```text
DeepSeek API key (masked with *; not stored):
```

On Windows, paste the key and press Enter. One `*` is displayed for each character, confirming
that the paste worked without revealing the key. Other platforms use hidden input. The key is
passed directly to the provider client and is not written to the report, repository, shell
history, or a `.env` file.

The command exits with `0` only when independent DOM checkpoints pass. A model saying that it
finished is not sufficient. One agent attempt can make multiple paid model requests as it takes
steps or retries, so check the provider balance before running.

The repository-local adapter requests DeepSeek JSON Output for Browser Use's complete
`AgentOutput` object and validates it with the framework's Pydantic schema. It does not repair or
guess malformed action parameters. This avoids relying on a forced function call for a deeply
nested agent-output schema while leaving Browser Use's action execution unchanged.

## 4. Run the three-task Gate C check

After the single attempt works, run all three clean tasks once:

```powershell
browser-agent-regression deepseek --runs 1 --output deepseek-gate-c.json
```

The default real-agent condition is `clean` to avoid accidental API spend. Add conditions only
when needed:

```powershell
browser-agent-regression deepseek `
  --runs 3 `
  --variant clean `
  --variant popup-overlay `
  --output deepseek-repeated.json
```

That example makes 18 agent attempts: 3 tasks × 2 conditions × 3 runs. Each attempt can make
multiple paid API requests. The CLI prints the agent-attempt count before starting.

## 5. Non-interactive use

For CI or another non-interactive shell, provide `DEEPSEEK_API_KEY` through that system's secret
store. The command refuses non-interactive execution when the variable is missing.

To set the key for only the current PowerShell process without showing it while typing:

```powershell
$secureKey = Read-Host "DeepSeek API key" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
```

Run the command, then clear the process variable:

```powershell
Remove-Item Env:DEEPSEEK_API_KEY
```

Do not use `setx` for a short-lived test key, commit `.env` files, or attach credentials and
unredacted private traces to issues.

## What the report means

Real-agent reports keep evidence schema `0.2` and use `evidence_kind: "real-agent"`. They record
the Browser Use version, model, non-vision setting, browser display mode, run count, fixture hashes,
duration, checkpoint results, and bounded errors. They never record the API key. These controlled
local results prove integration feasibility; they are not a general DeepSeek or Browser Use
benchmark.
