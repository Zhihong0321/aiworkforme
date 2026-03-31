from pathlib import Path
from types import SimpleNamespace

from src.app.runtime.agent_tooling import _resolved_server_launch, _runtime_paths


def test_runtime_paths_point_to_backend_root():
    scripts_dir, fallback_cwd = _runtime_paths()

    backend_root = Path(__file__).resolve().parents[1]
    assert Path(fallback_cwd).resolve() == backend_root
    assert Path(scripts_dir).resolve() == (backend_root / "mcp-runtime-scripts").resolve()


def test_python_server_launch_injects_backend_root_into_pythonpath():
    backend_root = Path(__file__).resolve().parents[1]
    server = SimpleNamespace(
        script="calendar_mcp.py",
        command="python",
        args="[]",
        cwd=str(backend_root),
        env_vars="{}",
    )

    _args, cwd, env_vars = _resolved_server_launch(server)

    assert Path(cwd).resolve() == backend_root
    pythonpath = env_vars.get("PYTHONPATH") or ""
    assert str(backend_root) in pythonpath.split(";") or str(backend_root) in pythonpath.split(":")
