from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UpdateMemberRequest(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    birthday: Optional[datetime] = None
    tribe_id: Optional[str] = None
    lifegroup_id: Optional[str] = None
