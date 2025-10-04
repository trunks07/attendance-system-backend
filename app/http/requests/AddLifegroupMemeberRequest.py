from pydantic import BaseModel
from  app.models.schemas.LifegroupSchema import PyObjectId


class LifregroupMemberRequest(BaseModel):
    members: list[PyObjectId]
