import uuid

from app import models
from app.db import get_db
from app.routers.auth import get_current_user
from app.schemas import (
    CalcRunListItem,
    CalcScenarioRead,
    FavoriteCreate,
    FavoriteRead,
    ProjectRead,
    UserActivitySummary,
    UserDashboardResponse,
    UserFavoritesGrouped,
    UserRead,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/auth/me", tags=["favorites"])

_SUPPORTED_TYPES = {
    "project": (models.Project, int),
    "scenario": (models.CalcScenario, uuid.UUID),
    "calc_run": (models.CalcRun, uuid.UUID),
}


def _validate_entity(db: Session, entity_type: str, entity_id: str) -> str:
    if entity_type not in _SUPPORTED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported entity_type"
        )
    model_cls, caster = _SUPPORTED_TYPES[entity_type]
    try:
        parsed_id = caster(entity_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    obj = db.get(model_cls, parsed_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return str(parsed_id)


@router.post("/favorites", response_model=FavoriteRead, status_code=status.HTTP_201_CREATED)
def add_favorite(
    payload: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> FavoriteRead:
    entity_id_str = _validate_entity(db, payload.entity_type, str(payload.entity_id))
    existing = (
        db.query(models.UserFavorite)
        .filter(
            models.UserFavorite.user_id == current_user.id,
            models.UserFavorite.entity_type == payload.entity_type,
            models.UserFavorite.entity_id == entity_id_str,
        )
        .first()
    )
    if existing:
        return FavoriteRead.model_validate(existing, from_attributes=True)

    favorite = models.UserFavorite(
        user_id=current_user.id,
        entity_type=payload.entity_type,
        entity_id=entity_id_str,
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return FavoriteRead.model_validate(favorite, from_attributes=True)


@router.get("/favorites", response_model=list[FavoriteRead])
def list_favorites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> list[FavoriteRead]:
    favorites = (
        db.query(models.UserFavorite)
        .filter(models.UserFavorite.user_id == current_user.id)
        .order_by(models.UserFavorite.created_at.desc())
        .all()
    )
    return [FavoriteRead.model_validate(f, from_attributes=True) for f in favorites]


@router.delete("/favorites/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    favorite = db.get(models.UserFavorite, favorite_id)
    if favorite is None or favorite.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")
    db.delete(favorite)
    db.commit()
    return None


@router.get("/dashboard", response_model=UserDashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> UserDashboardResponse:
    favorites = (
        db.query(models.UserFavorite).filter(models.UserFavorite.user_id == current_user.id).all()
    )

    project_ids = [int(f.entity_id) for f in favorites if f.entity_type == "project"]
    scenario_ids = []
    run_ids = []
    for f in favorites:
        if f.entity_type == "scenario":
            try:
                scenario_ids.append(uuid.UUID(f.entity_id))
            except Exception:
                continue
        elif f.entity_type == "calc_run":
            try:
                run_ids.append(uuid.UUID(f.entity_id))
            except Exception:
                continue

    projects = (
        db.query(models.Project).filter(models.Project.id.in_(project_ids)).all()
        if project_ids
        else []
    )
    scenarios = (
        db.query(models.CalcScenario).filter(models.CalcScenario.id.in_(scenario_ids)).all()
        if scenario_ids
        else []
    )
    runs = db.query(models.CalcRun).filter(models.CalcRun.id.in_(run_ids)).all() if run_ids else []

    favorites_grouped = UserFavoritesGrouped(
        projects=[ProjectRead.model_validate(p, from_attributes=True) for p in projects],
        scenarios=[CalcScenarioRead.model_validate(s, from_attributes=True) for s in scenarios],
        calc_runs=[CalcRunListItem.model_validate(r, from_attributes=True) for r in runs],
    )

    summary = UserActivitySummary(
        user=UserRead.model_validate(current_user, from_attributes=True),
        scenarios_total=0,
        calc_runs_total=0,
        calc_runs_by_status={},
        comments_total=0,
        last_activity_at=None,
    )

    return UserDashboardResponse(
        user=UserRead.model_validate(current_user, from_attributes=True),
        summary=summary,
        projects=[],
        member_projects=[],
        recent_calc_runs=[],
        recent_comments=[],
        favorites=favorites_grouped,
    )
