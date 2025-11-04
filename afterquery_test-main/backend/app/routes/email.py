from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
import os
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.services.email_service import EmailService


router = APIRouter(prefix="/email", tags=["email"])


def invite_email_html(candidate_name: str | None, assessment_title: str, start_link: str) -> str:
    name = candidate_name or "there"
    return f"""
    <p>Hi {name},</p>
    <p>You have been invited to complete the assessment <strong>{assessment_title}</strong>.</p>
    <p>Please start here: <a href="{start_link}">{start_link}</a></p>
    <p>Good luck!</p>
    """


def followup_email_html(candidate_name: str | None) -> str:
    name = candidate_name or "there"
    return f"""
    <p>Hi {name},</p>
    <p>Thanks for your submission. We'd like to schedule a follow-up interview.</p>
    <p>Please reply with your availability with the following link <\p>
    """
    # <p>Please reply with your availability with the following link <a href="{}">{Availability}</a>.</p>

@router.post("/send-invite/{invite_id}")
def send_invite_email(invite_id: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    assessment = db.query(models.Assessment).get(invite.assessment_id)
    candidate = db.query(models.Candidate).get(invite.candidate_id)
    if not assessment or not candidate:
        raise HTTPException(status_code=400, detail="Invalid invite")

    public_base = os.getenv("PUBLIC_APP_BASE_URL", "http://localhost:3000")
    start_link = f"{public_base}/candidate/{invite.start_url_slug}"

    svc = EmailService()
    svc.send_email(
        to=candidate.email,
        subject=f"Assessment Invitation: {assessment.title}",
        html=invite_email_html(candidate.full_name, assessment.title, start_link),
    )
    return {"status": "sent"}


@router.post("/send-followup/{invite_id}")
def send_followup_email(invite_id: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    candidate = db.query(models.Candidate).get(invite.candidate_id)
    if not candidate:
        raise HTTPException(status_code=400, detail="Invalid invite")

    svc = EmailService()
    svc.send_email(
        to=candidate.email,
        subject="Follow-Up Interview",
        html=followup_email_html(candidate.full_name),
    )
    return {"status": "sent"}


