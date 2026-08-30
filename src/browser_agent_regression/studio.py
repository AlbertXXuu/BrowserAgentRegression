"""Dependency-free, loopback-only visual interface for regression evidence."""

from __future__ import annotations

import hashlib
import json
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any

from .runner import TASKS, VARIANTS, build_report

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_PORT = 7870
ASSET_SHA256 = {
    "assets/brand/alvenx-wordmark.svg": "8ae10e02c27091e29e0191a7934506118f144aae11898b20222d7f9d587e2662",
    "assets/brand/alvenx-monogram.svg": "45367ec933c2ed8565cdf9e683fd4b856057d375435b46c62acb4fbb2cbeef16",
    "assets/fonts/InstrumentSans-wdth-wght.woff2": "aa72922aafcc0dc18f36ec1d805b0212057dabe8b9d5b8b57f67035aea1b826d",
}
TASK_LABELS = {
    "checkout.basic.v1": "Checkout completion",
    "catalog.find-and-save.v1": "Catalog find and save",
    "preferences.notifications.v1": "Notification preferences",
}


@dataclass(frozen=True)
class StudioAddress:
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT

    def validate(self) -> None:
        if self.host not in LOOPBACK_HOSTS:
            raise ValueError("Studio is local-only; --host must be a loopback address")
        if not 0 <= self.port <= 65535:
            raise ValueError("--port must be between 0 and 65535")


def _repository_evidence_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "evidence"
        / "v1.0.0-calibration.json"
    )


def _evidence_view(report: dict[str, Any]) -> dict[str, Any]:
    """Reduce a verified report to the evidence needed by the interface."""

    summaries = {
        (entry["task_id"], entry["driver"], entry["variant"]): entry
        for entry in report["summaries"]
    }
    regressions = {
        entry["task_id"]: entry
        for entry in report["regressions"]
        if entry["variant"] == "popup-overlay"
    }
    tasks: list[dict[str, Any]] = []
    for task_id in report["configuration"]["tasks"]:
        regression = regressions.get(task_id, {})
        baseline = summaries.get((task_id, "reference", "popup-overlay"), {})
        candidate = summaries.get((task_id, "popup-blind", "popup-overlay"), {})
        clean_reference = summaries.get((task_id, "reference", "clean"), {})
        clean_candidate = summaries.get((task_id, "popup-blind", "clean"), {})
        popup_attempts = [
            attempt
            for attempt in report["attempts"]
            if attempt["task_id"] == task_id
            and attempt["variant"] == "popup-overlay"
        ]
        checkpoint_ids = list(popup_attempts[0]["checkpoints"]) if popup_attempts else []
        checkpoints = []
        for checkpoint_id in checkpoint_ids:
            rates: dict[str, float] = {}
            for driver in ("reference", "popup-blind"):
                driver_attempts = [
                    attempt for attempt in popup_attempts if attempt["driver"] == driver
                ]
                passed = sum(
                    bool(attempt["checkpoints"].get(checkpoint_id))
                    for attempt in driver_attempts
                )
                rates[driver] = passed / len(driver_attempts) if driver_attempts else 0.0
            checkpoints.append(
                {
                    "id": checkpoint_id,
                    "referenceRate": rates["reference"],
                    "candidateRate": rates["popup-blind"],
                }
            )
        tasks.append(
            {
                "id": task_id,
                "label": TASK_LABELS.get(task_id, task_id),
                "cleanParity": clean_reference.get("success_rate")
                == clean_candidate.get("success_rate"),
                "baselineRate": float(baseline.get("success_rate", 0.0)),
                "candidateRate": float(candidate.get("success_rate", 0.0)),
                "firstFailure": regression.get("failed_checkpoint", "not detected"),
                "agreement": float(regression.get("failure_checkpoint_agreement", 0.0)),
                "checkpoints": checkpoints,
            }
        )
    return {
        "source": report.get("command", "calibrate"),
        "protocol": report["protocol_id"],
        "createdAt": report.get("created_at"),
        "attemptCount": len(report["attempts"]),
        "taskCount": len(tasks),
        "variantCount": len(VARIANTS),
        "regressionCount": len(regressions),
        "browser": report.get("environment", {}).get("browser", "unknown"),
        "tasks": tasks,
    }


def load_committed_evidence(path: Path | None = None) -> dict[str, Any]:
    evidence_path = path or _repository_evidence_path()
    if not evidence_path.is_file():
        return json.loads(
            files("browser_agent_regression")
            .joinpath("assets/evidence/studio-v1.json")
            .read_text(encoding="utf-8")
        )
    report = json.loads(evidence_path.read_text(encoding="utf-8"))
    return _evidence_view(report)


def _asset_bytes(relative: str) -> bytes:
    payload = files("browser_agent_regression").joinpath(relative).read_bytes()
    if hashlib.sha256(payload).hexdigest() != ASSET_SHA256[relative]:
        raise RuntimeError(f"bundled AlvenX asset failed integrity check: {relative}")
    return payload


def _validated_demo_runs(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 3:
        raise ValueError("runs must be an integer from 1 to 3")
    return value


def run_live_demo(*, runs: int = 1) -> dict[str, Any]:
    """Run the public deterministic calibration without writing a report to disk."""

    from .cli import _run_matrix

    runs = _validated_demo_runs(runs)
    attempts, browser_version = _run_matrix(
        drivers=["reference", "popup-blind"],
        tasks=list(TASKS),
        variants=["clean", "popup-overlay"],
        runs=runs,
        headed=False,
    )
    report = build_report(
        attempts,
        command="demo",
        runs=runs,
        tasks=list(TASKS),
        variants=["clean", "popup-overlay"],
        browser_version=browser_version,
    )
    return _evidence_view(report)


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="color-scheme" content="light">
  <meta name="theme-color" content="#EEF6FF">
  <title>Browser Agent Regression · AlvenX</title>
  <link rel="icon" href="/assets/monogram.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/studio.css">
  <script src="/studio.js" defer></script>
</head>
<body>
  <div class="page-frame">
    <header class="site-header liquid-surface">
      <a class="brand-link" href="#top" aria-label="Browser Agent Regression home">
        <img src="/assets/wordmark.svg" alt="AlvenX">
      </a>
      <nav aria-label="Page sections">
        <a href="#evidence">Evidence</a><a href="#tasks">Tasks</a><a href="#boundary">Method</a>
      </nav>
      <span class="local-badge"><i aria-hidden="true"></i>Studio v1.1.1 · Evidence v1.0.0</span>
    </header>

    <main id="top">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow"><span></span>AGENT RELIABILITY · CONTROLLED UI</p>
          <h1>Find the first point<br><em>where an agent drifts.</em></h1>
          <p class="lede">Compare browser-agent behavior across meaning-preserving interface changes,
            score checkpoints independently of the DOM, and keep the first failure as durable evidence.</p>
          <div class="hero-actions">
            <button class="liquid-button" id="run-demo" type="button">
              <span>Run local demo</span><b aria-hidden="true">↗</b>
            </button>
            <label class="run-control" for="demo-runs"><span>Repetitions</span>
              <select id="demo-runs" aria-describedby="run-status">
                <option value="1" selected>1 · quick</option>
                <option value="2">2 · compare</option>
                <option value="3">3 · steadier</option>
              </select>
            </label>
            <a class="text-link" href="#evidence">Inspect preserved v1 evidence ↓</a>
          </div>
          <p class="run-status" id="run-status" role="status" aria-live="polite">
            Built-in drivers · 12 controlled browser attempts · in-memory result
          </p>
        </div>
        <aside class="hero-proof" aria-labelledby="proof-title">
          <div class="proof-top"><span>CALIBRATION SIGNAL</span><strong id="proof-status">Verified</strong></div>
          <h2 id="proof-title">Reference / candidate checkpoints</h2>
          <div class="checkpoint-plot" id="checkpoint-plot" role="img"
               aria-label="Loading committed checkpoint evidence">
            <span class="plot-loading">Loading committed checkpoint evidence…</span>
          </div>
          <p id="proof-caption">The first committed calibration task will appear here.</p>
        </aside>
      </section>

      <section class="evidence-section" id="evidence">
        <header class="section-heading">
          <div><p class="eyebrow">PRESERVED V1.0.0 EVIDENCE</p><h2>One regression, localized three ways.</h2></div>
          <code id="protocol">loading protocol…</code>
        </header>
        <div class="metric-grid" aria-label="Evidence summary">
          <article><strong id="metric-tasks">—</strong><span>resettable tasks</span></article>
          <article><strong id="metric-variants">—</strong><span>UI variants</span></article>
          <article><strong id="metric-attempts">—</strong><span>measured attempts</span></article>
          <article><strong id="metric-regressions">—</strong><span>controlled regressions</span></article>
        </div>
        <aside class="use-guide" aria-label="How to read this calibration">
          <strong>Run → compare → localize</strong>
          <span>Choose repetitions, compare reference and popup-blind success, then inspect the first failed checkpoint. Repetitions change measurement confidence, not the controlled task set.</span>
        </aside>
      </section>

      <section class="task-section" id="tasks" aria-labelledby="tasks-title">
        <header class="section-heading compact">
          <div><p class="eyebrow">FIRST-FAILURE CHECKPOINTS</p><h2 id="tasks-title">The result remains inspectable.</h2></div>
          <span class="source-pill" id="evidence-source">Committed evidence</span>
        </header>
        <div class="task-grid" id="task-grid"><p class="loading">Loading local evidence…</p></div>
      </section>

      <section class="boundary" id="boundary">
        <div><p class="eyebrow">CALIBRATION METHOD</p><h2>Controlled changes,<br>inspectable evidence.</h2></div>
        <p>The popup-blind driver creates a known regression so the harness can verify clean parity,
          regression magnitude, and first-failure localization end to end. Model-backed adapters use
          the same evidence contract for named agents and configurations.</p>
      </section>
    </main>
    <footer><img src="/assets/monogram.svg" alt=""><span>Browser Agent Regression · AlvenX open source</span></footer>
  </div>
</body>
</html>
"""


STUDIO_CSS = r"""@font-face{font-family:"Instrument Sans";src:url("/assets/font.woff2") format("woff2");font-style:normal;font-weight:400 700;font-display:swap}
:root{color-scheme:light;--canvas:#eef6ff;--primary:#0b1731;--reading:#334155;--muted:#52647a;--blue:#2563eb;--indigo:#4f46e5;--violet:#7c3aed;--glass:rgb(255 255 255 / 28%);--glass-hover:rgb(255 255 255 / 35%);--edge:rgb(255 255 255 / 68%);--highlight:rgb(255 255 255 / 72%);--ease:cubic-bezier(.22,1,.36,1)}
*{box-sizing:border-box}html{scroll-behavior:smooth;background:var(--canvas)}body{margin:0;min-width:1080px;background:radial-gradient(circle at 15% 3%,#fff 0,transparent 34%),radial-gradient(circle at 87% 12%,rgb(196 214 255 / 52%),transparent 32%),linear-gradient(145deg,#fbfdff 0%,#f1f7ff 49%,#e7f1ff 100%);color:var(--primary);font-family:"Instrument Sans",Arial,sans-serif;text-rendering:optimizeLegibility}.page-frame{width:min(100%,1480px);margin:auto;padding:clamp(18px,3vw,44px) clamp(18px,5vw,74px) 30px}.site-header{position:fixed;z-index:100;top:14px;left:50%;display:flex;width:calc(min(100%,1480px) - 2 * clamp(18px,5vw,74px));min-height:70px;align-items:center;gap:28px;padding:12px 18px 12px 22px;border-radius:26px;transform:translateX(-50%)}.liquid-surface{border:1px solid var(--edge);background:rgb(255 255 255 / 26%);box-shadow:inset 0 1px 0 var(--highlight),inset 0 -1px 0 rgb(79 70 229 / 6%),0 24px 72px rgb(71 105 148 / 12%);-webkit-backdrop-filter:blur(18px) saturate(148%);backdrop-filter:blur(18px) saturate(148%)}.brand-link{display:flex;width:160px;border-radius:12px}.brand-link img{display:block;width:100%;height:auto}.site-header nav{display:flex;gap:6px;margin-left:auto}.site-header nav a{padding:9px 12px;border:1px solid transparent;border-radius:999px;color:var(--muted);font-size:.74rem;font-weight:620;letter-spacing:.08em;text-decoration:none;text-transform:uppercase;transition:220ms}.site-header nav a.active,.site-header nav a:hover{border-color:rgb(255 255 255 / 82%);background:rgb(255 255 255 / 35%);color:var(--primary)}.local-badge{display:flex;align-items:center;gap:8px;padding:9px 12px;border-radius:999px;background:rgb(255 255 255 / 42%);color:#315a88;font-size:.74rem;font-weight:620}.local-badge i{width:7px;height:7px;border-radius:50%;background:#2563eb;box-shadow:0 0 12px rgb(37 99 235 / 35%)}.hero{display:grid;min-height:min(760px,calc(100vh - 104px));grid-template-columns:minmax(0,1.4fr) minmax(330px,.6fr);align-items:center;gap:clamp(50px,7vw,112px);padding:clamp(80px,11vh,140px) 0}.eyebrow{margin:0 0 24px;color:#315a88;font-size:.76rem;font-weight:650;letter-spacing:.13em;text-transform:uppercase}.hero .eyebrow{display:flex;align-items:center;gap:10px}.hero .eyebrow span{width:7px;height:7px;border-radius:50%;background:var(--blue)}h1,h2,p{font-variation-settings:"wdth" 100}.hero h1{margin:0;font-size:clamp(3.3rem,6.7vw,7rem);font-weight:570;letter-spacing:-.04em;line-height:.95}.hero h1 em{display:block;margin-top:.14em;background:linear-gradient(100deg,var(--blue),var(--indigo) 48%,var(--violet));background-clip:text;-webkit-background-clip:text;color:transparent;font-style:normal}.lede{max-width:700px;margin:36px 0 0;color:var(--reading);font-size:clamp(1.02rem,1.45vw,1.25rem);line-height:1.7}.hero-actions{display:flex;align-items:center;flex-wrap:wrap;gap:24px;margin-top:40px}.liquid-button{position:relative;display:inline-flex;min-height:58px;align-items:center;gap:14px;padding:0 25px 0 27px;overflow:hidden;border:1px solid var(--edge);border-radius:999px;outline:0;background-color:var(--glass);background-image:radial-gradient(circle at 24% -12%,rgb(255 255 255 / 76%),transparent 43%),linear-gradient(118deg,rgb(255 255 255 / 18%),transparent 58%,rgb(255 255 255 / 12%));box-shadow:inset 0 1px 0 var(--highlight),inset 0 -1px 0 rgb(79 70 229 / 8%),0 24px 72px rgb(71 105 148 / 14%);-webkit-backdrop-filter:blur(24px) saturate(148%);backdrop-filter:blur(24px) saturate(148%);color:var(--primary);font:620 .98rem/1 "Instrument Sans",sans-serif;cursor:pointer;transition:420ms var(--ease)}.liquid-button::before{content:"";position:absolute;inset:-2px auto -2px -45%;width:40%;background:linear-gradient(105deg,transparent 22%,rgb(255 255 255 / 58%) 49%,transparent 70%);transform:skewX(-16deg);transition:transform 620ms var(--ease)}.liquid-button:hover{border-color:rgb(255 255 255 / 84%);background-color:var(--glass-hover);transform:translateY(-3px);box-shadow:inset 0 1px 0 rgb(255 255 255 / 80%),0 30px 80px rgb(71 105 148 / 17%)}.liquid-button:hover::before{transform:translateX(380%) skewX(-16deg)}.liquid-button:active{transform:translateY(-1px) scale(.985)}.liquid-button:focus-visible,.text-link:focus-visible,a:focus-visible{outline:3px solid rgb(37 99 235 / 45%);outline-offset:4px}.liquid-button:disabled{cursor:wait;opacity:.62;transform:none}.text-link{color:var(--reading);font-weight:600;text-decoration:none}.run-status{min-height:1.5em;margin:18px 0 0;color:var(--muted);font-size:.82rem}.hero-proof{align-self:center;padding:30px;border:1px solid rgb(255 255 255 / 82%);border-radius:32px;background:rgb(255 255 255 / 48%);box-shadow:inset 0 1px 0 #fff,0 30px 90px rgb(71 105 148 / 12%)}.proof-top{display:flex;align-items:center;justify-content:space-between;color:#315a88;font-size:.72rem;font-weight:650;letter-spacing:.1em}.proof-top strong{padding:7px 10px;border-radius:999px;background:#edfdf5;color:#18744b;letter-spacing:0}.proof-orbit{position:relative;width:min(100%,270px);aspect-ratio:1;margin:24px auto}.proof-orbit::before,.proof-orbit::after,.proof-orbit i{position:absolute;border:1px solid rgb(79 70 229 / 16%);border-radius:50%;content:""}.proof-orbit::before{inset:7%}.proof-orbit::after{inset:22%}.proof-orbit i:nth-child(1){inset:37%}.proof-orbit i:nth-child(2){top:7%;left:48%;width:14px;height:14px;border:0;background:var(--blue);box-shadow:0 0 25px rgb(37 99 235 / 48%)}.proof-orbit i:nth-child(3){right:10%;bottom:21%;width:11px;height:11px;border:0;background:var(--violet)}.proof-orbit b{position:absolute;inset:43%;border-radius:50%;background:linear-gradient(135deg,var(--blue),var(--violet));box-shadow:0 10px 36px rgb(79 70 229 / 28%)}.hero-proof p{margin:0;color:var(--reading);font-size:.92rem;line-height:1.6}.evidence-section,.task-section{padding:clamp(70px,9vw,126px) 0}.section-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:30px;margin-bottom:38px}.section-heading .eyebrow{margin-bottom:12px}.section-heading h2,.boundary h2{max-width:780px;margin:0;font-size:clamp(2.1rem,4.2vw,4.5rem);font-weight:560;letter-spacing:-.035em;line-height:1.02}.section-heading code{max-width:360px;padding:9px 12px;border-radius:10px;background:rgb(255 255 255 / 42%);color:var(--muted);font-size:.72rem;overflow-wrap:anywhere}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid rgb(71 105 148 / 18%);border-bottom:1px solid rgb(71 105 148 / 18%)}.metric-grid article{min-height:165px;padding:30px 26px;border-right:1px solid rgb(71 105 148 / 18%)}.metric-grid article:last-child{border:0}.metric-grid strong{display:block;font-size:clamp(2.5rem,4vw,4.3rem);font-weight:560;letter-spacing:-.04em}.metric-grid span{color:var(--muted);font-size:.88rem}.source-pill{padding:8px 11px;border-radius:999px;background:rgb(255 255 255 / 50%);color:#315a88;font-size:.76rem;font-weight:620}.task-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.task-card{position:relative;min-height:330px;padding:26px;border:1px solid rgb(255 255 255 / 78%);border-radius:24px;background:rgb(255 255 255 / 46%);box-shadow:inset 0 1px 0 #fff,0 16px 48px rgb(71 105 148 / 8%)}.task-index{color:#315a88;font-size:.72rem;font-weight:700;letter-spacing:.1em}.task-card h3{margin:66px 0 30px;font-size:clamp(1.45rem,2vw,2rem);font-weight:580;letter-spacing:-.025em}.rate-pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}.rate-pair div{padding:13px;border-radius:14px;background:rgb(255 255 255 / 52%)}.rate-pair span,.failure span{display:block;color:var(--muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.08em}.rate-pair strong{font-size:1.18rem}.failure{margin-top:18px;padding-top:18px;border-top:1px solid rgb(71 105 148 / 14%)}.failure code{display:block;margin-top:7px;color:var(--primary);font-size:.78rem;overflow-wrap:anywhere}.loading{color:var(--muted)}.boundary{display:grid;grid-template-columns:1fr 1fr;gap:clamp(30px,8vw,130px);align-items:end;margin:50px 0 100px;padding:clamp(34px,5vw,66px);border-radius:32px;background:linear-gradient(135deg,rgb(37 99 235 / 9%),rgb(124 58 237 / 8%));box-shadow:inset 0 1px 0 rgb(255 255 255 / 75%)}.boundary p:last-child{margin:0;color:var(--reading);font-size:1rem;line-height:1.72}footer{display:flex;align-items:center;gap:14px;padding:24px 0;color:var(--muted);font-size:.78rem}footer img{width:34px;height:34px;border-radius:9px}
body{line-height:1.62}.hero h1{overflow:visible;line-height:1.02}.hero h1 em{margin-top:.12em;padding-bottom:.06em}.hero-actions{gap:18px 24px}.run-control{display:grid;gap:5px;color:var(--muted);font-size:.72rem;font-weight:620}.run-control select{min-height:44px;padding:0 36px 0 14px;border:1px solid rgb(71 105 148 / 18%);border-radius:14px;background:rgb(255 255 255 / 68%);color:var(--primary);font:600 .86rem/1.55 "Instrument Sans",sans-serif}.run-control select:focus-visible{outline:3px solid rgb(37 99 235 / 45%);outline-offset:3px}.metric-grid{border:1px solid rgb(71 105 148 / 18%)}.metric-grid article:last-child{border-right:0}.use-guide{display:flex;align-items:baseline;gap:18px;margin-top:18px;padding:16px 18px;border-radius:14px;background:rgb(255 255 255 / 42%);color:var(--reading)}.use-guide strong{white-space:nowrap;font-size:.86rem}.use-guide span{font-size:.82rem;line-height:1.62}.evidence-section,.task-section,.boundary{scroll-margin-top:112px}
body{background:radial-gradient(circle at 12% 5%,rgb(147 197 253 / 42%),transparent 34%),radial-gradient(circle at 84% 7%,rgb(167 139 250 / 28%),transparent 36%),radial-gradient(circle at 68% 88%,rgb(79 70 229 / 14%),transparent 38%),linear-gradient(145deg,#fbfdff 0%,#f1f7ff 49%,#e7f1ff 100%);background-attachment:fixed}.boundary{border:1px solid rgb(255 255 255 / 68%);background-color:rgb(255 255 255 / 28%);background-image:radial-gradient(circle at 18% 0%,rgb(255 255 255 / 58%),transparent 44%),linear-gradient(135deg,rgb(37 99 235 / 7%),rgb(124 58 237 / 6%));box-shadow:inset 0 1px 0 rgb(255 255 255 / 72%),inset 0 -1px 0 rgb(79 70 229 / 6%),0 24px 72px rgb(71 105 148 / 12%);-webkit-backdrop-filter:blur(24px) saturate(148%);backdrop-filter:blur(24px) saturate(148%)}
body{min-width:0}.brand-link{min-height:44px;align-items:center}.site-header nav a{display:inline-flex;min-height:44px;align-items:center}.text-link{display:inline-flex;min-height:44px;align-items:center}.hero-proof h2{margin:22px 0 0;color:var(--primary);font-size:clamp(1.35rem,2vw,1.85rem);font-weight:570;letter-spacing:-.025em;line-height:1.08}.checkpoint-plot{margin:22px 0 18px;padding:18px;border:1px solid rgb(71 105 148 / 16%);border-radius:20px;background:rgb(248 251 255 / 66%)}.plot-loading{color:var(--muted);font-size:.82rem}.checkpoint-grid{display:grid;grid-template-columns:82px repeat(3,minmax(0,1fr));gap:12px 8px;align-items:center}.series-label{color:var(--reading);font-size:.72rem;font-weight:650}.checkpoint-node{position:relative;display:grid;min-width:0;min-height:62px;place-items:center;border:1px solid rgb(71 105 148 / 14%);border-radius:14px;background:rgb(255 255 255 / 58%)}.checkpoint-node i{width:12px;height:12px;border-radius:50%}.checkpoint-node b{font-size:.78rem}.checkpoint-node.reference i{background:var(--blue);box-shadow:0 0 18px rgb(37 99 235 / 38%)}.checkpoint-node.candidate i{background:var(--violet)}.checkpoint-node.first-failure{border-color:rgb(124 58 237 / 42%);background:rgb(237 233 254 / 62%);box-shadow:0 0 0 3px rgb(124 58 237 / 8%)}.checkpoint-node small{position:absolute;right:4px;bottom:2px;left:4px;color:#6d28d9;font-size:.55rem;font-weight:680;line-height:1.1;text-align:center;text-transform:uppercase}.checkpoint-grid code{color:var(--muted);font-size:.59rem;line-height:1.25;overflow-wrap:anywhere;text-align:center}.hero-proof #proof-caption{margin:0;color:var(--reading);font-size:.88rem;line-height:1.62}
@media(max-width:1099px){.hero{min-height:0;grid-template-columns:minmax(0,1fr);gap:34px;padding:124px 0 62px}.hero-proof{width:100%}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-grid article:nth-child(2){border-right:0}.metric-grid article:nth-child(-n+2){border-bottom:1px solid rgb(71 105 148 / 18%)}.task-grid{grid-template-columns:minmax(0,1fr)}.task-card{min-height:0}.task-card h3{margin:34px 0 24px}.section-heading{align-items:flex-start;flex-direction:column}.boundary{grid-template-columns:minmax(0,1fr);align-items:start}}
@media(max-width:959px){.site-header nav{gap:2px}.site-header nav a{padding-inline:9px}.local-badge{max-width:190px;font-size:.64rem;line-height:1.2}.hero h1{font-size:clamp(3rem,8vw,4.5rem)}.checkpoint-grid{grid-template-columns:72px repeat(3,minmax(0,1fr));gap:10px 6px}.use-guide{align-items:flex-start;flex-direction:column;gap:5px}}
.liquid-button{transition-property:transform,background-color,box-shadow,border-color}.liquid-button:focus-visible{outline:3px solid rgb(37 99 235 / 45%)!important;outline-offset:4px!important}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.liquid-button,.liquid-button::before,.site-header nav a{transition:none}}
"""


STUDIO_JS = r"""const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);const pct=v=>`${Math.round(v*100)}%`;
function renderCheckpoint(task){const plot=$("#checkpoint-plot"),nodes=(key,kind)=>task.checkpoints.map(c=>`<span class="checkpoint-node ${kind} ${kind==="candidate"&&c.id===task.firstFailure?"first-failure":""}"><i></i><b>${pct(c[key])}</b>${kind==="candidate"&&c.id===task.firstFailure?"<small>first divergence</small>":""}</span>`).join(""),labels=task.checkpoints.map(c=>`<code>${c.id}</code>`).join("");plot.innerHTML=`<div class="checkpoint-grid"><strong class="series-label">Reference</strong>${nodes("referenceRate","reference")}<strong class="series-label">Popup-blind</strong>${nodes("candidateRate","candidate")}<span></span>${labels}</div>`;plot.setAttribute("aria-label",`${task.label}: reference and popup-blind checkpoint pass rates; first divergence ${task.firstFailure}`);$("#proof-caption").textContent=`${task.label} · popup overlay. Reference passes all ${task.checkpoints.length} checkpoints; popup-blind first fails at ${task.firstFailure} (${pct(task.agreement)} repetition agreement).`;}
function render(data){$("#metric-tasks").textContent=data.taskCount;$("#metric-variants").textContent=data.variantCount;$("#metric-attempts").textContent=data.attemptCount;$("#metric-regressions").textContent=data.regressionCount;$("#protocol").textContent=data.protocol;$("#evidence-source").textContent=data.source==="demo"?"Fresh local demo":"Committed evidence";$("#proof-status").textContent=`${data.regressionCount}/${data.taskCount} localized`;renderCheckpoint(data.tasks[0]);$("#task-grid").innerHTML=data.tasks.map((t,i)=>`<article class="task-card"><span class="task-index">0${i+1}</span><h3>${t.label}</h3><div class="rate-pair"><div><span>Reference</span><strong>${pct(t.baselineRate)}</strong></div><div><span>Popup-blind</span><strong>${pct(t.candidateRate)}</strong></div></div><div class="failure"><span>First failed checkpoint · ${pct(t.agreement)} agreement</span><code>${t.firstFailure}</code></div></article>`).join("");}
async function load(){const response=await fetch("/api/evidence");if(!response.ok)throw new Error("Evidence unavailable");render(await response.json());}
async function run(){const button=$("#run-demo"),status=$("#run-status"),runs=Number($("#demo-runs").value);button.disabled=true;status.textContent=`Running ${12*runs} local browser attempts…`;try{const response=await fetch("/api/demo",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({runs})});const data=await response.json();if(!response.ok)throw new Error(data.error||"Demo failed");render(data);status.textContent=`PASS · ${data.regressionCount}/${data.taskCount} controlled regressions localized · Chromium ${data.browser}`;$("#proof-status").textContent="Fresh pass";$("#evidence").scrollIntoView({behavior:"smooth"});}catch(error){status.textContent=`Unable to run: ${error.message}`;}finally{button.disabled=false;}}
function syncNavigation(){const links=[...$$('.site-header nav a[href^="#"]')],sections=links.map(link=>document.querySelector(link.hash));const update=()=>{let active=sections[0];for(const section of sections){if(section&&section.getBoundingClientRect().top<=innerHeight*.35)active=section;}links.forEach(link=>{const selected=active&&link.hash===`#${active.id}`;link.classList.toggle('active',selected);if(selected)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');});};addEventListener('scroll',update,{passive:true});addEventListener('resize',update);update();}
window.addEventListener("DOMContentLoaded",()=>{load().catch(error=>{$("#run-status").textContent=error.message;});$("#run-demo").addEventListener("click",run);syncNavigation();});
"""


class _StudioHandler(BaseHTTPRequestHandler):
    server: StudioHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _send(self, payload: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self'; font-src 'self'; "
            "style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(payload, "application/json; charset=utf-8", status)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        routes = {
            "/": (INDEX_HTML.encode(), "text/html; charset=utf-8"),
            "/studio.css": (STUDIO_CSS.encode(), "text/css; charset=utf-8"),
            "/studio.js": (STUDIO_JS.encode(), "text/javascript; charset=utf-8"),
        }
        if self.path in routes:
            self._send(*routes[self.path])
            return
        assets = {
            "/assets/wordmark.svg": ("assets/brand/alvenx-wordmark.svg", "image/svg+xml"),
            "/assets/monogram.svg": ("assets/brand/alvenx-monogram.svg", "image/svg+xml"),
            "/assets/font.woff2": ("assets/fonts/InstrumentSans-wdth-wght.woff2", "font/woff2"),
        }
        if self.path in assets:
            relative, content_type = assets[self.path]
            self._send(_asset_bytes(relative), content_type)
            return
        if self.path == "/api/evidence":
            try:
                self._json(self.server.committed_evidence)
            except (KeyError, TypeError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/api/demo":
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 1_024:
                raise ValueError("request body is too large")
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("request body must be a JSON object")
            runs = _validated_demo_runs(payload.get("runs", 1))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if not self.server.run_lock.acquire(blocking=False):
            self._json({"error": "a local demo is already running"}, HTTPStatus.CONFLICT)
            return
        try:
            self._json(run_live_demo(runs=runs))
        except Exception as exc:  # UI boundary: return a concise local error.
            self._json({"error": " ".join(str(exc).split())[:500]}, HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            self.server.run_lock.release()


class StudioHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: StudioAddress, evidence_path: Path | None = None) -> None:
        address.validate()
        self.committed_evidence = load_committed_evidence(evidence_path)
        self.run_lock = threading.Lock()
        super().__init__((address.host, address.port), _StudioHandler)


def serve_studio(
    *, host: str = "127.0.0.1", port: int = DEFAULT_PORT, open_browser: bool = True
) -> int:
    server = StudioHTTPServer(StudioAddress(host, port))
    actual_port = int(server.server_address[1])
    display_host = "127.0.0.1" if host == "::1" else host
    url = f"http://{display_host}:{actual_port}/"
    print(f"Browser Agent Regression Studio: {url}")
    print("Local-only interface. Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
