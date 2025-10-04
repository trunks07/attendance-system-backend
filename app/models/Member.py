from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId
from fastapi import Depends, HTTPException
from motor.core import AgnosticClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import DeleteResult, UpdateResult
from app.config.database import get_db
from app.models.schemas.MemberSchema import MemberCreate, MemberUpdate
from app.models.Tribe import TribeModel

IDLike = Union[str, ObjectId]


class MemberModel:
    collection_name = "members"

    def __init__(self, db: Any):
        try:
            self.collection = db[self.collection_name]
        except Exception:
            try:
                self.collection = getattr(db, self.collection_name)
            except Exception:
                self.collection = db

        self.tribe_model = TribeModel(db)

    def _convert_objectids_to_str(
        self, document: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Normalize ObjectId fields to strings.

        Accept either a single document (dict) or a list of documents and convert
        in-place (returns a new transformed object for lists).
        """
        # If a list of documents, convert each one
        if isinstance(document, list):
            return [self._convert_objectids_to_str(doc) for doc in document]

        # Now `document` is a dict (or behaves like one)
        # Make a shallow copy so we don't unexpectedly mutate caller-owned objects
        doc_copy: Dict[str, Any] = dict(document) if document is not None else {}

        for key in ["_id", "tribe_id", "life_group_id"]:
            if key in doc_copy:
                val = doc_copy[key]
                # convert single ObjectId -> str
                if isinstance(val, ObjectId):
                    doc_copy[key] = str(val)
                # convert lists of ObjectId -> list[str]
                elif isinstance(val, list):
                    doc_copy[key] = [str(v) if isinstance(v, ObjectId) else v for v in val]

        return doc_copy

    def _base_query(self, include_deleted: bool = False) -> Dict[str, Any]:
        if include_deleted:
            return {}
        return {"$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]}

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
        cursor = self.collection.find(
            query, session=session, projection={"password": False}
        )
        members = await cursor.skip(skip).limit(limit).to_list(length=limit)

        converted_members: List[Dict[str, Any]] = [
            self._convert_objectids_to_str(member) for member in members
        ]

        return converted_members, total_count

    async def create(
        self, member_data: MemberCreate, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        item_dict: Dict[str, Any] = member_data.model_dump()

        # ensure deleted_at / timestamps exist
        item_dict.setdefault("created_at", datetime.now())
        item_dict.setdefault("updated_at", datetime.now())

        result = await self.collection.insert_one(item_dict, session=session)

        document = await self.collection.find_one(
            {"_id": result.inserted_id}, projection={"password": False}, session=session
        )
        if not document:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created member"
            )

        return self._convert_objectids_to_str(document)

    async def get_by_id(
    self,
    member_id: IDLike,
    include_deleted: bool = False,
    session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        # normalize id variable name for clarity
        member_obj_id: ObjectId
        if isinstance(member_id, str):
            if not ObjectId.is_valid(member_id):
                raise HTTPException(status_code=400, detail="Invalid ID format")
            member_obj_id = ObjectId(member_id)
        else:
            member_obj_id = member_id  # type: ignore[assignment]

        query: Dict[str, Any] = {"_id": member_obj_id}
        if not include_deleted:
            query.update(self._base_query(include_deleted))

        document = await self.collection.find_one(query, session=session)

        return self._convert_objectids_to_str(document) if document else None

    async def get_member_full_details(
        self,
        member_id: IDLike,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        member = await self.get_by_id(
            member_id, include_deleted=include_deleted, session=session
        )

        if member:
            tribe_id = member.get("tribe_id") if isinstance(member, dict) else None
            member["tribe"] = await self.tribe_model.get_by_id(tribe_id, session=session) if tribe_id else None

        return member

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

    async def get_by_ids(
        self,
        ids: List[IDLike],
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return a list of members matching the provided IDs.
        """
        member_obj_ids: List[ObjectId] = []

        for _id in ids:
            if isinstance(_id, str):
                if not ObjectId.is_valid(_id):
                    raise HTTPException(status_code=400, detail="Invalid ID format")
                member_obj_ids.append(ObjectId(_id))
            elif isinstance(_id, ObjectId):
                member_obj_ids.append(_id)
            else:
                raise HTTPException(status_code=400, detail="Invalid ID type")

        query: Dict[str, Any] = {"_id": {"$in": member_obj_ids}}
        if not include_deleted:
            query.update(self._base_query(include_deleted))

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

        member_obj_id = ObjectId(member_id)
        update_dict: Dict[str, Any] = update_data.model_dump(
            exclude_unset=True, exclude_none=True
        )

        # Always set updated_at to now (overrides if provided)
        update_dict["updated_at"] = datetime.now()

        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided")

        query: Dict[str, Any] = {"_id": member_obj_id}
        if not allow_update_deleted:
            query.update(self._base_query(include_deleted=False))

        update_result: UpdateResult = await self.collection.update_one(
            query, {"$set": update_dict}, session=session
        )  # type: ignore[assignment]

        if update_result.matched_count == 0:
            # either not found or is deleted (if allow_update_deleted=False)
            raise HTTPException(
                status_code=404, detail="Member not found or is deleted"
            )

        document = await self.get_by_id(
            member_obj_id, include_deleted=True, session=session
        )
        if not document:
            raise HTTPException(status_code=404, detail="Member not found after update")
        return document

    async def delete(
        self,
        member_id: str,
        session: Optional[AgnosticClientSession] = None,
        hard_delete: bool = False,
    ) -> bool:
        if not ObjectId.is_valid(member_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        member_obj_id = ObjectId(member_id)

        if hard_delete:
            delete_result: DeleteResult = await self.collection.delete_one(
                {"_id": member_obj_id}, session=session
            )

            if delete_result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Member not found")
            return True

        update_doc = {
            "$set": {"deleted_at": datetime.now(), "updated_at": datetime.now()}
        }

        update_result: UpdateResult = await self.collection.update_one(
            {"_id": member_obj_id, **self._base_query(include_deleted=False)},
            update_doc,
            session=session,
        )

        if update_result.matched_count == 0:
            existing = await self.collection.find_one(
                {"_id": member_obj_id}, session=session
            )
            if existing:
                # already soft-deleted
                return True
            raise HTTPException(status_code=404, detail="Member not found")
        return True

    async def restore(
        self, member_id: str, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        """
        Restore a soft-deleted member (clear deleted_at).
        """
        if not ObjectId.is_valid(member_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")
        member_obj_id = ObjectId(member_id)

        update = {"$set": {"deleted_at": None, "updated_at": datetime.now()}}
        update_result: UpdateResult = await self.collection.update_one(
            {"_id": member_obj_id, "deleted_at": {"$ne": None}}, update, session=session
        )  # type: ignore[assignment]
        if update_result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Member not found or not deleted"
            )

        document = await self.get_by_id(
            member_obj_id, include_deleted=True, session=session
        )
        if not document:
            raise HTTPException(
                status_code=404, detail="Member not found after restore"
            )
        return document


# Dependency for routes
def get_member_model(db: AsyncIOMotorDatabase = Depends(get_db)):
    return MemberModel(db)
