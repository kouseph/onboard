from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    Enum,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
import enum


Base = declarative_base()


class InviteStatus(str, enum.Enum):
    pending = "pending"
    started = "started"
    submitted = "submitted"
    expired = "expired"


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(UUID(as_uuid=True), primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    seed_repo_url = Column(Text, nullable=False)
    start_within_hours = Column(Integer, nullable=False)
    complete_within_hours = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    archived = Column(Boolean, nullable=False, default=False)

    seed_repo = relationship("SeedRepo", back_populates="assessment", uselist=False)
    invites = relationship("AssessmentInvite", back_populates="assessment")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(Text, nullable=False, unique=True)
    full_name = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)

    invites = relationship("AssessmentInvite", back_populates="candidate")


class AssessmentInvite(Base):
    __tablename__ = "assessment_invites"

    id = Column(UUID(as_uuid=True), primary_key=True)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(InviteStatus, name="invite_status"), nullable=False)
    start_deadline_at = Column(DateTime(timezone=True))
    complete_deadline_at = Column(DateTime(timezone=True))
    start_token = Column(Text, unique=True)
    start_url_slug = Column(Text, unique=True)
    started_at = Column(DateTime(timezone=True))
    submitted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False)

    assessment = relationship("Assessment", back_populates="invites")
    candidate = relationship("Candidate", back_populates="invites")
    candidate_repo = relationship(
        "CandidateRepo",
        back_populates="invite",
        uselist=False,
        passive_deletes=True,  # delegate FK cascade deletes to the database
    )
    submission = relationship("Submission", back_populates="invite", uselist=False)


class SeedRepo(Base):
    __tablename__ = "seed_repos"

    id = Column(UUID(as_uuid=True), primary_key=True)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, unique=True)
    default_branch = Column(Text, nullable=False)
    latest_main_sha = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    assessment = relationship("Assessment", back_populates="seed_repo")


class CandidateRepo(Base):
    __tablename__ = "candidate_repos"

    id = Column(UUID(as_uuid=True), primary_key=True)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="CASCADE"), nullable=False, unique=True)
    repo_full_name = Column(Text)
    git_provider = Column(Text, nullable=False)
    pinned_main_sha = Column(Text)
    archived = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    invite = relationship(
        "AssessmentInvite",
        back_populates="candidate_repo",
        passive_deletes=True,  # don't null FK; let DB ON DELETE CASCADE handle it
    )
    access_tokens = relationship(
        "RepoAccessToken",
        back_populates="candidate_repo",
        passive_deletes=True,  # rely on DB cascade; don't null FKs
    )


class RepoAccessToken(Base):
    __tablename__ = "repo_access_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True)
    candidate_repo_id = Column(UUID(as_uuid=True), ForeignKey("candidate_repos.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False)

    candidate_repo = relationship(
        "CandidateRepo",
        back_populates="access_tokens",
        passive_deletes=True,
    )


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(UUID(as_uuid=True), primary_key=True)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="CASCADE"), nullable=False, unique=True)
    final_sha = Column(Text)
    submitted_at = Column(DateTime(timezone=True), nullable=False)

    invite = relationship("AssessmentInvite", back_populates="submission")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="SET NULL"))
    event_type = Column(Text, nullable=False)
    payload = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ReviewComment(Base):
    __tablename__ = "review_comments"
    id = Column(UUID(as_uuid=True), primary_key=True)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="CASCADE"), nullable=False)
    user_type = Column(String, nullable=False)  # "admin" or "candidate"
    author_email = Column(Text, nullable=False)
    author_name = Column(Text)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    invite = relationship("AssessmentInvite", backref="review_comments")


class FollowUpEmail(Base):
    __tablename__ = "followup_emails"
    id = Column(UUID(as_uuid=True), primary_key=True)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="CASCADE"), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)
    template_subject = Column(Text, nullable=False)
    template_body = Column(Text, nullable=False)
    invite = relationship("AssessmentInvite", backref="followup_emails")

class Setting(Base):
    __tablename__ = "settings"
    id = Column(UUID(as_uuid=True), primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)


class ReviewInlineComment(Base):
    __tablename__ = "review_inline_comments"
    id = Column(UUID(as_uuid=True), primary_key=True)
    invite_id = Column(UUID(as_uuid=True), ForeignKey("assessment_invites.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(Text, nullable=False)
    line = Column(Integer)
    message = Column(Text, nullable=False)
    author_email = Column(Text, nullable=False)
    author_name = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False)

    invite = relationship("AssessmentInvite", backref="inline_comments")


