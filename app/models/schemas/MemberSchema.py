from datetime import datetime
from typing import Any, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: Any
    ) -> core_schema.CoreSchema:
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


class MemberBase(BaseModel):
    first_name: str
    middle_name: Optional[str]
    last_name: str
    address: str
    birthday: datetime


class MemberCreate(MemberBase):
    tribe_id: PyObjectId
    life_group_id: Optional[PyObjectId] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class MemberUpdate(BaseModel):
    tribe_id: Optional[PyObjectId] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    birthday: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.now)


class Member(MemberBase):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    tribe_id: PyObjectId
    life_groupt_id : Optional[PyObjectId]
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
