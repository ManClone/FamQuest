from fastapi import APIRouter, status
from pydantic import BaseModel

from app.auth import (
    CurrentSession,
    DbSession,
    ParentSession,
    get_family,
    me_response,
    unlock_parent_area,
)
from app.demo_mode import NotInDemo
from app.errors import ApiError
from app.logs import logger
from app.schemas import FamilyName, LanguageCode, MeResponse, Pin, Timezone
from app.security import hash_secret, login_limiter, pin_limiter, verify_secret

router = APIRouter(prefix="/parent", tags=["parent"])


class UnlockRequest(BaseModel):
    pin: str


class PinRequest(BaseModel):
    pin: Pin


class FamilySettings(BaseModel):
    name: FamilyName
    default_language: LanguageCode
    timezone: Timezone


class PinResetRequest(BaseModel):
    password: str
    pin: Pin


