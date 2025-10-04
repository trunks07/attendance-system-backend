from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId
from fastapi import Depends, HTTPException
from motor.core import AgnosticClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import DeleteResult, UpdateResult
from app.config.database import get_db
from app.models.Member import MemberModel
from app.models.schemas.LifegroupSchema import LifegroupCreate, LifegroupUpdate
from app.models.Tribe import TribeModel

IDLike = Union[str, ObjectId]


class LifegroupModel:
    collection_name = "lifregroups"

    def __init__(self, db: Any):
        try:
            self.collection = db[self.collection_name]
        except Exception:
            try:
                self.collection = getattr(db, self.collection_name)
            except Exception:
                self.collection = db

        self.member_model = MemberModel(db)
        self.tribe_model = TribeModel(db)

    def _convert_objectids_to_str(self, document: Dict[str, Any]) -> Dict[str, Any]:
        for key in ["_id", "tribe_id", "leader_id", "members"]:
            if document:
                if key in document and isinstance(document[key], ObjectId):
                    document[key] = str(document[key])

                if key in document and isinstance(document[key], list):
                    document[key] = [str(t) for t in document[key]]
        return document

    def _base_query(self, include_deleted: bool = False) -> Dict[str, Any]:
        if include_deleted:
            return {}

        return {"$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]}

    async def get_lifegroup_list(
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
        lifegroups = await cursor.skip(skip).limit(limit).to_list(length=limit)

        converted_lifegroups = [self._convert_objectids_to_str(t) for t in lifegroups]
        return converted_lifegroups, total_count

    async def create(
        self,
        lifegroup_data: LifegroupCreate,
        session: Optional[AgnosticClientSession] = None,
    ) -> Dict[str, Any]:
        item_dict = lifegroup_data.model_dump()
        item_dict.setdefault("created_at", datetime.now())
        item_dict.setdefault("updated_at", datetime.now())

        result = await self.collection.insert_one(item_dict, session=session)

        document = await self.collection.find_one(
            {"_id": result.inserted_id}, session=session
        )
        if not document:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created lifegroup"
            )

        return self._convert_objectids_to_str(document)

    async def get_by_id(
        self,
        lifegroup_id: IDLike,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        # normalized id variable name for mypy clarity
        lifegroup_obj_id: ObjectId
        if isinstance(lifegroup_id, str):
            if not ObjectId.is_valid(lifegroup_id):
                raise HTTPException(status_code=400, detail="Invalid ID format")
            lifegroup_obj_id = ObjectId(lifegroup_id)
        else:
            lifegroup_obj_id = lifegroup_id  # type: ignore[assignment]

        query: Dict[str, Any] = {"_id": lifegroup_obj_id}
        if not include_deleted:
            # only non-deleted documents
            query.update(self._base_query(include_deleted))

        document = await self.collection.find_one(query, session=session)
        return self._convert_objectids_to_str(document) if document else None

    async def get_full_details(
        self,
        lifegroup_id: IDLike,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        document = await self.get_by_id(lifegroup_id, include_deleted, session=session)

        if document:
            document["leader"] = await self.member_model.get_by_id(
                document["leader_id"], session=session
            )

            document["tribe"] = await self.tribe_model.get_by_id(
                document["tribe_id"], session=session
            )

            if len(document["members"]) > 0:
                document["members"] = await self.member_model.get_by_ids(
                    ids=document["members"], session=session
                )

        return document

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

    async def get_lifegroup_by_member_id(
        self,
        member_id: str,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> List[Dict[str, Any]]:
        if not ObjectId.is_valid(member_id):
            raise HTTPException(status_code=400, detail="Invalid member ID format")

        member_obj_id = ObjectId(member_id)

        query: Dict[str, Any] = {"members": member_obj_id}
        if not include_deleted:
            # only non-deleted documents
            query.update(self._base_query(include_deleted))

        document = await self.collection.find_one(query, session=session)

        return self._convert_objectids_to_str(document) if document else None

    async def update(
        self,
        lifegroup_id: str,
        update_data: LifegroupUpdate,
        session: Optional[AgnosticClientSession] = None,
        allow_update_deleted: bool = False,
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(lifegroup_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        lifegroup_obj_id = ObjectId(lifegroup_id)
        update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict["updated_at"] = datetime.now()

        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided")

        query: Dict[str, Any] = {"_id": lifegroup_obj_id}
        if not allow_update_deleted:
            query.update(self._base_query(include_deleted=False))

        update_result: UpdateResult = await self.collection.update_one(
            query, {"$set": update_dict}, session=session
        )  # type: ignore[assignment]

        if update_result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Lifegroup not found or is deleted"
            )

        document = await self.get_by_id(
            lifegroup_obj_id, include_deleted=True, session=session
        )
        if not document:
            raise HTTPException(
                status_code=404, detail="Lifegroup not found after update"
            )
        return document

    async def delete(
        self,
        lifegroup_id: str,
        session: Optional[AgnosticClientSession] = None,
        hard_delete: bool = False,
    ) -> bool:
        if not ObjectId.is_valid(lifegroup_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        lifegroup_obj_id = ObjectId(lifegroup_id)

        if hard_delete:
            delete_result: DeleteResult = await self.collection.delete_one(
                {"_id": lifegroup_obj_id}, session=session
            )  # type: ignore[assignment]
            if delete_result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Lifegroup not found")
            return True

        # soft delete -> set deleted_at timestamp
        update_doc = {
            "$set": {"deleted_at": datetime.now(), "updated_at": datetime.now()}
        }
        update_result: UpdateResult = await self.collection.update_one(
            {"_id": lifegroup_obj_id, **self._base_query(include_deleted=False)},
            update_doc,
            session=session,
        )  # type: ignore[assignment]

        if update_result.matched_count == 0:
            existing = await self.collection.find_one(
                {"_id": lifegroup_obj_id}, session=session
            )
            if existing:
                # already soft-deleted
                return True
            raise HTTPException(status_code=404, detail="Lifegroup not found")
        return True

    async def restore(
        self, lifegroup_id: str, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(lifegroup_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        lifegroup_obj_id = ObjectId(lifegroup_id)
        update = {"$set": {"deleted_at": None, "updated_at": datetime.now()}}
        update_result: UpdateResult = await self.collection.update_one(
            {"_id": lifegroup_obj_id, "deleted_at": {"$ne": None}},
            update,
            session=session,
        )  # type: ignore[assignment]

        if update_result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Lifegroup not found or not deleted"
            )

        document = await self.get_by_id(
            lifegroup_obj_id, include_deleted=True, session=session
        )
        if not document:
            raise HTTPException(
                status_code=404, detail="Lifegroup not found after restore"
            )
        return document


# Dependency for routes
def get_lifegroup_model(db: AsyncIOMotorDatabase = Depends(get_db)):
    return LifegroupModel(db)
