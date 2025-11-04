from __future__ import annotations

from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, exists

from app.database import get_db
from app import models
from app.schemas import AssessmentCreate, AssessmentOut, AssessmentUpdate


router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("/", response_model=AssessmentOut)
def create_assessment(payload: AssessmentCreate, db: Session = Depends(get_db)):
    assessment = models.Assessment(
        id=uuid.uuid4(),
        title=payload.title,
        description=payload.description,
        instructions=payload.instructions,
        seed_repo_url=str(payload.seed_repo_url),
        start_within_hours=payload.start_within_hours,
        complete_within_hours=payload.complete_within_hours,
        created_at=datetime.utcnow(),
        archived=False,
    )
    db.add(assessment)
    # ensure seed repo row exists with default branch main
    seed_repo = models.SeedRepo(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        default_branch="main",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(seed_repo)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.get("/{assessment_id}", response_model=AssessmentOut)
def get_assessment(assessment_id: str, db: Session = Depends(get_db)):
    row = db.query(models.Assessment).get(assessment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return row


@router.get("/", response_model=list[AssessmentOut])
def list_assessments(
    status: str | None = Query(None, description="available | archived | undefined for all"),
    db: Session = Depends(get_db),
):
    """
    Challenges listing:
    - available: assessments.archived = false
    - archived: assessments.archived = true
    - undefined/any other: return all
    """
    base_query = db.query(models.Assessment)

    if status == "available":
        return (
            base_query.filter(models.Assessment.archived.is_(False))
            .order_by(models.Assessment.created_at.desc())
            .all()
        )
    if status == "archived":
        return (
            base_query.filter(models.Assessment.archived.is_(True))
            .order_by(models.Assessment.created_at.desc())
            .all()
        )

    return base_query.order_by(models.Assessment.created_at.desc()).all()


@router.put("/{assessment_id}/archive", response_model=AssessmentOut)
def archive_assessment(assessment_id: str, db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).get(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    assessment.archived = True
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@router.put("/{assessment_id}/unarchive", response_model=AssessmentOut)
def unarchive_assessment(assessment_id: str, db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).get(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    assessment.archived = False
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


# Update assessment (e.g., edit repository URL or other fields)
@router.put("/{assessment_id}", response_model=AssessmentOut)
def update_assessment(assessment_id: str, payload: AssessmentUpdate, db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).get(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Update provided fields only
    if payload.title is not None:
        assessment.title = payload.title
    if payload.description is not None:
        assessment.description = payload.description
    if payload.instructions is not None:
        assessment.instructions = payload.instructions
    if payload.seed_repo_url is not None:
        assessment.seed_repo_url = str(payload.seed_repo_url)
    if payload.start_within_hours is not None:
        assessment.start_within_hours = payload.start_within_hours
    if payload.complete_within_hours is not None:
        assessment.complete_within_hours = payload.complete_within_hours

    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


# Delete assessment (cascades via FKs)
@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: str, db: Session = Depends(get_db)):
    assessment = db.query(models.Assessment).get(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Rely on database-level ON DELETE CASCADE constraints defined in schema.sql.
    # Deleting the assessment will cascade to invites, seed repos, candidate repos,
    # access tokens, submissions, comments, and inline comments.
    try:
        db.delete(assessment)
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete assessment: {str(e)}")

