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


def _print_results(checks: list[SmokeResult]) -> int:
    failures = [c for c in checks if not c.ok]
    for check in checks:
        status_str = "OK" if check.ok else "FAIL"
        print(f"[{status_str}] {check.name} -> {check.status} {check.detail}")

    if failures:
        print(f"FAIL ({len(failures)}/{len(checks)}) smoke checks failed")
        return 1

    print(f"PASS ({len(checks)}) smoke checks passed")
    return 0


def run_smoke(base_url: str = DEFAULT_BASE_URL) -> int:
    checks: list[SmokeResult] = []
    project: dict[str, Any] | None = None
    project_id: int | None = None
    project_plant_id: Any = None
    initial_calc_runs_total: int | None = None
    flowsheet_version_id: Any = None
    new_run_id: Any = None

    def add_check(name: str, status: int, ok: bool, detail: str) -> None:
        checks.append(SmokeResult(name=name, status=status, ok=ok, detail=detail))

    status, body = _request("/health", base_url=base_url)
    add_check("GET /health", status, status == 200, "ok" if status == 200 else body)
    if status != 200:
        return _print_results(checks)

    status, body = _request("/api/projects/my", base_url=base_url)
    projects_json = _parse_json(body)
    items = projects_json.get("items") if isinstance(projects_json, dict) else None
    total = projects_json.get("total") if isinstance(projects_json, dict) else None
    ok_projects = status == 200 and isinstance(items, list) and isinstance(total, int)
    add_check(
        "GET /api/projects/my",
        status,
        ok_projects,
        body if not ok_projects else f"items={len(items)} total={total}",
    )
    if not ok_projects:
        return _print_results(checks)

    project = items[0] if items else None
    project_id = project.get("id") if isinstance(project, dict) else None
    project_owner = project.get("owner_user_id") if isinstance(project, dict) else None
    project_plant_id = project.get("plant_id") if isinstance(project, dict) else None
    ok_project = project_id is not None and project_owner is None
    add_check(
        "Select first project",
        status if status != 200 else 200,
        ok_project,
        "no projects returned; seed demo data first" if project_id is None else f"id={project_id} owner={project_owner}",
    )
    if not ok_project:
        return _print_results(checks)

    status, body = _request(f"/api/projects/{project_id}/dashboard", base_url=base_url)
    dashboard_json = _parse_json(body)
    summary = dashboard_json.get("summary") if isinstance(dashboard_json, dict) else None
    calc_runs_total = summary.get("calc_runs_total") if isinstance(summary, dict) else None
    flowsheet_versions = dashboard_json.get("flowsheet_versions") if isinstance(dashboard_json, dict) else None
    project_block = dashboard_json.get("project") if isinstance(dashboard_json, dict) else None
    ok_dashboard = (
        status == 200
        and isinstance(calc_runs_total, int)
        and isinstance(flowsheet_versions, list)
        and project_block is not None
    )
    add_check(
        f"GET /api/projects/{project_id}/dashboard",
        status,
        ok_dashboard,
        body if not ok_dashboard else f"calc_runs_total={calc_runs_total} flowsheet_versions={len(flowsheet_versions)}",
    )
    if not ok_dashboard:
        return _print_results(checks)

    initial_calc_runs_total = calc_runs_total
    flowsheet_version = flowsheet_versions[0] if flowsheet_versions else None
    flowsheet_version_id = flowsheet_version.get("id") if isinstance(flowsheet_version, dict) else None
    ok_flowsheet_version = flowsheet_version_id is not None
    add_check(
        "Pick flowsheet_version_id",
        status,
        ok_flowsheet_version,
        "no flowsheet_versions linked to project" if not ok_flowsheet_version else f"id={flowsheet_version_id}",
    )
    if not ok_flowsheet_version:
        return _print_results(checks)

    plant_id_value = project_block.get("plant_id") if isinstance(project_block, dict) else project_plant_id
    payload = {
        "model_version": "grind_mvp_v1",
        "plant_id": plant_id_value or "demo-plant",
        "flowsheet_version_id": flowsheet_version_id,
        "project_id": project_id,
        "scenario_name": "smoke-auto",
        "feed": {"tonnage_tph": 500.0, "p80_mm": 12.0, "density_t_per_m3": 2.7},
        "mill": {
            "type": "SAG",
            "power_installed_kw": 8000.0,
            "power_draw_kw": 7200.0,
            "ball_charge_percent": 12.0,
            "speed_percent_critical": 75.0,
        },
        "classifier": {
            "type": "cyclone",
            "cut_size_p80_mm": 0.18,
            "circulating_load_percent": 250.0,
        },
        "options": {"use_baseline_run_id": None},
    }

    status, body = _request("/api/calc/grind-mvp-runs", method="POST", payload=payload, base_url=base_url)
    run_json = _parse_json(body)
    new_run_id = run_json.get("calc_run_id") if isinstance(run_json, dict) else None
    ok_run = status == 200 and new_run_id is not None
    add_check(
        "POST /api/calc/grind-mvp-runs",
        status,
        ok_run,
        body if not ok_run else f"calc_run_id={new_run_id}",
    )
    if not ok_run:
        return _print_results(checks)

    status, body = _request(f"/api/projects/{project_id}/dashboard", base_url=base_url)
    dashboard_after_json = _parse_json(body)
    summary_after = dashboard_after_json.get("summary") if isinstance(dashboard_after_json, dict) else None
    calc_runs_total_after = summary_after.get("calc_runs_total") if isinstance(summary_after, dict) else None
    recent_runs = dashboard_after_json.get("recent_calc_runs") if isinstance(dashboard_after_json, dict) else None
    ok_dashboard_after = (
        status == 200 and isinstance(calc_runs_total_after, int) and isinstance(recent_runs, list)
    )
    add_check(
        f"GET /api/projects/{project_id}/dashboard (after run)",
        status,
        ok_dashboard_after,
        body if not ok_dashboard_after else f"calc_runs_total={calc_runs_total_after} recent={len(recent_runs)}",
    )
    if not ok_dashboard_after:
        return _print_results(checks)

    ok_counter = calc_runs_total_after == (initial_calc_runs_total or 0) + 1
    add_check(
        "calc_runs_total increased",
        status,
        ok_counter,
        f"before={initial_calc_runs_total}, after={calc_runs_total_after}",
    )
    if not ok_counter:
        return _print_results(checks)

    recent_ids = {str(item.get("id")) for item in recent_runs if isinstance(item, dict)}
    ok_recent = str(new_run_id) in recent_ids
    add_check(
        "recent_calc_runs contains new run",
        status,
        ok_recent,
        f"new_run_id={new_run_id}",
    )

    return _print_results(checks)


if __name__ == "__main__":
    base = DEFAULT_BASE_URL
    if len(sys.argv) > 1 and sys.argv[1]:
        base = sys.argv[1]
    # give the server a brief moment if it was just started
    time.sleep(0.2)
    sys.exit(run_smoke(base))
