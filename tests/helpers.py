"""Helpers for hermetic pipeline tests."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DXF = REPO_ROOT / "simple_room.dxf"
CANONICAL_STAGES = (
    "parse_dxf.py",
    "semantic_classification.py",
    "material_assignment.py",
    "cost_estimation.py",
)


def run_script(script: str, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a repository CLI script inside a test working directory."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT) + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / script), *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )


def build_canonical_workspace(workspace: Path) -> Path:
    """Recreate the canonical simple_room.dxf pipeline outputs under ``workspace``."""
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copy(CANONICAL_DXF, workspace / CANONICAL_DXF.name)
    for script in CANONICAL_STAGES:
        result = run_script(script, workspace)
        assert result.returncode == 0, f"{script} failed in fresh workspace: {result.stderr}"
    return workspace
