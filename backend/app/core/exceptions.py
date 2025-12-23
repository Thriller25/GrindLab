"""
Custom exception classes and error handling utilities for GrindLab.
"""

from typing import Any, Optional

from fastapi import HTTPException, status


class GrindLabException(Exception):
    """Base exception for GrindLab application."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFound(GrindLabException):
    """Raised when a requested resource is not found."""

    pass


class PermissionDenied(GrindLabException):
    """Raised when user doesn't have permission to perform action."""

    pass


class InvalidInput(GrindLabException):
    """Raised when input validation fails."""

    pass


def raise_not_found(resource_type: str, identifier: Any = None, message: str = None) -> None:
    """
    Raise a 404 HTTPException with descriptive message.

    Args:
        resource_type: Type of resource (e.g., "Project", "User", "Plant")
        identifier: The ID/identifier that was not found
        message: Custom message (overrides default)

    Raises:
        HTTPException: 404 Not Found
    """
    if message:
        detail = message
    elif identifier:
        detail = f"{resource_type} with id '{identifier}' not found"
    else:
        detail = f"{resource_type} not found"

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def raise_permission_denied(message: str = None, action: str = None) -> None:
    """
    Raise a 403 HTTPException with descriptive message.

    Args:
        message: Custom message
        action: The action that was denied (e.g., "edit project", "delete user")

    Raises:
        HTTPException: 403 Forbidden
    """
    if message:
        detail = message
    elif action:
        detail = f"You don't have permission to {action}"
    else:
        detail = "Permission denied"

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def raise_bad_request(message: str, field: str = None) -> None:
    """
    Raise a 400 HTTPException with descriptive message.

    Args:
        message: Description of what's invalid
        field: Field name that's invalid (optional)

    Raises:
        HTTPException: 400 Bad Request
    """
    if field:
        detail = f"Invalid value for '{field}': {message}"
    else:
        detail = message

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def raise_conflict(message: str, existing: Any = None) -> None:
    """
    Raise a 409 HTTPException for conflicts.

    Args:
        message: Description of the conflict
        existing: Description of existing conflicting resource

    Raises:
        HTTPException: 409 Conflict
    """
    if existing:
        detail = f"{message} (existing: {existing})"
    else:
        detail = message

    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def raise_internal_error(operation: str, error: Exception = None) -> None:
    """
    Raise a 500 HTTPException for internal errors.

    Args:
        operation: What operation failed (e.g., "create demo project")
        error: The underlying exception (for logging)

    Raises:
        HTTPException: 500 Internal Server Error
    """
    detail = f"Failed to {operation}. Please try again or contact support."

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )
