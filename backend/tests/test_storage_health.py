from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.adapters.api import status_routes
from src.app.runtime import sales_materials


def test_sales_material_storage_health_reports_persistent_mount_usage(monkeypatch, tmp_path: Path):
    mount_root = tmp_path / "storage"
    storage_dir = mount_root / "sales-materials"
    monkeypatch.setenv("STORAGE_MOUNT_PATH", str(mount_root))
    monkeypatch.setattr(sales_materials, "SALES_MATERIALS_DIR", storage_dir)

    result = sales_materials.get_sales_material_storage_health()

    assert result["status"] == "ok"
    assert result["configured_path_writable"] is True
    assert result["persistent_mount_exists"] is True
    assert result["using_persistent_mount"] is True
    assert result["warnings"] == []


def test_sales_material_storage_health_warns_when_not_using_persistent_mount(monkeypatch, tmp_path: Path):
    mount_root = tmp_path / "storage"
    mount_root.mkdir(parents=True, exist_ok=True)
    storage_dir = tmp_path / "local-sales-materials"
    monkeypatch.setenv("STORAGE_MOUNT_PATH", str(mount_root))
    monkeypatch.setattr(sales_materials, "SALES_MATERIALS_DIR", storage_dir)

    result = sales_materials.get_sales_material_storage_health()

    assert result["status"] == "warn"
    assert result["configured_path_writable"] is True
    assert result["persistent_mount_exists"] is True
    assert result["using_persistent_mount"] is False
    assert "not under mounted persistent path" in " ".join(result["warnings"])


def test_sales_material_paths_are_side_effect_free_until_write(monkeypatch, tmp_path: Path):
    storage_dir = tmp_path / "sales-materials"
    monkeypatch.setattr(sales_materials, "SALES_MATERIALS_DIR", storage_dir)
    material = SimpleNamespace(
        tenant_id=1,
        agent_id=2,
        stored_name="abc-brochure.pdf",
        source_type="file",
    )

    file_path = sales_materials.sales_material_path(material)
    assert file_path == storage_dir / "tenant-1" / "agent-2" / "abc-brochure.pdf"
    assert not file_path.parent.exists()

    sales_materials.write_sales_material_file(material, b"%PDF-1.4")
    assert file_path.is_file()


def test_health_check_exposes_startup_storage_snapshot(monkeypatch):
    startup_health = {
        "ready": True,
        "checked_at": "2026-03-19T10:00:00",
        "storage": {
            "status": "warn",
            "configured_path": "/app/storage/sales-materials",
            "using_persistent_mount": False,
            "warnings": ["Sales materials directory is not under mounted persistent path /storage"],
        },
    }

    original_import_module = status_routes.importlib.import_module

    def _fake_import_module(name: str):
        if name == "src.infra.lifecycle":
            return SimpleNamespace(STARTUP_HEALTH=startup_health)
        return original_import_module(name)

    monkeypatch.setattr(status_routes.importlib, "import_module", _fake_import_module)

    response = status_routes.health_check()

    assert response["status"] == "ok"
    assert response["startup"]["storage"]["status"] == "warn"
    assert response["startup"]["storage"]["using_persistent_mount"] is False


def test_readiness_check_keeps_storage_non_blocking(monkeypatch):
    startup_health = {
        "ready": True,
        "checked_at": "2026-03-19T10:00:00",
        "storage": {"status": "error", "configured_path_writable": False},
    }

    class _FakeSession:
        def execute(self, _query):
            return None

    def _fake_import_module(name: str):
        if name == "src.infra.database":
            return SimpleNamespace(engine=object())
        if name == "src.infra.lifecycle":
            return SimpleNamespace(STARTUP_HEALTH=startup_health)
        if name == "src.infra.schema_checks":
            return SimpleNamespace(evaluate_message_schema_compat=lambda _engine: {"ok": True})
        raise AssertionError(f"Unexpected import: {name}")

    monkeypatch.setattr(status_routes.importlib, "import_module", _fake_import_module)

    response = status_routes.readiness_check(db_session=_FakeSession())

    assert response["status"] == "ready"
    assert response["storage"]["status"] == "error"
