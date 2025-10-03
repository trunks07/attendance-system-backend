from datetime import datetime
from typing import Any, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import core_schema

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> core_schema.CoreSchema:
        return core_schema.with_info_after_validator_function(
            cls.validate,
            core_schema.str_schema(),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, value: str, _info: Any) -> ObjectId:
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")
        return ObjectId(value)

class TribeBase(BaseModel):
    name: str
    description: str

class TribeCreate(TribeBase):
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class TribeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.now)

class Tribe(TribeBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        json_encoders={ObjectId: str},
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        elif isinstance(v, datetime):
            return v
        return datetime.now()
