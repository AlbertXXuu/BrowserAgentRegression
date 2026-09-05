import hashlib
import json
import struct
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright

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
    assert "Studio v1.1.2 · Evidence v1.0.0" in INDEX_HTML
    assert "Evidence v1.0.0" in INDEX_HTML
    assert "position:fixed" in STUDIO_CSS
    assert ".site-header{position:fixed;z-index:100" in STUDIO_CSS
    assert "0 24px 72px rgb(71 105 148 / 12%)" in STUDIO_CSS
    assert "syncNavigation" in STUDIO_JS
    assert "aria-current','location'" in STUDIO_JS
    assert 'id="checkpoint-plot"' in INDEX_HTML
    assert "renderCheckpoint" in STUDIO_JS
    assert "first divergence" in STUDIO_JS
    assert "grid-template-columns:minmax(0,1fr);grid-template-rows:12px" in STUDIO_CSS
    assert ".checkpoint-node small{width:100%;min-height:20px" in STUDIO_CSS
    assert "proof-orbit" not in INDEX_HTML
    assert "checkpoint-orbit" not in STUDIO_CSS
    assert "body{min-width:0}" in STUDIO_CSS
    assert "@media(max-width:1099px)" in STUDIO_CSS
    assert ".site-header nav a{display:inline-flex;min-height:44px" in STUDIO_CSS
    assert ".text-link{display:inline-flex;min-height:44px" in STUDIO_CSS
    assert INDEX_HTML.count('class="link-label"') == 2
    assert INDEX_HTML.count('class="link-arrow" aria-hidden="true"') == 2
    assert ".liquid-button,.text-link{text-decoration:none}" in STUDIO_CSS
    assert ".text-link .link-label{text-decoration:underline" in STUDIO_CSS
    assert ".link-arrow{display:inline-block;flex:0 0 auto;text-decoration:none}" in STUDIO_CSS
    assert ".liquid-button:focus-visible{outline:3px solid" in STUDIO_CSS
    assert ".liquid-button{transition-property:transform" in STUDIO_CSS
    assert "background:rgb(147 197 253 / 28%);color:var(--blue)" in STUDIO_CSS


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


@pytest.mark.browser
def test_current_checkpoint_labels_stay_inside_their_nodes() -> None:
    server = StudioHTTPServer(StudioAddress(port=0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            try:
                for width in (1920, 1600, 1440, 1280, 1100, 1024, 900, 390):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.goto(base)
                    page.wait_for_function(
                        "document.querySelectorAll('.checkpoint-node').length === 6"
                    )
                    page.evaluate("document.fonts.ready")
                    assert page.locator(".checkpoint-label").all_text_contents() == [
                        "Email accepted", "Shipping selected", "Confirmed"
                    ]
                    assert page.locator(".checkpoint-label").evaluate_all(
                        "labels => labels.map(label => label.title)"
                    ) == [
                        "checkout.email.accepted",
                        "checkout.shipping.selected",
                        "checkout.confirmed",
                    ]
                    words_are_whole = page.locator(
                        ".checkpoint-node small, .checkpoint-label"
                    ).evaluate_all(
                        """labels => labels.every(label => {
                            const text = label.firstChild;
                            if (!text) return true;
                            return [...text.textContent.matchAll(/\\S+/g)].every(word => {
                                const range = document.createRange();
                                range.setStart(text, word.index);
                                range.setEnd(text, word.index + word[0].length);
                                const tops = [...range.getClientRects()].map(rect => rect.top);
                                return Math.max(...tops) - Math.min(...tops) <= 0.5;
                            });
                        })"""
                    )
                    assert words_are_whole, f"Annotation words split at {width}px"
                    layout = page.locator(".checkpoint-node").evaluate_all(
                        """nodes => {
                            const tolerance = 0.5;
                            const contained = nodes.every(node => {
                                const parent = node.getBoundingClientRect();
                                return [...node.children].every(child => {
                                    const rect = child.getBoundingClientRect();
                                    return rect.left >= parent.left - tolerance
                                        && rect.right <= parent.right + tolerance
                                        && rect.top >= parent.top - tolerance
                                        && rect.bottom <= parent.bottom + tolerance;
                                });
                            });
                            const candidates = nodes
                                .filter(node => node.classList.contains('candidate'))
                                .map(node => node.getBoundingClientRect());
                            const equalRowHeights = ['reference', 'candidate'].every(kind => {
                                const row = nodes.filter(node => node.classList.contains(kind));
                                const heights = row.map(node => node.getBoundingClientRect().height);
                                return Math.max(...heights) - Math.min(...heights) <= tolerance;
                            });
                            const alignedRowContent = ['reference', 'candidate'].every(kind => {
                                const row = nodes.filter(node => node.classList.contains(kind));
                                return ['i', 'b', 'small'].every(selector => {
                                    const tops = row.map(node => {
                                        const child = node.querySelector(selector);
                                        return child.getBoundingClientRect().top
                                            - node.getBoundingClientRect().top;
                                    });
                                    return Math.max(...tops) - Math.min(...tops) <= tolerance;
                                });
                            });
                            const internalOverlap = nodes.some(node => {
                                const percentage = node.querySelector('b').getBoundingClientRect();
                                const annotation = node.querySelector('small').getBoundingClientRect();
                                return Math.min(percentage.right, annotation.right)
                                        - Math.max(percentage.left, annotation.left) > tolerance
                                    && Math.min(percentage.bottom, annotation.bottom)
                                        - Math.max(percentage.top, annotation.top) > tolerance;
                            });
                            const adjacentOverlap = candidates.slice(0, -1).some((rect, index) => {
                                const next = candidates[index + 1];
                                return Math.min(rect.right, next.right)
                                        - Math.max(rect.left, next.left) > tolerance
                                    && Math.min(rect.bottom, next.bottom)
                                        - Math.max(rect.top, next.top) > tolerance;
                            });
                            return {
                                contained,
                                equalRowHeights,
                                alignedRowContent,
                                internalOverlap,
                                adjacentOverlap,
                            };
                        }"""
                    )
                    assert layout == {
                        "contained": True,
                        "equalRowHeights": True,
                        "alignedRowContent": True,
                        "internalOverlap": False,
                        "adjacentOverlap": False,
                    }
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.browser
def test_home_preserves_url_and_evidence_for_pointer_keyboard_and_reduced_motion() -> None:
    server = StudioHTTPServer(StudioAddress(port=0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.goto(f"{base}/#method")
                page.wait_for_function("() => document.querySelectorAll('.checkpoint-node').length === 6")
                page.evaluate("history.replaceState(null, '', '?source=local#method')")
                page.locator("#demo-runs").select_option("3")
                home = page.get_by_role("button", name="AlvenX — Back to top")
                page.evaluate("""() => {
                    window.__homeDocument = 'retained';
                    window.__homeCalls = [];
                    const scroll = window.scrollTo.bind(window);
                    window.scrollTo = options => { window.__homeCalls.push(options); scroll(options); };
                }""")
                state = """() => ({url: location.href, history: history.length,
                    runs: document.querySelector('#demo-runs').value,
                    tasks: document.querySelector('#task-grid').textContent,
                    evidence: document.querySelector('#evidence-source').textContent,
                    result: document.querySelector('#run-status').textContent,
                    document: window.__homeDocument})"""
                before = page.evaluate(state)
                for reduced in ("no-preference", "reduce"):
                    page.emulate_media(reduced_motion=reduced)
                    for activation in ("click", "Enter", "Space"):
                        page.evaluate("window.scrollTo({top:0,behavior:'instant'}); window.__homeCalls=[]")
                        if activation == "click":
                            home.click()
                        else:
                            home.evaluate("element => element.focus({preventScroll:true})")
                            home.press(activation)
                        assert page.evaluate("window.scrollY") == 0
                        assert page.evaluate("window.__homeCalls") == []
                        page.evaluate("window.scrollTo({top:document.body.scrollHeight,behavior:'instant'}); window.__homeCalls=[]")
                        assert page.evaluate("window.scrollY") > 0
                        if activation == "click":
                            home.click()
                        else:
                            home.evaluate("element => element.focus({preventScroll:true})")
                            home.press(activation)
                        page.wait_for_function("() => window.scrollY === 0")
                        assert page.evaluate("window.__homeCalls") == [{
                            "top": 0, "left": 0,
                            "behavior": "instant" if reduced == "reduce" else "smooth",
                        }]
                        assert page.evaluate(state) == before
                assert home.evaluate("element => getComputedStyle(element).width") == "160px"
                assert home.evaluate("element => getComputedStyle(element).outlineStyle") == "solid"
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


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
