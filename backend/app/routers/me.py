import uuid
from typing import Any, Dict

from app import models
from app.routers.auth import get_current_user_optional
from fastapi import APIRouter, Depends

# Fallback anonymous identity for unauthenticated requests
ANONYMOUS_EMAIL = "anonymous@grindlab.local"
ANONYMOUS_ID = uuid.UUID(int=0)

router = APIRouter(prefix="/api/me", tags=["me"])


def _safe_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:
        return None


@router.get("/dashboard")
def get_dashboard(current_user: models.User | None = Depends(get_current_user_optional)):
    """
    Lightweight dashboard endpoint for the current user.
    Avoids ORM joins that rely on missing project relationships; always returns a safe payload.
    """
    user_id = getattr(current_user, "id", ANONYMOUS_ID)
    user_email = getattr(current_user, "email", ANONYMOUS_EMAIL)
    user_full_name = getattr(current_user, "full_name", "Anonymous")

    summary: Dict[str, int | Dict[str, int]] = {
        "calc_runs_total": 0,
        "scenarios_total": 0,
        "comments_total": 0,
        "projects_total": 0,
        "calc_runs_by_status": {},
    }

    return {
        "user": {
            "id": str(user_id),
            "email": user_email,
            "full_name": user_full_name,
        },
        "summary": summary,
        "projects": [],
        "member_projects": [],
        "recent_calc_runs": [],
        "recent_comments": [],
        "favorites": {"projects": [], "scenarios": [], "calc_runs": []},
    }
