import uuid
from datetime import datetime
from pydantic import BaseModel

class FavoriteBase(BaseModel):
    entity_type: str
    entity_id: uuid.UUID


class FavoriteCreate(FavoriteBase):
    pass


class FavoriteRead(FavoriteBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
