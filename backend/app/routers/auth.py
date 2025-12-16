import uuid

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
    ChangePasswordRequest,
    Token,
    UserActivitySummary,
    UserCreate,
    UserLogin,
    UserRead,
)

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
    scenarios_total = (
        db.query(func.count(models.CalcScenario.id))
        .filter(models.CalcScenario.created_by_user_id == current_user.id)
        .scalar()
    ) or 0

    calc_runs_total = (
        db.query(func.count(models.CalcRun.id))
        .filter(models.CalcRun.started_by_user_id == current_user.id)
        .scalar()
    ) or 0

    status_rows = (
        db.query(models.CalcRun.status, func.count(models.CalcRun.id))
        .filter(models.CalcRun.started_by_user_id == current_user.id)
        .group_by(models.CalcRun.status)
        .all()
    )
    calc_runs_by_status = {status: count for status, count in status_rows if status is not None}

    comments_total = (
        db.query(func.count(models.Comment.id))
        .filter(models.Comment.author == current_user.email)
        .scalar()
    ) or 0

    scenario_last = (
        db.query(func.max(models.CalcScenario.created_at))
        .filter(models.CalcScenario.created_by_user_id == current_user.id)
        .scalar()
    )
    run_last = (
        db.query(func.max(models.CalcRun.started_at))
        .filter(models.CalcRun.started_by_user_id == current_user.id)
        .scalar()
    )
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
