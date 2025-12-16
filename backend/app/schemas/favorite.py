from datetime import datetime

from pydantic import BaseModel


class FavoriteBase(BaseModel):
    entity_type: str
    entity_id: str | int


class FavoriteCreate(FavoriteBase):
    pass


class FavoriteRead(FavoriteBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
