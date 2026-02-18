import uuid

import pytest

from live_test_utils import (
    api_request,
    create_agent,
    create_membership,
    create_tenant,
    create_user,
    create_workspace,
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


def test_denied_platform_access_is_logged_for_platform_review(admin_token: str):
    actor = _create_tenant_actor(admin_token, "M7-Deny")
    denied = api_request("GET", "/api/v1/platform/tenants", token=actor["token"])
    assert denied.status_code == 403, denied.text

    rows = require_ok(
        api_request(
            "GET",
            f"/api/v1/platform/security-events?tenant_id={actor['tenant_id']}&limit=200",
            token=admin_token,
        ),
        200,
    )
    matches = [
        row
        for row in rows
        if row.get("endpoint") == "/api/v1/platform/tenants"
        and row.get("reason") == "platform_admin_required"
        and row.get("status_code") == 403
        and row.get("actor_user_id") == actor["user_id"]
        and row.get("tenant_id") == actor["tenant_id"]
    ]
    assert matches, rows


def test_analytics_summary_and_security_events_are_tenant_scoped(admin_token: str):
    actor_a = _create_tenant_actor(admin_token, "M7-A")
    actor_b = _create_tenant_actor(admin_token, "M7-B")

    create_workspace(actor_a["token"], "M7 Workspace A")
    create_workspace(actor_b["token"], "M7 Workspace B")
    create_agent(actor_a["token"], "M7 Agent A")
    create_agent(actor_b["token"], "M7 Agent B")

    assert api_request("GET", "/api/v1/platform/users", token=actor_a["token"]).status_code == 403
    assert api_request("GET", "/api/v1/platform/users", token=actor_b["token"]).status_code == 403

    summary_a = require_ok(
        api_request("GET", "/api/v1/analytics/summary?window_hours=168", token=actor_a["token"]),
        200,
    )
    summary_b = require_ok(
        api_request("GET", "/api/v1/analytics/summary?window_hours=168", token=actor_b["token"]),
        200,
    )

    assert int(summary_a["workspace_count"]) == 1
    assert int(summary_b["workspace_count"]) == 1
    assert int(summary_a["agent_count"]) == 1
    assert int(summary_b["agent_count"]) == 1
    assert int(summary_a["denied_events_window"]) >= 1
    assert int(summary_b["denied_events_window"]) >= 1

    events_a = require_ok(
        api_request(
            "GET",
            "/api/v1/analytics/security-events?window_hours=168&limit=100",
            token=actor_a["token"],
        ),
        200,
    )
    events_b = require_ok(
        api_request(
            "GET",
            "/api/v1/analytics/security-events?window_hours=168&limit=100",
            token=actor_b["token"],
        ),
        200,
    )

    assert events_a, events_a
    assert events_b, events_b
    assert all(row.get("tenant_id") == actor_a["tenant_id"] for row in events_a)
    assert all(row.get("tenant_id") == actor_b["tenant_id"] for row in events_b)
    assert any(row.get("reason") == "platform_admin_required" for row in events_a)
    assert any(row.get("reason") == "platform_admin_required" for row in events_b)


def test_platform_security_event_feed_requires_platform_role(admin_token: str):
    actor = _create_tenant_actor(admin_token, "M7-NoPlatform")
    denied = api_request("GET", "/api/v1/platform/security-events", token=actor["token"])
    assert denied.status_code == 403, denied.text


def test_platform_audit_log_export_csv(admin_token: str):
    suffix = uuid.uuid4().hex[:8]
    tenant_id = create_tenant(admin_token, f"M7-Export-{suffix}")

    export_resp = api_request(
        "GET",
        f"/api/v1/platform/audit-logs/export?tenant_id={tenant_id}&limit=200",
        token=admin_token,
    )
    assert export_resp.status_code == 200, export_resp.text
    assert export_resp.headers.get("content-type", "").startswith("text/csv")
    body = export_resp.text
    assert body.startswith("id,created_at,actor_user_id,tenant_id,action,target_type,target_id,details_json")
    assert "tenant.create" in body
