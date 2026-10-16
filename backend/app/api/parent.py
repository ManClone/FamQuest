from fastapi import APIRouter
from pydantic import BaseModel

from app.auth import DbSession, ParentSession, get_family, me_response
from app.demo_mode import NotInDemo
from app.schemas import FamilyName, LanguageCode, MeResponse, Timezone

router = APIRouter(prefix="/parent", tags=["parent"])


class FamilySettings(BaseModel):
    name: FamilyName
    default_language: LanguageCode
    timezone: Timezone


@router.put("/family", dependencies=[NotInDemo])
def update_family(body: FamilySettings, auth_session: ParentSession, db: DbSession) -> MeResponse:
    family = get_family(db)
    family.name, family.default_language = body.name, body.default_language
    family.timezone = body.timezone
    db.commit()
    return me_response(db, auth_session)
