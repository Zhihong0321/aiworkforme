import concurrent.futures
import uuid

import pytest

from live_test_utils import (
    api_request,
    create_membership,
    create_tenant,
    create_user,
    login,
    require_ok,
)


@pytest.fixture(scope="session")
def admin_token() -> str:
    return str(login("admin@aiworkfor.me", "admin12345")["access_token"])


def _create_tenant_actor(admin_token: str, label: str) -> dict:
    suffix = uuid.uuid4().hex[:8]
    tenant_id = create_tenant(admin_token, f"{label}-Tenant-{suffix}")
    email = f"{label.lower()}-{suffix}@aiworkfor.me"
    user_id = create_user(admin_token, email, "tenant12345", is_platform_admin=False)
    create_membership(admin_token, tenant_id, user_id, role="tenant_user")
    token = str(login(email, "tenant12345", tenant_id=tenant_id)["access_token"])
    return {"tenant_id": tenant_id, "user_id": user_id, "token": token}


def test_concurrent_workspace_creation_remains_tenant_isolated(admin_token: str):
    actor_a = _create_tenant_actor(admin_token, "T7-Concurrent-A")
    actor_b = _create_tenant_actor(admin_token, "T7-Concurrent-B")

    prefix_a = f"T7A-{uuid.uuid4().hex[:6]}"
    prefix_b = f"T7B-{uuid.uuid4().hex[:6]}"
    per_tenant_creates = 8

    jobs: list[tuple[str, str]] = []
    for idx in range(per_tenant_creates):
        jobs.append((actor_a["token"], f"{prefix_a}-{idx}"))
        jobs.append((actor_b["token"], f"{prefix_b}-{idx}"))

    def _create_workspace(token: str, name: str) -> int:
        resp = api_request("POST", "/api/v1/workspaces/", token=token, json={"name": name})
        assert resp.status_code == 200, resp.text
        return int(require_ok(resp, 200)["id"])

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        created_ids = list(pool.map(lambda item: _create_workspace(item[0], item[1]), jobs))

    assert len(created_ids) == per_tenant_creates * 2
    assert len(set(created_ids)) == len(created_ids)

    list_a = require_ok(api_request("GET", "/api/v1/workspaces/", token=actor_a["token"]), 200)
    list_b = require_ok(api_request("GET", "/api/v1/workspaces/", token=actor_b["token"]), 200)
    names_a = {row["name"] for row in list_a}
    names_b = {row["name"] for row in list_b}

    expected_a = {f"{prefix_a}-{idx}" for idx in range(per_tenant_creates)}
    expected_b = {f"{prefix_b}-{idx}" for idx in range(per_tenant_creates)}

    assert expected_a.issubset(names_a)
    assert expected_b.issubset(names_b)
    assert not (expected_b & names_a)
    assert not (expected_a & names_b)


def test_membership_create_retry_has_no_duplicate_side_effect(admin_token: str):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = create_tenant(admin_token, f"T7-Idempotency-{suffix}")
    user_id = create_user(admin_token, f"t7-idempotency-{suffix}@aiworkfor.me", "tenant12345")

    first = api_request(
        "POST",
        f"/api/v1/platform/tenants/{tenant_id}/memberships",
        token=admin_token,
        json={"user_id": user_id, "role": "tenant_user"},
    )
    require_ok(first, 200)

    second = api_request(
        "POST",
        f"/api/v1/platform/tenants/{tenant_id}/memberships",
        token=admin_token,
        json={"user_id": user_id, "role": "tenant_user"},
    )
    assert second.status_code == 409, second.text

    memberships = require_ok(
        api_request("GET", f"/api/v1/platform/tenants/{tenant_id}/memberships", token=admin_token),
        200,
    )
    owned = [row for row in memberships if int(row["user_id"]) == user_id]
    assert len(owned) == 1


def test_cross_tenant_mcp_delete_retry_cannot_touch_foreign_resource(admin_token: str):
    actor_a = _create_tenant_actor(admin_token, "T7-MCP-A")
    actor_b = _create_tenant_actor(admin_token, "T7-MCP-B")

    create_resp = api_request(
        "POST",
        "/api/v1/mcp/servers",
        token=actor_b["token"],
        json={
            "name": f"T7-MCP-{uuid.uuid4().hex[:6]}",
            "script": "knowledge_retrieval.py",
            "command": "python",
            "args": "[]",
            "cwd": "/app",
            "env_vars": "{}",
        },
    )
    mcp_id = int(require_ok(create_resp, 200)["id"])

    for _ in range(3):
        denied = api_request("DELETE", f"/api/v1/mcp/servers/{mcp_id}", token=actor_a["token"])
        assert denied.status_code == 404, denied.text

    list_b = require_ok(api_request("GET", "/api/v1/mcp/servers", token=actor_b["token"]), 200)
    assert any(int(row["id"]) == mcp_id for row in list_b)

    deleted = api_request("DELETE", f"/api/v1/mcp/servers/{mcp_id}", token=actor_b["token"])
    require_ok(deleted, 200)
