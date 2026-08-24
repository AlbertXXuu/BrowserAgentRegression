import json
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from browser_agent_regression.studio import (
    INDEX_HTML,
    STUDIO_CSS,
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
    assert 'id="demo-runs"' in INDEX_HTML
    assert "Run → compare → localize" in INDEX_HTML


def test_demo_repetition_control_is_bounded() -> None:
    assert _validated_demo_runs(1) == 1
    assert _validated_demo_runs(3) == 3
    for value in (0, 4, True, "2"):
        with pytest.raises(ValueError, match="runs"):
            _validated_demo_runs(value)


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
