from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, HttpUrl, EmailStr


class AssessmentCreate(BaseModel):
    title: str
    description: str | None = None
    instructions: str | None = None
    seed_repo_url: HttpUrl
    start_within_hours: int
    complete_within_hours: int


class AssessmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    instructions: str | None = None
    seed_repo_url: HttpUrl | None = None
    start_within_hours: int | None = None
    complete_within_hours: int | None = None


class AssessmentOut(BaseModel):
    id: UUID
    title: str
    description: str | None
    instructions: str | None
    seed_repo_url: str
    start_within_hours: int
    complete_within_hours: int
    created_at: datetime

    class Config:
        from_attributes = True


class InviteCreate(BaseModel):
    assessment_id: str
    email: EmailStr
    full_name: str | None = None


class InviteOut(BaseModel):
    id: UUID
    assessment_id: UUID
    candidate_id: UUID
    status: str
    start_deadline_at: datetime | None
    complete_deadline_at: datetime | None
    start_url_slug: str | None
    started_at: datetime | None
    submitted_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True



class CandidateLite(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None

    class Config:
        from_attributes = True


class AssessmentLite(BaseModel):
    id: UUID
    title: str
    seed_repo_url: str

    class Config:
        from_attributes = True


class AdminInviteOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    start_deadline_at: datetime | None
    complete_deadline_at: datetime | None
    started_at: datetime | None
    submitted_at: datetime | None
    candidate: CandidateLite
    assessment: AssessmentLite

    class Config:
        from_attributes = True


class ReviewCommentOut(BaseModel):
    id: UUID
    invite_id: UUID
    user_type: str  # "admin" or "candidate"
    author_email: str
    author_name: str | None
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class FollowUpEmailOut(BaseModel):
    id: UUID
    invite_id: UUID
    sent_at: datetime
    template_subject: str
    template_body: str

    class Config:
        from_attributes = True

class SettingOut(BaseModel):
    id: UUID
    key: str
    value: str

    class Config:
        from_attributes = True


class DiffFile(BaseModel):
    filename: str
    additions: int
    deletions: int
    changes: int
    status: str
    patch: str | None = None

class InlineCommentOut(BaseModel):
    id: UUID
    invite_id: UUID
    file_path: str
    line: int | None
    message: str
    author_email: str
    author_name: str | None
    created_at: datetime

    class Config:
        from_attributes = True

