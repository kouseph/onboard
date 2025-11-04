from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import os
import resend

from app.database import get_db
from app import models
from app.schemas import InviteCreate, InviteOut, AdminInviteOut
from app.routes.email import invite_email_html
from app.services.email_service import EmailService


router = APIRouter(prefix="/invites", tags=["invites"])


def _generate_slug() -> str:
    return secrets.token_urlsafe(10).lower()


@router.post("/", response_model=InviteOut)
def create_invite(payload: InviteCreate, db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).get(payload.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    candidate = db.query(models.Candidate).filter(models.Candidate.email == payload.email.lower()).first()
    if not candidate:
        candidate = models.Candidate(
            id=uuid.uuid4(),
            email=payload.email.lower(),
            full_name=payload.full_name,
            created_at=datetime.now(timezone.utc),
        )
        db.add(candidate)

    start_deadline_at = datetime.now(timezone.utc) + timedelta(hours=assessment.start_within_hours)

    invite = models.AssessmentInvite(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        candidate_id=candidate.id,
        status=models.InviteStatus.pending,
        start_deadline_at=start_deadline_at,
        start_url_slug=_generate_slug(),
        created_at=datetime.now(timezone.utc),
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    # Send invite email immediately after creation (best-effort; don't fail invite creation)
    try:
        assessment_title = assessment.title
        candidate = db.query(models.Candidate).get(invite.candidate_id)
        public_base = os.getenv("PUBLIC_APP_BASE_URL", "http://localhost:3000")
        start_link = f"{public_base}/candidate/{invite.start_url_slug}"

        # Configure Resend only if API key is present
        api_key = os.getenv("RESEND_API_KEY")
        from_addr = os.getenv("EMAIL_FROM")
        if api_key and from_addr:
            resend.api_key = api_key
            resend.Emails.send({
                "from": from_addr,
                "to": [candidate.email],
                "subject": f"Assessment Invitation: {assessment_title}",
                "html": invite_email_html(candidate.full_name, assessment_title, start_link),
            })
        else:
            # Missing email configuration; proceed without sending
            print("[invite email] Skipped sending: RESEND_API_KEY or EMAIL_FROM not set")
    except Exception as e:
        # Log and proceed; we don't want email failures to block API
        print(f"[invite email] Failed to send: {e}")

    return invite


@router.get("/", response_model=list[InviteOut])
def list_invites(db: Session = Depends(get_db)):
    rows = db.query(models.AssessmentInvite).order_by(models.AssessmentInvite.created_at.desc()).all()
    return rows


@router.get("/admin", response_model=list[AdminInviteOut])
def list_invites_with_details(db: Session = Depends(get_db)):
    invites = (
        db.query(models.AssessmentInvite)
        .order_by(models.AssessmentInvite.created_at.desc())
        .all()
    )
    results: list[dict] = []
    for inv in invites:
        assessment = db.query(models.Assessment).get(inv.assessment_id)
        candidate = db.query(models.Candidate).get(inv.candidate_id)
        results.append(
            {
                "id": inv.id,
                "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                "created_at": inv.created_at,
                "start_deadline_at": inv.start_deadline_at,
                "complete_deadline_at": inv.complete_deadline_at,
                "started_at": inv.started_at,
                "submitted_at": inv.submitted_at,
                "candidate": candidate,
                "assessment": assessment,
            }
        )
    return results


@router.delete("/{invite_id}")
def cancel_invite(invite_id: str, db: Session = Depends(get_db)):
    """
    Cancel/delete an assignment invite.
    This will cascade delete related records (candidate_repo, tokens, etc.).
    """
    try:
        print('this is good!')
        invite_uuid = uuid.UUID(invite_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid invite ID format")
    
    # Use filter to ensure proper UUID comparison
    invite = db.query(models.AssessmentInvite).filter(models.AssessmentInvite.id == invite_uuid).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    # Optional: prevent deletion of submitted assessments for audit trail
    # Uncomment the following lines if you want to keep submitted assessments:
    # if invite.status == models.InviteStatus.submitted:
    #     raise HTTPException(
    #         status_code=400, 
    #         detail="Cannot cancel a submitted assessment. Contact an administrator if needed."
    #     )
    
    try:
        # Proactively delete dependent rows that maintain NOT NULL FKs to invite
        # even though DB has ON DELETE CASCADE, some ORM paths can attempt to null first.
        cand_repo = (
            db.query(models.CandidateRepo)
            .filter(models.CandidateRepo.invite_id == invite.id)
            .first()
        )
        if cand_repo:
            # Proactively delete tokens referencing the candidate repo to avoid NOT NULL FK updates
            db.query(models.RepoAccessToken).filter(
                models.RepoAccessToken.candidate_repo_id == cand_repo.id
            ).delete(synchronize_session=False)
            db.flush()
            # Now delete the candidate repo
            db.delete(cand_repo)
            db.flush()

        # Submissions reference invite with UNIQUE FK; delete if present
        submission = (
            db.query(models.Submission)
            .filter(models.Submission.invite_id == invite.id)
            .first()
        )
        if submission:
            db.delete(submission)
            db.flush()

        # Clean up comment threads and follow-up emails tied to the invite
        db.query(models.ReviewInlineComment).filter(
            models.ReviewInlineComment.invite_id == invite.id
        ).delete(synchronize_session=False)
        db.query(models.ReviewComment).filter(
            models.ReviewComment.invite_id == invite.id
        ).delete(synchronize_session=False)
        db.query(models.FollowUpEmail).filter(
            models.FollowUpEmail.invite_id == invite.id
        ).delete(synchronize_session=False)
        db.flush()

        # Now delete the invite; remaining dependents will cascade
        db.delete(invite)
        db.commit()
        return {"status": "deleted", "message": "Assignment cancelled successfully"}
    except IntegrityError as e:
        db.rollback()
        # Surface a helpful error; cascades should normally handle dependents
        raise HTTPException(status_code=409, detail=f"Cannot delete invite due to related records: {str(e.orig)}")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error while deleting invite: {str(e)}")

