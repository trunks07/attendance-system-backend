from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, cast
from bson import ObjectId
from fastapi import Depends, HTTPException
from motor.core import AgnosticClientSession
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.results import DeleteResult, UpdateResult
from app.config.database import get_db
from app.models.schemas.AttendanceSchema import AttendanceCreate, AttendanceUpdate
from app.libs.helper import Helper

IDLike = Union[str, ObjectId]


class AttendanceModel:
    collection_name = "attendances"

    def __init__(self, db: Any):
        try:
            self.collection = db[self.collection_name]
        except Exception:
            try:
                self.collection = getattr(db, self.collection_name)
            except Exception:
                self.collection = db

    def _convert_objectids_recursive(self, value: Any) -> Any:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, dict):
            return {k: self._convert_objectids_recursive(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._convert_objectids_recursive(v) for v in value]
        return value

    def _base_query(self, include_deleted: bool = False) -> Dict[str, Any]:
        if include_deleted:
            return {}

        return {"$or": [{"deleted_at": None}, {"deleted_at": {"$exists": False}}]}

    async def get_attendance_list(
        self,
        skip: int = 0,
        limit: int = 10,
        search_term: Optional[str] = None,
        tribe: Optional[str] = None,
        start_datetime: Optional[str] = None,  # accepts typical frontend formats
        end_datetime: Optional[str] = None,    # accepts typical frontend formats
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = self._base_query(include_deleted)

        # Build date/time range match if any
        date_range_spec: Optional[Dict[str, Any]] = None
        if start_datetime or end_datetime:
            try:
                start_dt = Helper.parse_flexible_datetime(start_datetime) if start_datetime else None
                end_dt = Helper.parse_flexible_datetime(end_datetime) if end_datetime else None
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            range_query: Dict[str, Any] = {}
            if start_dt is not None:
                range_query["$gte"] = start_dt
            if end_dt is not None:
                range_query["$lt"] = end_dt

            if not range_query:
                raise HTTPException(status_code=400, detail="Invalid datetime range")

            # Try to match against common date fields in attendance documents
            date_range_spec = {
                "$or": [
                    {"date": range_query},
                    {"attendance_date": range_query},
                    {"created_at": range_query},
                ]
            }

        # Start pipeline with base query and optional date filter (applied early)
        if date_range_spec:
            pipeline = [{"$match": {**query, **date_range_spec}}]
        else:
            pipeline = [{"$match": query}]

        # Lookup member and tribe (unwind member first, then lookup tribe)
        pipeline += [
            {
                "$lookup": {
                    "from": "members",
                    "localField": "member_id",
                    "foreignField": "_id",
                    "as": "member",
                }
            },
            {"$unwind": {"path": "$member", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": "tribes",
                    "localField": "member.tribe_id",
                    "foreignField": "_id",
                    "as": "member.tribe",
                }
            },
            {"$addFields": {"member.tribe": {"$arrayElemAt": ["$member.tribe", 0]}}},
            {"$match": {"member": {"$ne": None}}},
        ]

        # search_term filter (after lookups so we can search member and tribe fields)
        if search_term:
            regex_pattern = {"$regex": f".*{search_term}.*", "$options": "i"}
            pipeline.append(
                {
                    "$match": {
                        "$or": [
                            {"name": regex_pattern},
                            {"description": regex_pattern},
                            {"member.first_name": regex_pattern},
                            {"member.last_name": regex_pattern},
                            {"member.tribe.name": regex_pattern},
                        ]
                    }
                }
            )

        # tribe filter (expects tribe string id)
        if tribe:
            if not ObjectId.is_valid(tribe):
                raise HTTPException(status_code=400, detail="Invalid tribe id format")
            pipeline.append(
                {"$match": {"$or": [{"member.tribe_id": ObjectId(tribe)}, {"member.tribe._id": ObjectId(tribe)}]}}
            )

        # Count total results before pagination
        count_pipeline = pipeline + [{"$count": "total"}]
        count_cursor = self.collection.aggregate(count_pipeline, session=session)
        count_list = await count_cursor.to_list(length=1)
        total_count = count_list[0]["total"] if count_list else 0

        # Add pagination
        pipeline += [{"$skip": skip}, {"$limit": limit}]

        cursor = self.collection.aggregate(pipeline, session=session)
        attendances = await cursor.to_list(length=limit)

        # Recursively convert ObjectId -> str for all results
        converted_attendances = [self._convert_objectids_recursive(t) for t in attendances]

        return converted_attendances, total_count


    async def create(
        self, attendance_data: AttendanceCreate, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        item_dict = cast(Dict[str, Any], attendance_data.model_dump())
        item_dict.setdefault("created_at", datetime.now())
        item_dict.setdefault("updated_at", datetime.now())

        result = await self.collection.insert_one(item_dict, session=session)

        document = await self.collection.find_one(
            {"_id": result.inserted_id}, session=session
        )
        if not document:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created Attendance"
            )

        return self._convert_objectids_recursive(document)

    async def get_by_id(
        self,
        attendance_id: IDLike,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> Optional[Dict[str, Any]]:
        # normalized id variable name for mypy clarity
        attendance_obj_id: ObjectId
        if isinstance(attendance_id, str):
            if not ObjectId.is_valid(attendance_id):
                raise HTTPException(status_code=400, detail="Invalid ID format")
            attendance_obj_id = ObjectId(attendance_id)
        else:
            attendance_obj_id = attendance_id  # type: ignore[assignment]

        query: Dict[str, Any] = {"_id": attendance_obj_id}
        if not include_deleted:
            # only non-deleted documents
            query.update(self._base_query(include_deleted))

        pipeline = [
            {"$match": query},
            {
                "$lookup": {
                    "from": "members",
                    "localField": "member_id",
                    "foreignField": "_id",
                    "as": "member",
                }
            },
            {
                "$unwind": {
                    "path": "$member",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$lookup": {
                    "from": "tribes",
                    "localField": "member.tribe_id",
                    "foreignField": "_id",
                    "as": "member.tribe",
                }
            },
            {
                "$addFields": {
                    "member.tribe": {
                        "$arrayElemAt": [
                            "$member.tribe", 0
                        ]
                    }
                }
            },
            {
                "$match": {
                    "member": {
                        "$ne": None
                    }
                }
            }
        ]


        # document = await self.collection.find_one(query, session=session)
        document = await self.collection.aggregate(pipeline, session=session).next()
        return self._convert_objectids_recursive(document) if document else None

    async def get_all(
        self,
        include_deleted: bool = False,
        session: Optional[AgnosticClientSession] = None,
    ) -> List[Dict[str, Any]]:
        query = self._base_query(include_deleted)
        documents = await self.collection.find(query, session=session).to_list(
            length=None
        )
        return [self._convert_objectids_recursive(doc) for doc in documents]

    async def update(
        self,
        attendance_id: str,
        update_data: AttendanceUpdate,
        session: Optional[AgnosticClientSession] = None,
        allow_update_deleted: bool = False,
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(attendance_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        attendance_obj_id = ObjectId(attendance_id)
        update_dict = update_data.model_dump(exclude_unset=True, exclude_none=True)
        update_dict["updated_at"] = datetime.now()

        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided")

        query: Dict[str, Any] = {"_id": attendance_obj_id}
        if not allow_update_deleted:
            query.update(self._base_query(include_deleted=False))

        update_result: UpdateResult = await self.collection.update_one(
            query, {"$set": update_dict}, session=session
        )  # type: ignore[assignment]

        if update_result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Attendance not found or is deleted")

        document = await self.get_by_id(
            attendance_obj_id, include_deleted=True, session=session
        )
        if not document:
            raise HTTPException(status_code=404, detail="Attendance not found after update")
        return document

    async def delete(
        self,
        attendance_id: str,
        session: Optional[AgnosticClientSession] = None,
        hard_delete: bool = False,
    ) -> bool:
        if not ObjectId.is_valid(attendance_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        attendance_obj_id = ObjectId(attendance_id)

        if hard_delete:
            delete_result: DeleteResult = await self.collection.delete_one(
                {"_id": attendance_obj_id}, session=session
            )  # type: ignore[assignment]
            if delete_result.deleted_count == 0:
                raise HTTPException(status_code=404, detail="Attendance not found")
            return True

        # soft delete -> set deleted_at timestamp
        update_doc = {
            "$set": {"deleted_at": datetime.now(), "updated_at": datetime.now()}
        }
        update_result: UpdateResult = await self.collection.update_one(
            {"_id": attendance_obj_id, **self._base_query(include_deleted=False)},
            update_doc,
            session=session,
        )  # type: ignore[assignment]

        if update_result.matched_count == 0:
            existing = await self.collection.find_one(
                {"_id": attendance_obj_id}, session=session
            )
            if existing:
                # already soft-deleted
                return True
            raise HTTPException(status_code=404, detail="Attendance not found")
        return True

    async def restore(
        self, attendance_id: str, session: Optional[AgnosticClientSession] = None
    ) -> Dict[str, Any]:
        if not ObjectId.is_valid(attendance_id):
            raise HTTPException(status_code=400, detail="Invalid ID format")

        attendance_obj_id = ObjectId(attendance_id)
        update = {"$set": {"deleted_at": None, "updated_at": datetime.now()}}
        update_result: UpdateResult = await self.collection.update_one(
            {"_id": attendance_obj_id, "deleted_at": {"$ne": None}}, update, session=session
        )  # type: ignore[assignment]

        if update_result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail="Attendance not found or not deleted"
            )

        document = await self.get_by_id(
            attendance_obj_id, include_deleted=True, session=session
        )
        if not document:
            raise HTTPException(status_code=404, detail="Attendance not found after restore")
        return document


# Dependency for routes
def get_attendance_model(db: AsyncIOMotorDatabase = Depends(get_db)):
    return AttendanceModel(db)
