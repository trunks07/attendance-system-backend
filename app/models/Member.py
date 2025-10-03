from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId
from fastapi import Depends, HTTPException
from motor.core import AgnosticClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.config.database import get_db
from app.models.schemas.MemberSchema import MemberCreate, MemberUpdate
from app.models.Tribe import TribeModel

IDLike = Union[str, ObjectId]


class MemberModel:
    collection_name = "members"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db[self.collection_name]
        self.tribe_model = TribeModel(db)

    def _convert_objectids_to_str(self, document: Dict[str, Any]) -> Dict[str, Any]:
        # defensive copy not required here but could be used if mutation is concerning
        for key in ["_id", "tribe_id", "life_group_id"]:
            if key in document and isinstance(document[key], ObjectId):
                document[key] = str(document[key])
        return document

    def _base_query(self, include_deleted: bool = False) -> Dict[str, Any]:
        # default to excluding soft deleted docs
        return {} if include_deleted else {"deleted": {"$ne": True}}

    async def get_member_list(
        self,
        skip: int = 0,
        limit: int = 10,
        search_term: Optional[str] = None,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query: Dict[str, Any] = self._base_query(include_deleted)

        if search_term:
            regex_pattern = {"$regex": f".*{search_term}.*", "$options": "i"}
            query["$or"] = [
                {"first_name": regex_pattern},
                {"middle_name": regex_pattern},
                {"last_name": regex_pattern},
                {"address": regex_pattern},
            ]

        total_count = await self.collection.count_documents(query, session=session)
        cursor = self.collection.find(query, session=session, projection={"password": False})
        members = await cursor.skip(skip).limit(limit).to_list(length=limit)

        converted_members: List[Dict[str, Any]] = [
            self._convert_objectids_to_str(member) for member in members
        ]

        return converted_members, total_count

    async def create(
        self, member_data: MemberCreate, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        item_dict: Dict[str, Any] = member_data.model_dump()

        # ensure soft-delete fields are set on create
        item_dict.setdefault("deleted", False)
        item_dict.setdefault("deleted_at", None)

        result = await self.collection.insert_one(item_dict, session=session)

        document = await self.collection.find_one(
            {"_id": result.inserted_id}, projection={"password": False}, session=session
        )
        if not document:
            raise HTTPException(status_code=500, detail="Failed to retrieve created member")

        return self._convert_objectids_to_str(document)

    async def get_by_id(
        self,
        member_id: IDLike,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        if isinstance(member_id, str):
            if not ObjectId.is_valid(member_id):
                raise HTTPException(status_code=400, detail="Invalid ID format")
            member_id = ObjectId(member_id)

        query = {"_id": member_id}
        if not include_deleted:
            query["deleted"] = {"$ne": True}

        document = await self.collection.find_one(
            query, projection={"password": False}, session=session
        )

        return self._convert_objectids_to_str(document) if document else None

    async def get_member_full_details(
        self,
        member_id: IDLike,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        if isinstance(member_id, str):
            if not ObjectId.is_valid(member_id):
                raise HTTPException(status_code=400, detail="Invalid ID format")
            member_id = ObjectId(member_id)

        query = {"_id": member_id}
        if not include_deleted:
            query["deleted"] = {"$ne": True}

        document = await self.collection.find_one(
            query, projection={"password": False}, session=session
        )

        if document:
            document["tribe"] = await self.tribe_model.get_by_id(
                document["tribe_id"], include_deleted=True, session=session
            )

        return self._convert_objectids_to_str(document) if document else None

    async def get_all(
        self, include_deleted: bool = False, session: Optional[AgnosticClientSession] = None
    ) -> List[Dict[str, Any]]:
        query = self._base_query(include_deleted)
        documents = await self.collection.find(query, session=session).to_list(length=None)
        return [self._convert_objectids_to_str(doc) for doc in documents]

    async def update(
        self,
        member_id: str,
        update_data: MemberUpdate,
        session: Optional[AgnosticClientSession] = None,
        allow_update_deleted: bool = False,
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(member_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        obj_id = ObjectId(member_id)
        update_dict: Dict[str, Any] = update_data.model_dump(
            exclude_unset=True, exclude_none=True
        )

        # Always set updated_at to now (overrides if provided)
        update_dict["updated_at"] = datetime.now()

        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided")

        query = {"_id": obj_id}
        if not allow_update_deleted:
            query["deleted"] = {"$ne": True}

        result = await self.collection.update_one(query, {"$set": update_dict}, session=session)

        if result.matched_count == 0:
            # either not found or is deleted (if allow_update_deleted=False)
            raise HTTPException(status_code=404, detail="Member not found or is deleted")

        document = await self.get_by_id(obj_id, include_deleted=True, session=session)
        if not document:
            raise HTTPException(status_code=404, detail="Member not found after update")
        return document

    async def delete(
        self,
        member_id: str,
        session: Optional[AgnosticClientSession] = None,
        hard_delete: bool = False,
    ) -> bool:
        """
        Soft-delete by default (set `deleted=True` and `deleted_at`).
        If hard_delete=True, actually removes the document.
        """
        if not ObjectId.is_valid(member_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        obj_id = ObjectId(member_id)

        if hard_delete:
            result = await self.collection.delete_one({"_id": obj_id}, session=session)
            if result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Member not found")
            return True

        # soft delete
        update = {"$set": {"deleted": True, "deleted_at": datetime.now(), "updated_at": datetime.now()}}
        result = await self.collection.update_one({"_id": obj_id, "deleted": {"$ne": True}}, update, session=session)

        if result.matched_count == 0:
            # either not found or already deleted
            # decide whether to return True or raise; raising for clarity
            existing = await self.collection.find_one({"_id": obj_id}, session=session)
            if existing:
                # already deleted
                return True
            raise HTTPException(status_code=404, detail="Member not found")
        return True

    async def restore(
        self, member_id: str, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        """
        Restore a soft-deleted member (set deleted=False and clear deleted_at).
        """
        if not ObjectId.is_valid(member_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")
        obj_id = ObjectId(member_id)

        update = {"$set": {"deleted": False, "deleted_at": None, "updated_at": datetime.now()}}
        result = await self.collection.update_one({"_id": obj_id, "deleted": True}, update, session=session)
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Member not found or not deleted")

        document = await self.get_by_id(obj_id, include_deleted=True, session=session)
        if not document:
            raise HTTPException(status_code=404, detail="Member not found after restore")
        return document


# Dependency for routes
def get_member_model(db: AsyncIOMotorDatabase = Depends(get_db)):
    return MemberModel(db)
