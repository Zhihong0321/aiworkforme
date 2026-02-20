"""
Manual production smoke test (not part of default pytest run).

Usage:
  PROD_BASE_URL="https://your-prod.example.com" \
  PROD_USER_EMAIL="tenant-user@example.com" \
  PROD_USER_PASSWORD="your-password" \
  python3 backend/tests/smoke_prod_manual.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class CheckResult:
    name: str
    status_code: int
    ok: bool
    detail: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _request(
    method: str,
    base_url: str,
    path: str,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, str] | None = None,
) -> tuple[int, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    headers: dict[str, str] = {"Accept": "application/json"}
    payload: bytes | None = None

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if json_body is not None:
        payload = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form_body is not None:
        payload = urlencode(form_body).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = Request(url=url, data=payload, method=method.upper(), headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return resp.status, {}
            try:
                return resp.status, json.loads(raw.decode("utf-8"))
            except Exception:
                return resp.status, raw.decode("utf-8", errors="replace")
    except HTTPError as err:
        raw = err.read()
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            body = raw.decode("utf-8", errors="replace")
        return err.code, body
    except URLError as err:
        raise RuntimeError(f"Network error calling {url}: {err}") from err


def _check(results: list[CheckResult], name: str, actual: int, expected: int) -> None:
    ok = actual == expected
    results.append(CheckResult(name=name, status_code=actual, ok=ok))
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name} -> {actual} (expected {expected})")


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def main() -> int:
    base_url = _require_env("PROD_BASE_URL")
    email = _require_env("PROD_USER_EMAIL")
    password = _require_env("PROD_USER_PASSWORD")

    start_ts = utc_now_iso()
    run_id = uuid.uuid4().hex[:8]
    print(f"Production smoke run started at {start_ts} (UTC), run_id={run_id}")
    print(f"Target: {base_url}")

    results: list[CheckResult] = []
    lead_id: int | None = None
    mcp_id: int | None = None
    token: str | None = None

    # 1) Login
    code, body = _request(
        "POST",
        base_url,
        "/api/v1/auth/login",
        form_body={"username": email, "password": password},
    )
    _check(results, "POST /api/v1/auth/login", code, 200)
    if code == 200 and isinstance(body, dict):
        token = str(body.get("access_token") or "")
    if not token:
        print("Cannot continue without access token.")
        return 1

    # 2) Read checks
    for path, expected in [
        ("/api/v1/", 200),
        ("/api/v1/health", 200),
        ("/api/v1/ready", 200),
        ("/api/v1/leads/", 200),
        ("/api/v1/agents/", 200),
        ("/api/v1/mcp/servers", 200),
        ("/api/v1/analytics/summary?window_hours=24", 200),
        ("/api/v1/messaging/mvp/operational-check", 200),
        ("/api/v1/messaging/mvp/inbound-health", 200),
        ("/api/v1/platform/tenants", 403),  # expected for tenant users
    ]:
        code, _ = _request("GET", base_url, path, token=token)
        _check(results, f"GET {path}", code, expected)

    # 3) Write checks
    code, body = _request(
        "POST",
        base_url,
        "/api/v1/leads/",
        token=token,
        json_body={"external_id": f"+1555{run_id[:4]}{run_id[4:]}"},
    )
    _check(results, "POST /api/v1/leads/", code, 200)
    if code == 200 and isinstance(body, dict):
        lead_id = int(body.get("id") or 0) or None

    if lead_id is not None:
        code, _ = _request(
            "POST",
            base_url,
            f"/api/v1/leads/{lead_id}/mode",
            token=token,
            json_body={"mode": "working"},
        )
        _check(results, f"POST /api/v1/leads/{lead_id}/mode", code, 200)

    code, _ = _request(
        "POST",
        base_url,
        "/api/v1/agents/",
        token=token,
        json_body={"name": f"ProdTest-Agent-{run_id}", "system_prompt": "You are a smoke test agent."},
    )
    _check(results, "POST /api/v1/agents/", code, 200)

    code, body = _request(
        "POST",
        base_url,
        "/api/v1/mcp/servers",
        token=token,
        json_body={
            "name": f"ProdTest-MCP-{run_id}",
            "script": "knowledge_retrieval.py",
            "command": "python",
            "args": "[]",
            "cwd": "/app",
            "env_vars": "{}",
        },
    )
    _check(results, "POST /api/v1/mcp/servers", code, 200)
    if code == 200 and isinstance(body, dict):
        mcp_id = int(body.get("id") or 0) or None

    # 4) Cleanup
    if lead_id is not None:
        code, _ = _request(
            "DELETE",
            base_url,
            f"/api/v1/leads/{lead_id}",
            token=token,
        )
        _check(results, f"DELETE /api/v1/leads/{lead_id}", code, 200)

    if mcp_id is not None:
        code, _ = _request(
            "DELETE",
            base_url,
            f"/api/v1/mcp/servers/{mcp_id}",
            token=token,
        )
        _check(results, f"DELETE /api/v1/mcp/servers/{mcp_id}", code, 200)

    passed = sum(1 for r in results if r.ok)
    failed = len(results) - passed
    end_ts = utc_now_iso()

    print("\nSummary")
    print(f"- Start (UTC): {start_ts}")
    print(f"- End (UTC):   {end_ts}")
    print(f"- Total checks: {len(results)}")
    print(f"- Passed: {passed}")
    print(f"- Failed: {failed}")
    if lead_id is not None:
        print(f"- Created lead_id: {lead_id}")
    if mcp_id is not None:
        print(f"- Created mcp_id: {mcp_id}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        raise SystemExit(1)
