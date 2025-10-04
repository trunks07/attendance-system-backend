from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId
from fastapi import Depends, HTTPException
from motor.core import AgnosticClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config.database import get_db
from app.models.schemas.UserSchema import UserCreate, UserUpdate

IDLike = Union[str, ObjectId]


class UserModel:
    collection_name = "users"

    def __init__(self, db: Any):
        try:
            self.collection = db[self.collection_name]
        except Exception:
            try:
                self.collection = getattr(db, self.collection_name)
            except Exception:
                self.collection = db

    def _convert_objectids_to_str(self, document: Dict[str, Any]) -> Dict[str, Any]:
        for key in ["_id"]:
            if key in document and isinstance(document[key], ObjectId):
                document[key] = str(document[key])
        return document

    async def get_user_list(
        self,
        skip: int = 0,
        limit: int = 10,
        search_term: Optional[str] = None,
        session: Optional[AgnosticClientSession] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query: Dict[str, Any] = {}

        if search_term:
            regex_pattern = {"$regex": f".*{search_term}.*", "$options": "i"}
            query["$or"] = [{"email": regex_pattern, "full_name": regex_pattern}]

        total_count = await self.collection.count_documents(query, session=session)
        users = await (
            self.collection.find(query, session=session, projection={"password": False})
            .skip(skip)
            .limit(limit)
            .to_list(length=limit)
        )

        # `users` is a list of dicts (not None), convert each doc
        converted_users: List[Dict[str, Any]] = [
            self._convert_objectids_to_str(user) for user in users
        ]

        return converted_users, total_count

    async def create(
        self, user_data: UserCreate, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        item_dict: Dict[str, Any] = user_data.model_dump()
        result = await self.collection.insert_one(item_dict, session=session)

        document = await self.collection.find_one(
            {"_id": result.inserted_id}, projection={"password": False}, session=session
        )
        if not document:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created user"
            )

        return self._convert_objectids_to_str(document)

    async def get_by_id(
        self,
        user_id: IDLike,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        if isinstance(user_id, str):
            if not ObjectId.is_valid(user_id):
                raise HTTPException(400, "Invalid ID format")
            user_id = ObjectId(user_id)

        document = await self.collection.find_one(
            {"_id": user_id},
            projection={"password": False},
            session=session,
        )

        return self._convert_objectids_to_str(document) if document else None

    async def get_all(
        self, session: Optional[AgnosticClientSession] = None
    ) -> List[Dict[str, Any]]:
        documents = await self.collection.find({}, session=session).to_list(length=None)
        return [self._convert_objectids_to_str(doc) for doc in documents]

    async def get_by_email(
        self, email: str, session: Optional[AgnosticClientSession] = None
    ) -> Optional[Dict[str, Any]]:
        document = await self.collection.find_one({"email": email}, session=session)
        return self._convert_objectids_to_str(document) if document else None

    async def update_password(
        self,
        user_id: IDLike,
        new_password: str,
        session: Optional[AgnosticClientSession] = None,
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(400, "Invalid ID format")

        obj_id = ObjectId(user_id)
        update_dict: Dict[str, Any] = {
            "password": new_password,
            "updated_at": datetime.now(),
        }

        await self.collection.update_one(
            {"_id": obj_id}, {"$set": update_dict}, session=session
        )

        document = await self.get_by_id(obj_id, session=session)
        if not document:
            raise HTTPException(status_code=404, detail="User not found after update")
        return document

    async def update(
        self,
        user_id: str,
        update_data: UserUpdate,
        session: Optional[AgnosticClientSession] = None,
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(400, "Invalid ID format")

        obj_id = ObjectId(user_id)
        update_dict: Dict[str, Any] = update_data.model_dump(
            exclude_unset=True, exclude_none=True
        )
        update_dict["updated_at"] = datetime.now()

        if not update_dict:
            raise HTTPException(400, "No update data provided")

        await self.collection.update_one(
            {"_id": obj_id}, {"$set": update_dict}, session=session
        )

        document = await self.get_by_id(obj_id, session=session)
        if not document:
            raise HTTPException(status_code=404, detail="User not found after update")
        return document

    async def delete(
        self, user_id: str, session: Optional[AgnosticClientSession] = None
    ) -> bool:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(400, "Invalid ID format")

        obj_id = ObjectId(user_id)
        result = await self.collection.delete_one({"_id": obj_id}, session=session)
        if result.deleted_count == 0:
            raise HTTPException(404, "User not found")
        return True


# Dependency for routes
def get_user_model(db: AsyncIOMotorDatabase = Depends(get_db)):
    return UserModel(db)
