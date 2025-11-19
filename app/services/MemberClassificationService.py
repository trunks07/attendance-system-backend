from app.models.Member import MemberModel
from app.models.Attendance import AttendanceModel
from app.models.schemas.AttendanceSchema import AttendanceTypes
from app.models.schemas.MemberSchema import Classifications, Member, MemberUpdate
from app.config.database import get_db
from app.libs.helper import Helper

class MemberClassificationService:
    def __init__(self):
        pass


    async def checkMemberClassification(self, member_id: str, type: AttendanceTypes):
        db = await get_db()
        member = await MemberModel(db).get_by_id(member_id)
        classification = await self.processClassification(member, type)

        if not member.get('classification') or member['classification'] != classification:
            await MemberModel(db).update(member_id=member_id, update_data=MemberUpdate(**{'classification': classification}))

        return True

    async def processClassification(self, member: Member, type: AttendanceTypes):
        db = await get_db()
        weeks_required = 4

        start_date = Helper.get_start_date_of_week(weeks_required)
        end_date = Helper.get_date_today()

        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()

        attendances = await AttendanceModel(db).get_member_attendances(
            start_datetime=start_date_str,
            end_datetime=end_date_str,
            member_id=member['_id']
        )

        lg_count = 0
        ws_count = 0
        for attendance in attendances:
            if attendance['type'] == AttendanceTypes.LG:
                lg_count += 1
            else:
                ws_count += 1

        if lg_count >= weeks_required and ws_count >= weeks_required:
            return Classifications.WSAMLGAM 
        elif lg_count >= weeks_required:
            return Classifications.LGAM
        elif ws_count >= weeks_required:
            return Classifications.WSAM
        elif ws_count == 0 and lg_count == 0:
            return Classifications.INACTIVE
        else:
            return Classifications(member['classification']) if member.get('classification') else self.classify(type)

    def classify(self, type: AttendanceTypes):
        return Classifications.LGAM if type == AttendanceTypes.LG else Classifications.WSAM