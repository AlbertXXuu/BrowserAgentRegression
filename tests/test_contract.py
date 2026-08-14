import json
from pathlib import Path

import pytest

from browser_agent_regression.runner import (
    TASK_CHECKPOINTS,
    TASK_FIXTURES,
    TASKS,
    VARIANTS,
    TaskId,
)


@pytest.mark.parametrize("task_id", TASKS)
def test_task_manifest_matches_runner_contract(task_id: TaskId) -> None:
    manifest_name = Path(TASK_FIXTURES[task_id]).with_suffix(".json")
    manifest_path = (
        Path(__file__).parents[1]
        / "src"
        / "browser_agent_regression"
        / "fixtures"
        / manifest_name
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["task_id"] == task_id
    assert manifest["fixture"] == TASK_FIXTURES[task_id]
    assert tuple(manifest["variants"]) == VARIANTS
    assert tuple(item["id"] for item in manifest["checkpoints"]) == TASK_CHECKPOINTS[task_id]
    assert manifest["reset"] == "reload"
