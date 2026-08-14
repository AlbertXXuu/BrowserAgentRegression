import json
from pathlib import Path

from browser_agent_regression.runner import CHECKPOINTS, VARIANTS


def test_checkout_manifest_matches_runner_contract() -> None:
    manifest_path = (
        Path(__file__).parents[1]
        / "src"
        / "browser_agent_regression"
        / "fixtures"
        / "checkout.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["task_id"] == "checkout.basic.v1"
    assert tuple(manifest["variants"]) == VARIANTS
    assert tuple(item["id"] for item in manifest["checkpoints"]) == CHECKPOINTS
    assert manifest["reset"] == "reload"
