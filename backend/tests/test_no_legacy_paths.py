from pathlib import Path


REPO_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_runtime_and_policy_dirs_removed() -> None:
    assert not (REPO_BACKEND_ROOT / "runtime").exists()
    assert not (REPO_BACKEND_ROOT / "policy").exists()


def test_no_legacy_runtime_policy_imports() -> None:
    roots = [REPO_BACKEND_ROOT / "src", REPO_BACKEND_ROOT / "routers"]
    offenders: list[str] = []

    for root in roots:
        if not root.exists():
            continue
        for file_path in root.rglob("*.py"):
            text = file_path.read_text(encoding="utf-8")
            for marker in (
                "from runtime",
                "import runtime",
                "from policy",
                "import policy",
            ):
                if marker in text:
                    offenders.append(str(file_path.relative_to(REPO_BACKEND_ROOT)))
                    break

    assert not offenders, "Legacy imports found: " + ", ".join(sorted(offenders))
