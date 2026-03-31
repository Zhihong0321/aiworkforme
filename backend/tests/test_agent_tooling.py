from pathlib import Path

from src.app.runtime.agent_tooling import _runtime_paths


def test_runtime_paths_point_to_backend_root():
    scripts_dir, fallback_cwd = _runtime_paths()

    backend_root = Path(__file__).resolve().parents[1]
    assert Path(fallback_cwd).resolve() == backend_root
    assert Path(scripts_dir).resolve() == (backend_root / "mcp-runtime-scripts").resolve()
