import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


DEFAULT_BASE_URL = "http://127.0.0.1:8000"


@dataclass
class SmokeResult:
    name: str
    status: int
    ok: bool
    detail: str = ""


def _request(path: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, base_url: str = DEFAULT_BASE_URL):
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if hasattr(exc, "read") else ""
        return exc.code, body
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def _parse_json(body: str) -> Any:
    try:
        return json.loads(body)
    except Exception:
        return None


def run_smoke(base_url: str = DEFAULT_BASE_URL) -> int:
    checks: list[SmokeResult] = []

    status, body = _request("/health", base_url=base_url)
    checks.append(SmokeResult("GET /health", status, status == 200, body))

    status, body = _request("/api/me/dashboard", base_url=base_url)
    dashboard_json = _parse_json(body)
    checks.append(
        SmokeResult(
            "GET /api/me/dashboard",
            status,
            status == 200 and isinstance(dashboard_json, dict),
            body if status != 200 else "ok",
        )
    )

    status, body = _request("/api/projects/my", base_url=base_url)
    projects_json = _parse_json(body)
    initial_total = projects_json.get("total", 0) if isinstance(projects_json, dict) else 0
    checks.append(
        SmokeResult(
            "GET /api/projects/my (before seed)",
            status,
            status == 200 and isinstance(projects_json, dict),
            body if status != 200 else f"total={initial_total}",
        )
    )

    status, body = _request("/api/projects/demo-seed", method="POST", base_url=base_url)
    checks.append(
        SmokeResult(
            "POST /api/projects/demo-seed",
            status,
            status == 200,
            body if status != 200 else "seeded",
        )
    )

    status, body = _request("/api/projects/my", base_url=base_url)
    projects_json = _parse_json(body)
    items_after = projects_json.get("items") if isinstance(projects_json, dict) else None
    total_after = projects_json.get("total") if isinstance(projects_json, dict) else None
    ok_after = (
        status == 200
        and isinstance(items_after, list)
        and isinstance(total_after, int)
        and (len(items_after) > 0 or (isinstance(total_after, int) and total_after > 0))
    )
    checks.append(
        SmokeResult(
            "GET /api/projects/my (after seed)",
            status,
            ok_after,
            body if status != 200 else f"items={len(items_after or [])}, total={total_after}",
        )
    )

    failed = [c for c in checks if not c.ok]
    for check in checks:
        status_str = "OK" if check.ok else "FAIL"
        print(f"[{status_str}] {check.name} -> {check.status} {check.detail}")

    return 0 if not failed else 1


if __name__ == "__main__":
    base = DEFAULT_BASE_URL
    if len(sys.argv) > 1 and sys.argv[1]:
        base = sys.argv[1]
    # give the server a brief moment if it was just started
    time.sleep(0.2)
    sys.exit(run_smoke(base))
