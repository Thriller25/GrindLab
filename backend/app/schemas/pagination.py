# Pagination schemas for paginated API responses
from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.

    Example:
        PaginatedResponse[ProjectRead](
            total=100,
            skip=0,
            limit=10,
            items=[...],
            has_more=True
        )
    """

    total: int = Field(..., description="Total number of items in database")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, le=100, description="Number of items returned")
    items: List[T] = Field(..., description="List of items")

    @property
    def has_more(self) -> bool:
        """Check if there are more items after current page"""
        return (self.skip + self.limit) < self.total

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages"""
        return (self.total + self.limit - 1) // self.limit

    @property
    def current_page(self) -> int:
        """Calculate current page number (0-indexed)"""
        return self.skip // self.limit if self.limit > 0 else 0


__all__ = ["PaginatedResponse"]
