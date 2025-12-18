import uuid
from datetime import datetime, timedelta, timezone

from app import models
from app.db import SessionLocal

DEMO_PREFIX = "DEMO_"


def _clear_demo(session):
    flowsheets = session.query(models.Flowsheet).filter(models.Flowsheet.name.like(f"{DEMO_PREFIX}%")).all()
    flowsheet_ids = [fs.id for fs in flowsheets]
    version_ids = [
        v.id for v in session.query(models.FlowsheetVersion.id).filter(models.FlowsheetVersion.flowsheet_id.in_(flowsheet_ids))
    ]

    if version_ids:
        session.query(models.ProjectFlowsheetVersion).filter(
            models.ProjectFlowsheetVersion.flowsheet_version_id.in_(version_ids)
        ).delete(synchronize_session=False)
        session.query(models.CalcRun).filter(models.CalcRun.flowsheet_version_id.in_(version_ids)).delete(
            synchronize_session=False
        )
        session.query(models.CalcScenario).filter(models.CalcScenario.flowsheet_version_id.in_(version_ids)).delete(
            synchronize_session=False
        )
        session.query(models.Unit).filter(models.Unit.flowsheet_version_id.in_(version_ids)).delete(
            synchronize_session=False
        )
        session.query(models.FlowsheetVersion).filter(models.FlowsheetVersion.id.in_(version_ids)).delete(
            synchronize_session=False
        )

    if flowsheet_ids:
        session.query(models.Flowsheet).filter(models.Flowsheet.id.in_(flowsheet_ids)).delete(synchronize_session=False)

    session.query(models.Project).filter(models.Project.name.like(f"{DEMO_PREFIX}%")).delete(synchronize_session=False)
    session.query(models.Plant).filter(models.Plant.name.like(f"{DEMO_PREFIX}%")).delete(synchronize_session=False)
    session.commit()


def seed_demo():
    session = SessionLocal()
    try:
        _clear_demo(session)

        plant = models.Plant(name=f"{DEMO_PREFIX}Demo Plant", code="DEMO_PLANT", company="Demo Co")
        session.add(plant)
        session.flush()

        flowsheet = models.Flowsheet(
            plant_id=plant.id,
            name=f"{DEMO_PREFIX}Flowsheet",
            description="Demo flowsheet for UI",
            status="ACTIVE",
        )
        session.add(flowsheet)
        session.flush()

        version = models.FlowsheetVersion(
            flowsheet_id=flowsheet.id,
            version_label="DEMO_v1",
            status="ACTIVE",
            is_active=True,
            comment="Demo version",
        )
        session.add(version)
        session.flush()

        project = models.Project(
            name=f"{DEMO_PREFIX}Project",
            description="Demo project for UI scenarios",
            owner_user_id=None,
            plant_id=plant.id,
        )
        session.add(project)
        session.flush()

        link = models.ProjectFlowsheetVersion(project_id=project.id, flowsheet_version_id=version.id)
        session.add(link)
        session.flush()

        units = []
        for idx, name in enumerate(["Crusher", "Mill", "Classifier", "Thickener", "Pump"], start=1):
            unit = models.Unit(
                flowsheet_version_id=version.id,
                name=f"{DEMO_PREFIX}{name}",
                tag=f"U-{idx:02d}",
                order_index=idx,
                position_x=idx * 100,
                position_y=idx * 50,
                participates_in_opt=True,
                is_active=True,
            )
            units.append(unit)
        session.add_all(units)

        base_input = {"feed_tph": 200.0, "target_p80_microns": 180.0, "model_version": "grind_mvp_v1"}
        scenario_base = models.CalcScenario(
            flowsheet_version_id=version.id,
            project_id=project.id,
            name=f"{DEMO_PREFIX}Base",
            description="Base demo scenario",
            default_input_json=base_input,
            is_baseline=True,
        )
        scenario_test = models.CalcScenario(
            flowsheet_version_id=version.id,
            project_id=project.id,
            name=f"{DEMO_PREFIX}Test",
            description="Test demo scenario",
            default_input_json={**base_input, "feed_tph": 220.0},
            is_baseline=False,
        )
        session.add_all([scenario_base, scenario_test])
        session.flush()

        now = datetime.now(timezone.utc)
        runs = []
        for i, scenario in enumerate([scenario_base, scenario_test, scenario_test], start=1):
            started = now - timedelta(hours=6 * i)
            finished = started + timedelta(minutes=5)
            runs.append(
                models.CalcRun(
                    flowsheet_version_id=version.id,
                    scenario_id=scenario.id,
                    scenario_name=scenario.name,
                    project_id=project.id,
                    comment=f"{DEMO_PREFIX}Run {i}",
                    status="success",
                    started_at=started,
                    finished_at=finished,
                    input_json=scenario.default_input_json,
                    result_json={
                        "model_version": "grind_mvp_v1",
                        "kpi": {
                            "throughput_tph": scenario.default_input_json.get("feed_tph", 0) + i * 5,
                            "product_p80_mm": 0.18,
                            "specific_energy_kwh_per_t": 10.0 + i,
                            "circulating_load_percent": 250.0,
                            "mill_utilization_percent": 80.0 + i,
                        },
                    },
                )
            )
        session.add_all(runs)
        session.commit()

        print("Seeded demo data:")
        print(f"Plant: {plant.id}")
        print(f"Flowsheet: {flowsheet.id}")
        print(f"FlowsheetVersion: {version.id}")
        print(f"Scenarios: {[scenario_base.id, scenario_test.id]}")
        print(f"CalcRuns: {[r.id for r in runs]}")
        print("seed completed")
    finally:
        session.close()


if __name__ == "__main__":
    seed_demo()
