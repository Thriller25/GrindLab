import uuid
from typing import List

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.schemas import (
    CalcRunListItem,
    ChangePasswordRequest,
    CommentRead,
    FavoriteCreate,
    FavoriteRead,
    CalcScenarioRead,
    ProjectRead,
    Token,
    UserActivitySummary,
    UserCreate,
    UserDashboardResponse,
    UserLogin,
    UserRead,
)
from app.schemas.user import UserFavoritesGrouped

router = APIRouter(prefix="/api/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user = models.User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user, from_attributes=True)


@router.post("/login", response_model=UserRead)
def login_user(payload: UserLogin, db: Session = Depends(get_db)) -> UserRead:
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return UserRead.model_validate(user, from_attributes=True)


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token, token_type="bearer")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_uuid = uuid.UUID(user_id)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = db.get(models.User, user_uuid)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


async def get_current_user_optional(
    token: str = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> models.User | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            return None
        user_uuid = uuid.UUID(user_id)
    except (jwt.PyJWTError, ValueError):
        return None

    user = db.get(models.User, user_uuid)
    if user is None or not user.is_active:
        return None
    return user


@router.get("/me", response_model=UserRead)
async def read_users_me(current_user: models.User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user, from_attributes=True)


def _calculate_user_summary(db: Session, current_user: models.User) -> UserActivitySummary:
    if hasattr(models.CalcScenario, "created_by_user_id"):
        scenarios_total = (
            db.query(func.count(models.CalcScenario.id))
            .filter(models.CalcScenario.created_by_user_id == current_user.id)
            .scalar()
        ) or 0
    else:
        scenarios_total = 0

    if hasattr(models.CalcRun, "started_by_user_id"):
        calc_runs_total = (
            db.query(func.count(models.CalcRun.id))
            .filter(models.CalcRun.started_by_user_id == current_user.id)
            .scalar()
        ) or 0
    else:
        calc_runs_total = db.query(func.count(models.CalcRun.id)).scalar() or 0

    status_query = db.query(models.CalcRun.status, func.count(models.CalcRun.id))
    if hasattr(models.CalcRun, "started_by_user_id"):
        status_query = status_query.filter(models.CalcRun.started_by_user_id == current_user.id)
    status_rows = status_query.group_by(models.CalcRun.status).all()
    calc_runs_by_status = {status: count for status, count in status_rows if status is not None}

    comments_total = (
        db.query(func.count(models.Comment.id))
        .filter(models.Comment.author == current_user.email)
        .scalar()
    ) or 0

    if hasattr(models.CalcScenario, "created_by_user_id"):
        scenario_last = (
            db.query(func.max(models.CalcScenario.created_at))
            .filter(models.CalcScenario.created_by_user_id == current_user.id)
            .scalar()
        )
    else:
        scenario_last = None
    run_last_query = db.query(func.max(models.CalcRun.started_at))
    if hasattr(models.CalcRun, "started_by_user_id"):
        run_last_query = run_last_query.filter(models.CalcRun.started_by_user_id == current_user.id)
    run_last = run_last_query.scalar()
    comment_last = (
        db.query(func.max(models.Comment.created_at))
        .filter(models.Comment.author == current_user.email)
        .scalar()
    )
    last_candidates = [dt for dt in (scenario_last, run_last, comment_last) if dt is not None]
    last_activity_at = max(last_candidates) if last_candidates else None

    return UserActivitySummary(
        user=UserRead.model_validate(current_user, from_attributes=True),
        scenarios_total=scenarios_total,
        calc_runs_total=calc_runs_total,
        calc_runs_by_status=calc_runs_by_status,
        comments_total=comments_total,
        last_activity_at=last_activity_at,
    )


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect old password")

    current_user.hashed_password = hash_password(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"detail": "Password changed successfully"}


@router.get("/me/summary", response_model=UserActivitySummary)
def get_me_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> UserActivitySummary:
    return _calculate_user_summary(db, current_user)


RECENT_RUNS_LIMIT = 10
RECENT_COMMENTS_LIMIT = 10
VALID_FAVORITE_TYPES = {"project", "scenario", "calc_run"}


@router.get("/me/favorites", response_model=List[FavoriteRead])
def get_my_favorites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[FavoriteRead]:
    favorites = (
        db.query(models.UserFavorite)
        .filter(models.UserFavorite.user_id == current_user.id)
        .order_by(models.UserFavorite.created_at.desc())
        .all()
    )
    return [FavoriteRead.model_validate(fav, from_attributes=True) for fav in favorites]


@router.post("/me/favorites", response_model=FavoriteRead, status_code=status.HTTP_201_CREATED)
def add_favorite(
    payload: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> FavoriteRead:
    if payload.entity_type not in VALID_FAVORITE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported entity_type")

    if payload.entity_type == "project":
        entity = db.get(models.Project, payload.entity_id)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    elif payload.entity_type == "scenario":
        entity = db.get(models.CalcScenario, payload.entity_id)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    elif payload.entity_type == "calc_run":
        entity = db.get(models.CalcRun, payload.entity_id)
        if entity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calc run not found")

    existing = (
        db.query(models.UserFavorite)
        .filter(
            models.UserFavorite.user_id == current_user.id,
            models.UserFavorite.entity_type == payload.entity_type,
            models.UserFavorite.entity_id == payload.entity_id,
        )
        .first()
    )
    if existing:
        return FavoriteRead.model_validate(existing, from_attributes=True)

    favorite = models.UserFavorite(
        user_id=current_user.id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return FavoriteRead.model_validate(favorite, from_attributes=True)


@router.delete("/me/favorites/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    favorite_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    favorite = (
        db.query(models.UserFavorite)
        .filter(models.UserFavorite.id == favorite_id, models.UserFavorite.user_id == current_user.id)
        .first()
    )
    if favorite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found")

    db.delete(favorite)
    db.commit()
    return None


@router.get("/me/dashboard", response_model=UserDashboardResponse)
def get_me_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> UserDashboardResponse:
    summary = _calculate_user_summary(db, current_user)

    projects_owner = (
        db.query(models.Project)
        .filter(models.Project.owner_user_id == current_user.id)
        .order_by(models.Project.created_at.desc())
        .all()
    )
    projects_owner_dto = [ProjectRead.model_validate(p, from_attributes=True) for p in projects_owner]

    member_links = db.query(models.ProjectMember).filter(models.ProjectMember.user_id == current_user.id).all()
    member_project_ids = [link.project_id for link in member_links]
    if member_project_ids:
        projects_member = (
            db.query(models.Project)
            .filter(models.Project.id.in_(member_project_ids), models.Project.owner_user_id != current_user.id)
            .order_by(models.Project.created_at.desc())
            .all()
        )
    else:
        projects_member = []
    projects_member_dto = [ProjectRead.model_validate(p, from_attributes=True) for p in projects_member]

    recent_runs_query = db.query(models.CalcRun)
    if hasattr(models.CalcRun, "started_by_user_id"):
        recent_runs_query = recent_runs_query.filter(models.CalcRun.started_by_user_id == current_user.id)
    recent_runs = (
        recent_runs_query.order_by(models.CalcRun.started_at.desc().nullslast())
        .limit(RECENT_RUNS_LIMIT)
        .all()
    )
    recent_runs_dto = [CalcRunListItem.model_validate(r, from_attributes=True) for r in recent_runs]

    recent_comments = (
        db.query(models.Comment)
        .filter(models.Comment.author == current_user.email)
        .order_by(models.Comment.created_at.desc())
        .limit(RECENT_COMMENTS_LIMIT)
        .all()
    )
    recent_comments_dto = [CommentRead.model_validate(c, from_attributes=True) for c in recent_comments]

    favorites = db.query(models.UserFavorite).filter(models.UserFavorite.user_id == current_user.id).all()
    project_ids = [fav.entity_id for fav in favorites if fav.entity_type == "project"]
    scenario_ids = [fav.entity_id for fav in favorites if fav.entity_type == "scenario"]
    run_ids = [fav.entity_id for fav in favorites if fav.entity_type == "calc_run"]

    if project_ids:
        favorite_projects = db.query(models.Project).filter(models.Project.id.in_(project_ids)).all()
    else:
        favorite_projects = []
    if scenario_ids:
        favorite_scenarios = db.query(models.CalcScenario).filter(models.CalcScenario.id.in_(scenario_ids)).all()
    else:
        favorite_scenarios = []
    if run_ids:
        favorite_runs = db.query(models.CalcRun).filter(models.CalcRun.id.in_(run_ids)).all()
    else:
        favorite_runs = []

    favorites_grouped = UserFavoritesGrouped(
        projects=[ProjectRead.model_validate(p, from_attributes=True) for p in favorite_projects],
        scenarios=[CalcScenarioRead.model_validate(s, from_attributes=True) for s in favorite_scenarios],
        calc_runs=[CalcRunListItem.model_validate(r, from_attributes=True) for r in favorite_runs],
    )

    return UserDashboardResponse(
        user=UserRead.model_validate(current_user, from_attributes=True),
        summary=summary,
        projects=projects_owner_dto,
        member_projects=projects_member_dto,
        recent_calc_runs=recent_runs_dto,
        recent_comments=recent_comments_dto,
        favorites=favorites_grouped,
    )
