from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Tuple
import uuid

from app import models
from app.core.security import hash_password
from app.db import Base, SessionLocal, engine


def _get_or_create_demo_user(db) -> models.User:
    user = db.query(models.User).first()
    if user:
        return user

    demo_user = models.User(
        email="demo@example.com",
        full_name="Demo User",
        hashed_password=hash_password("demo"),
        is_active=True,
        is_superuser=True,
    )
    db.add(demo_user)
    db.flush()
    return demo_user


def seed_plants_and_flowsheets(db) -> Tuple[Dict[str, models.Plant], Dict[str, models.FlowsheetVersion]]:
    created_any = False

    plants_data = [
        {"code": "GOLD-1", "name": "Золотоизвлекательная фабрика №1"},
        {"code": "CUZN-2", "name": "ЗИФ 2,5"},
        {"code": "FE-3", "name": "Железорудная фабрика №3"},
    ]

    plants: Dict[str, models.Plant] = {}
    for data in plants_data:
        plant = db.query(models.Plant).filter_by(code=data["code"]).first()
        if not plant:
            plant = models.Plant(**data)
            db.add(plant)
            db.flush()
            created_any = True
        plants[data["code"]] = plant

    flowsheets_data = [
        {
            "plant_code": "GOLD-1",
            "name": "Схема измельчения 1 (SAG)",
            "status": "ACTIVE",
            "description": "Базовая схема измельчения с SAG мельницей",
        },
        {
            "plant_code": "GOLD-1",
            "name": "Схема измельчения 2 (SABC)",
            "status": "DRAFT",
            "description": "SABC схема с дополнительной стадией измельчения",
        },
        {
            "plant_code": "CUZN-2",
            "name": "Cu-Zn схема 1",
            "status": "ACTIVE",
            "description": "Схема измельчения и классификации для Cu-Zn",
        },
        {
            "plant_code": "FE-3",
            "name": "Fe схема 1",
            "status": "ACTIVE",
            "description": "Железорудная схема с мельницей и классификацией",
        },
    ]

    flowsheets: Dict[Tuple[str, str], models.Flowsheet] = {}
    for data in flowsheets_data:
        plant = plants.get(data["plant_code"])
        if not plant:
            continue
        flowsheet = (
            db.query(models.Flowsheet)
            .filter_by(plant_id=plant.id, name=data["name"])
            .first()
        )
        if not flowsheet:
            flowsheet = models.Flowsheet(
                plant_id=plant.id,
                name=data["name"],
                status=data["status"],
                description=data["description"],
            )
            db.add(flowsheet)
            db.flush()
            created_any = True
        flowsheets[(data["plant_code"], data["name"])] = flowsheet

    versions_data = [
        {
            "key": "gold_base_v1",
            "plant_code": "GOLD-1",
            "flowsheet_name": "Схема измельчения 1 (SAG)",
            "version_label": "Базовая v1",
            "status": "ACTIVE",
            "is_active": True,
            "comment": "Базовая модель схемы измельчения",
        },
        {
            "key": "gold_opt_v2",
            "plant_code": "GOLD-1",
            "flowsheet_name": "Схема измельчения 1 (SAG)",
            "version_label": "Оптимизация v2",
            "status": "ACTIVE",
            "is_active": True,
            "comment": "Оптимизационная версия схемы",
        },
        {
            "key": "gold_sabc_v1",
            "plant_code": "GOLD-1",
            "flowsheet_name": "Схема измельчения 2 (SABC)",
            "version_label": "SABC v1",
            "status": "DRAFT",
            "is_active": False,
            "comment": "Черновая SABC версия",
        },
        {
            "key": "cuzn_v1",
            "plant_code": "CUZN-2",
            "flowsheet_name": "Cu-Zn схема 1",
            "version_label": "Cu-Zn v1",
            "status": "ACTIVE",
            "is_active": True,
            "comment": "Базовая Cu-Zn версия",
        },
        {
            "key": "fe_v1",
            "plant_code": "FE-3",
            "flowsheet_name": "Fe схема 1",
            "version_label": "Fe v1",
            "status": "ACTIVE",
            "is_active": True,
            "comment": "Базовая Fe версия",
        },
    ]

    versions: Dict[str, models.FlowsheetVersion] = {}
    for data in versions_data:
        flowsheet = flowsheets.get((data["plant_code"], data["flowsheet_name"]))
        if not flowsheet:
            continue
        version = (
            db.query(models.FlowsheetVersion)
            .filter_by(flowsheet_id=flowsheet.id, version_label=data["version_label"])
            .first()
        )
        if not version:
            version = models.FlowsheetVersion(
                flowsheet_id=flowsheet.id,
                version_label=data["version_label"],
                status=data["status"],
                is_active=data["is_active"],
                comment=data["comment"],
            )
            db.add(version)
            db.flush()
            created_any = True
        versions[data["key"]] = version

    if created_any:
        db.commit()
        print("Demo plants, flowsheets, and versions created successfully.")
    else:
        print("Demo plants, flowsheets, and versions already present, skipping.")

    return plants, versions


def seed_projects(db, gold_plant_id: uuid.UUID | None) -> List[models.Project]:
    created_any = False
    reset_owners = False
    projects: List[models.Project] = []

    project_specs = [
        {
            "name": "Тестовый проект 1",
            "description": "Демонстрационный проект по базовой работе схемы",
            "plant_id": gold_plant_id,
            "owner_user_id": None,
        },
        {
            "name": "Оптимизация энергопотребления",
            "description": "Поиск режима с меньшей удельной энергией",
            "plant_id": gold_plant_id,
            "owner_user_id": None,
        },
        {
            "name": "Summary No Runs",
            "description": "Демо-проект без расчётов для проверки пустых состояний.",
            "plant_id": gold_plant_id,
            "owner_user_id": None,
        },
    ]

    for spec in project_specs:
        project = db.query(models.Project).filter_by(name=spec["name"]).first()
        if not project:
            project = models.Project(
                name=spec["name"],
                description=spec["description"],
                owner_user_id=spec.get("owner_user_id"),
                plant_id=spec["plant_id"],
            )
            db.add(project)
            db.flush()
            created_any = True
        else:
            # Демо-проекты должны быть публичными
            if project.owner_user_id is not None:
                project.owner_user_id = None
                db.add(project)
                reset_owners = True
        projects.append(project)

    if created_any or reset_owners:
        db.commit()
        if created_any:
            print("Demo projects created successfully.")
        if reset_owners:
            print("Demo projects owners reset to NULL.")
    else:
        print("Demo projects already present, skipping.")

    return projects


def seed_project_flowsheet_links(
    db, projects: List[models.Project], versions: List[models.FlowsheetVersion]
) -> None:
    created_any = False
    for project in projects:
        for version in versions:
            link = (
                db.query(models.ProjectFlowsheetVersion)
                .filter_by(project_id=project.id, flowsheet_version_id=version.id)
                .first()
            )
            if link:
                continue
            link = models.ProjectFlowsheetVersion(
                project_id=project.id,
                flowsheet_version_id=version.id,
            )
            db.add(link)
            created_any = True
    if created_any:
        db.commit()
        print("Demo project-flowsheet links created successfully.")
    else:
        print("Demo project-flowsheet links already present, skipping.")


def _build_demo_input_json(
    plant_id: uuid.UUID | None,
    flowsheet_version_id: uuid.UUID,
    scenario_name: str,
    project_id: int,
) -> dict:
    return {
        "model_version": "grind_mvp_v1",
        "plant_id": str(plant_id) if plant_id is not None else None,
        "flowsheet_version_id": str(flowsheet_version_id),
        "scenario_name": scenario_name,
        "project_id": project_id,
        "feed": {"tonnage_tph": 500, "p80_mm": 0.18, "density_t_per_m3": 2.6},
        "mill": {
            "type": "SAG",
            "power_installed_kw": 15000,
            "power_draw_kw": 13000,
            "ball_charge_percent": 15,
            "speed_percent_critical": 75,
        },
        "classifier": {"type": "Hydrocyclone", "cut_size_p80_mm": 0.18, "circulating_load_percent": 250},
        "options": {"use_baseline_run_id": None},
    }


def _build_demo_result_json(
    throughput_tph: float,
    product_p80_mm: float,
    specific_energy_kwhpt: float,
    circulating_load_pct: float,
) -> dict:
    return {
        "model_version": "grind_mvp_v1",
        "kpi": {
            "throughput_tph": throughput_tph,
            "product_p80_mm": product_p80_mm,
            "specific_energy_kwh_per_t": specific_energy_kwhpt,
            "circulating_load_percent": circulating_load_pct,
            "mill_utilization_percent": 92.0,
        },
        "size_distribution": {
            "feed": [
                {"size_mm": 1.0, "cum_percent": 10},
                {"size_mm": 0.5, "cum_percent": 40},
                {"size_mm": 0.2, "cum_percent": 75},
            ],
            "product": [
                {"size_mm": 0.5, "cum_percent": 20},
                {"size_mm": 0.2, "cum_percent": 60},
                {"size_mm": 0.1, "cum_percent": 90},
            ],
        },
    }


def seed_grind_mvp_runs(
    db, projects: List[models.Project], versions: List[models.FlowsheetVersion]
) -> None:
    created_any = False
    now = datetime.now(timezone.utc)

    scenarios = [
        ("Базовый сценарий", 540.0, 0.184, 13.3, 250.0),
        ("Снижение энергии", 500.0, 0.184, 12.0, 250.0),
        ("Рост производительности", 580.0, 0.184, 14.0, 270.0),
    ]

    for project in projects:
        for version in versions:
            existing = (
                db.query(models.CalcRun)
                .filter_by(project_id=project.id, flowsheet_version_id=version.id)
                .first()
            )
            if existing:
                continue

            for scenario_name, tph, p80, spec_energy, cl in scenarios:
                run = models.CalcRun(
                    flowsheet_version_id=version.id,
                    scenario_name=scenario_name,
                    project_id=project.id,
                    status="success",
                    started_at=now,
                    finished_at=now,
                    comment="Демо расчёт",
                    input_json=_build_demo_input_json(
                        plant_id=project.plant_id,
                        flowsheet_version_id=version.id,
                        scenario_name=scenario_name,
                        project_id=project.id,
                    ),
                    result_json=_build_demo_result_json(
                        throughput_tph=tph,
                        product_p80_mm=p80,
                        specific_energy_kwhpt=spec_energy,
                        circulating_load_pct=cl,
                    ),
                )
                db.add(run)
                created_any = True

    if created_any:
        db.commit()
        print("Demo grind_mvp_v1 runs created successfully.")
    else:
        print("Demo grind_mvp_v1 runs already present, skipping.")


def seed_demo_data() -> None:
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)

        _ = _get_or_create_demo_user(db)
        plants, versions = seed_plants_and_flowsheets(db)
        gold_plant = plants.get("GOLD-1")
        projects = seed_projects(db, gold_plant_id=gold_plant.id if gold_plant else None)
        demo_versions = [versions.get("gold_base_v1"), versions.get("gold_opt_v2")]
        demo_versions = [v for v in demo_versions if v is not None]

        if projects and demo_versions:
            seed_project_flowsheet_links(db, projects, demo_versions)
            seed_grind_mvp_runs(db, projects, demo_versions)
        else:
            print("Skipping project links and runs seeding because demo data is missing.")

        print("Demo data seeded successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
