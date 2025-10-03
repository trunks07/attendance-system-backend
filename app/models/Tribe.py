from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId
from fastapi import Depends, HTTPException
from motor.core import AgnosticClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config.database import get_db
from app.models.schemas.TribeSchema import TribeCreate, TribeUpdate

IDLike = Union[str, ObjectId]


class TribeModel:
    collection_name = "tribes"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db[self.collection_name]

    def _convert_objectids_to_str(self, document: Dict[str, Any]) -> Dict[str, Any]:
        if "_id" in document and isinstance(document["_id"], ObjectId):
            document["_id"] = str(document["_id"])
        return document

    def _base_query(self, include_deleted: bool = False) -> Dict[str, Any]:
        return {} if include_deleted else {"deleted": {"$ne": True}}

    async def get_tribe_list(
        self,
        skip: int = 0,
        limit: int = 10,
        search_term: Optional[str] = None,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = self._base_query(include_deleted)

        if search_term:
            regex_pattern = {"$regex": f".*{search_term}.*", "$options": "i"}
            query["$or"] = [{"name": regex_pattern}, {"description": regex_pattern}]

        total_count = await self.collection.count_documents(query, session=session)
        cursor = self.collection.find(query, session=session)
        tribes = await cursor.skip(skip).limit(limit).to_list(length=limit)

        converted_tribes = [self._convert_objectids_to_str(t) for t in tribes]
        return converted_tribes, total_count

    async def create(
        self, tribe_data: TribeCreate, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        item_dict = tribe_data.model_dump()
        item_dict.setdefault("deleted", False)
        item_dict.setdefault("deleted_at", None)

        result = await self.collection.insert_one(item_dict, session=session)

        document = await self.collection.find_one(
            {"_id": result.inserted_id}, session=session
        )
        if not document:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created tribe"
            )

        return self._convert_objectids_to_str(document)

    async def get_by_id(
        self,
        tribe_id: IDLike,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        if isinstance(tribe_id, str):
            if not ObjectId.is_valid(tribe_id):
                raise HTTPException(status_code=400, detail="Invalid ID format")
            tribe_id = ObjectId(tribe_id)

        query = {"_id": tribe_id}
        if not include_deleted:
            query["deleted"] = {"$ne": True}

        document = await self.collection.find_one(query, session=session)
        return self._convert_objectids_to_str(document) if document else None

    async def get_all(
        self,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> List[Dict[str, Any]]:
        query = self._base_query(include_deleted)
        documents = await self.collection.find(query, session=session).to_list(
            length=None
        )
        return [self._convert_objectids_to_str(doc) for doc in documents]

    async def update(
        self,
        tribe_id: str,
        update_data: TribeUpdate,
        session: Optional[AgnosticClientSession] = None,
        allow_update_deleted: bool = False,
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(tribe_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        obj_id = ObjectId(tribe_id)
        update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict["updated_at"] = datetime.now()

        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided")

        query = {"_id": obj_id}
        if not allow_update_deleted:
            query["deleted"] = {"$ne": True}

        result = await self.collection.update_one(
            query, {"$set": update_dict}, session=session
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Tribe not found or is deleted")

        document = await self.get_by_id(obj_id, include_deleted=True, session=session)
        if not document:
            raise HTTPException(status_code=404, detail="Tribe not found after update")
        return document

    async def delete(
        self,
        tribe_id: str,
        session: Optional[AgnosticClientSession] = None,
        hard_delete: bool = False,
    ) -> bool:
        if not ObjectId.is_valid(tribe_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        obj_id = ObjectId(tribe_id)

        if hard_delete:
            result = await self.collection.delete_one({"_id": obj_id}, session=session)
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Tribe not found")
            return True

        # soft delete
        update = {
            "$set": {
                "deleted": True,
                "deleted_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        }
        result = await self.collection.update_one(
            {"_id": obj_id, "deleted": {"$ne": True}}, update, session=session
        )
        if result.matched_count == 0:
            existing = await self.collection.find_one({"_id": obj_id}, session=session)
            if existing:
                return True
            raise HTTPException(status_code=404, detail="Tribe not found")
        return True

    async def restore(
        self, tribe_id: str, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(tribe_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        obj_id = ObjectId(tribe_id)
        update = {
            "$set": {"deleted": False, "deleted_at": None, "updated_at": datetime.now()}
        }
        result = await self.collection.update_one(
            {"_id": obj_id, "deleted": True}, update, session=session
        )
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Tribe not found or not deleted"
            )

        document = await self.get_by_id(obj_id, include_deleted=True, session=session)
        if not document:
            raise HTTPException(status_code=404, detail="Tribe not found after restore")
        return document


# Dependency for routes
def get_tribe_model(db: AsyncIOMotorDatabase = Depends(get_db)):
    return TribeModel(db)
