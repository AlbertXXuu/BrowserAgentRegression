import hashlib
import json
import struct
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from browser_agent_regression.studio import (
    INDEX_HTML,
    STUDIO_CSS,
    STUDIO_JS,
    StudioAddress,
    StudioHTTPServer,
    _validated_demo_runs,
    load_committed_evidence,
)


def test_committed_evidence_is_reduced_to_three_localized_tasks() -> None:
    view = load_committed_evidence()

    assert view["attemptCount"] == 36
    assert view["taskCount"] == 3
    assert view["regressionCount"] == 3
    assert all(task["cleanParity"] for task in view["tasks"])
    assert all(task["baselineRate"] == 1.0 for task in view["tasks"])
    assert all(task["candidateRate"] == 0.0 for task in view["tasks"])
    assert all(task["firstFailure"] != "not detected" for task in view["tasks"])
    assert all(len(task["checkpoints"]) == 3 for task in view["tasks"])
    assert all(
        checkpoint["referenceRate"] == 1.0
        and checkpoint["candidateRate"] == 0.0
        for task in view["tasks"]
        for checkpoint in task["checkpoints"]
    )


def test_packaged_fallback_matches_repository_evidence() -> None:
    assert load_committed_evidence(Path("missing/report.json")) == load_committed_evidence()


def test_studio_uses_locked_interface_tokens_and_accessible_controls() -> None:
    assert "rgb(255 255 255 / 28%)" in STUDIO_CSS
    assert "blur(24px)" in STUDIO_CSS
    assert "cubic-bezier(.22,1,.36,1)" in STUDIO_CSS
    assert 'id="run-demo"' in INDEX_HTML
    assert 'aria-live="polite"' in INDEX_HTML
    assert "ambient" not in STUDIO_CSS.casefold()
    assert "border:1px solid rgb(71 105 148 / 18%)" in STUDIO_CSS
    assert "line-height:1.02" in STUDIO_CSS
    assert "radial-gradient(circle at 12% 5%,rgb(147 197 253 / 42%),transparent 34%)" in STUDIO_CSS
    assert ".boundary{border:1px solid rgb(255 255 255 / 68%)" in STUDIO_CSS
    assert "backdrop-filter:blur(24px) saturate(148%)" in STUDIO_CSS
    assert 'id="demo-runs"' in INDEX_HTML
    assert "Run → compare → localize" in INDEX_HTML
    assert "Built-in drivers" in INDEX_HTML
    assert "Controlled changes" in INDEX_HTML
    assert "Studio v1.1.0 · Evidence v1.0.0" in INDEX_HTML
    assert "Evidence v1.0.0" in INDEX_HTML
    assert "position:fixed" in STUDIO_CSS
    assert ".site-header{position:fixed;z-index:100" in STUDIO_CSS
    assert "0 24px 72px rgb(71 105 148 / 12%)" in STUDIO_CSS
    assert "syncNavigation" in STUDIO_JS
    assert "aria-current','location'" in STUDIO_JS
    assert 'id="checkpoint-plot"' in INDEX_HTML
    assert "renderCheckpoint" in STUDIO_JS
    assert "first divergence" in STUDIO_JS
    assert "proof-orbit" not in INDEX_HTML
    assert "checkpoint-orbit" not in STUDIO_CSS
    assert "body{min-width:0}" in STUDIO_CSS
    assert "@media(max-width:1099px)" in STUDIO_CSS
    assert ".site-header nav a{display:inline-flex;min-height:44px" in STUDIO_CSS
    assert ".text-link{display:inline-flex;min-height:44px" in STUDIO_CSS
    assert ".liquid-button:focus-visible{outline:3px solid" in STUDIO_CSS
    assert ".liquid-button{transition-property:transform" in STUDIO_CSS


def test_demo_repetition_control_is_bounded() -> None:
    assert _validated_demo_runs(1) == 1
    assert _validated_demo_runs(3) == 3
    for value in (0, 4, True, "2"):
        with pytest.raises(ValueError, match="runs"):
            _validated_demo_runs(value)


def test_studio_viewport_evidence_matches_the_closure_contract() -> None:
    evidence_root = Path(__file__).resolve().parents[1] / "docs/assets/studio"
    audit = json.loads(
        (evidence_root / "viewport-audit.json").read_text(encoding="utf-8")
    )

    assert [item["width_px"] for item in audit["viewports"]] == [
        900,
        1024,
        1280,
        1440,
        1600,
    ]
    assert all(not item["horizontal_overflow"] for item in audit["viewports"])
    assert all(
        item["minimum_critical_target_height_px"] >= 44
        for item in audit["viewports"]
    )
    assert audit["checkpoint_visual"]["reference_rates"] == [1.0, 1.0, 1.0]
    assert audit["checkpoint_visual"]["candidate_rates"] == [0.0, 0.0, 0.0]
    assert audit["checkpoint_visual"]["first_divergence"] == "checkout.email.accepted"
    assert audit["live_demo"]["result"] == "PASS"

    for item in audit["viewports"]:
        payload = (evidence_root / item["screenshot"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == item["screenshot_sha256"]
        assert payload[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">I", payload[16:20])[0] == item["width_px"]
        assert struct.unpack(">I", payload[20:24])[0] == item["screenshot_height_px"]


def test_studio_rejects_non_loopback_hosts() -> None:
    with pytest.raises(ValueError, match="local-only"):
        StudioAddress("0.0.0.0", 7870).validate()


def test_studio_serves_page_assets_and_evidence() -> None:
    server = StudioHTTPServer(StudioAddress(port=0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(f"{base}/", timeout=3) as response:  # noqa: S310 - loopback test
            assert response.status == 200
            assert b"Find the first point" in response.read()
        with urlopen(f"{base}/api/evidence", timeout=3) as response:  # noqa: S310
            payload = json.load(response)
            assert payload["taskCount"] == 3
        with urlopen(f"{base}/assets/wordmark.svg", timeout=3) as response:  # noqa: S310
            assert response.headers["Content-Type"] == "image/svg+xml"
            assert response.read().lstrip().startswith(b"<svg")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
