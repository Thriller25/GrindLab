import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.schemas import CommentBase, CommentCreate, CommentListResponse, CommentRead, UserCommentCreate
from app.routers.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/comments", tags=["comments"])
me_router = APIRouter(prefix="/api", tags=["comments"])


def _validate_entity(db: Session, entity_type: str, entity_id: uuid.UUID) -> None:
    entity_id_str = str(entity_id)
    if entity_type == "calc_run":
        if db.get(models.CalcRun, entity_id_str) is None:
            raise HTTPException(status_code=404, detail=f"CalcRun {entity_id} not found")
    elif entity_type == "scenario":
        if db.get(models.CalcScenario, entity_id_str) is None:
            raise HTTPException(status_code=404, detail=f"CalcScenario {entity_id} not found")
    else:
        raise HTTPException(status_code=400, detail="Unsupported entity_type")


def _create_comment(
    db: Session, entity_type: str, entity_id: uuid.UUID, payload: CommentBase
) -> models.Comment:
    _validate_entity(db, entity_type, entity_id)
    comment = models.Comment(
        entity_type=entity_type,
        entity_id=str(entity_id),
        author=payload.author,
        text=payload.text,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.post("/", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(payload: CommentCreate, db: Session = Depends(get_db)) -> CommentRead:
    comment = _create_comment(db, payload.entity_type, payload.entity_id, payload)
    return CommentRead.model_validate(comment, from_attributes=True)


@router.post("/calc-runs/{run_id}", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment_for_run(run_id: uuid.UUID, payload: CommentBase, db: Session = Depends(get_db)) -> CommentRead:
    comment = _create_comment(db, "calc_run", run_id, payload)
    return CommentRead.model_validate(comment, from_attributes=True)


@router.post("/calc-scenarios/{scenario_id}", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment_for_scenario(
    scenario_id: uuid.UUID, payload: CommentBase, db: Session = Depends(get_db)
) -> CommentRead:
    comment = _create_comment(db, "scenario", scenario_id, payload)
    return CommentRead.model_validate(comment, from_attributes=True)


@router.post("/calc-runs/{run_id}/comments/me", response_model=CommentRead)
def create_comment_for_run_me(
    run_id: uuid.UUID,
    payload: UserCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    comment = _create_comment(
        db,
        "calc_run",
        run_id,
        CommentBase(author=current_user.email, text=payload.text),
    )
    return CommentRead.model_validate(comment, from_attributes=True)


@router.post("/calc-scenarios/{scenario_id}/comments/me", response_model=CommentRead)
def create_comment_for_scenario_me(
    scenario_id: uuid.UUID,
    payload: UserCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    comment = _create_comment(
        db,
        "scenario",
        scenario_id,
        CommentBase(author=current_user.email, text=payload.text),
    )
    return CommentRead.model_validate(comment, from_attributes=True)


@me_router.post("/calc-runs/{run_id}/comments/me", response_model=CommentRead)
def create_comment_for_run_me_direct(
    run_id: uuid.UUID,
    payload: UserCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    return create_comment_for_run_me(run_id, payload, db, current_user)


@me_router.post("/calc-scenarios/{scenario_id}/comments/me", response_model=CommentRead)
def create_comment_for_scenario_me_direct(
    scenario_id: uuid.UUID,
    payload: UserCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    return create_comment_for_scenario_me(scenario_id, payload, db, current_user)


@router.get("/by-entity", response_model=CommentListResponse)
def list_comments_by_entity(
    entity_type: str = Query(..., description="calc_run or scenario"),
    entity_id: uuid.UUID = Query(...),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> CommentListResponse:
    _validate_entity(db, entity_type, entity_id)
    query = db.query(models.Comment).filter(
        models.Comment.entity_type == entity_type, models.Comment.entity_id == str(entity_id)
    )
    total = query.with_entities(func.count()).scalar() or 0
    comments = query.order_by(models.Comment.created_at.desc()).offset(offset).limit(limit).all()
    items = [CommentRead.model_validate(comment, from_attributes=True) for comment in comments]
    return CommentListResponse(items=items, total=total)


@router.get("/calc-runs/{run_id}", response_model=CommentListResponse)
def list_comments_for_run(
    run_id: uuid.UUID, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)
) -> CommentListResponse:
    return list_comments_by_entity("calc_run", run_id, limit, offset, db)


@router.get("/calc-scenarios/{scenario_id}", response_model=CommentListResponse)
def list_comments_for_scenario(
    scenario_id: uuid.UUID, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)
) -> CommentListResponse:
    return list_comments_by_entity("scenario", scenario_id, limit, offset, db)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: uuid.UUID, db: Session = Depends(get_db)):
    comment = db.get(models.Comment, str(comment_id))
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    db.delete(comment)
    db.commit()
    return None
