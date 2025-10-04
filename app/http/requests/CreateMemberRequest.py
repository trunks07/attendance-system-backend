from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CreateMemberRequest(BaseModel):
    first_name: str
    middle_name: Optional[str]
    last_name: str
    address: str
    birthday: datetime
    tribe_id: str
    lifegroup_id: Optional[str] = None
