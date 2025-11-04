from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.services.github_service import GitHubService


router = APIRouter(prefix="/candidate", tags=["candidate"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_git_clone_info(cand_repo: models.CandidateRepo, invite: models.AssessmentInvite, db: Session) -> dict[str, str]:
    """
    Generate git clone URL with a fresh access token for a candidate repo.
    Creates a new access token and returns the git info (clone_url and branch).
    """
    if not cand_repo or not cand_repo.repo_full_name:
        raise ValueError("Candidate repo or repo_full_name is missing")
    
    now = datetime.now(timezone.utc)
    token_plain = secrets.token_urlsafe(32)
    token_hash = _hash_token(token_plain)
    
    # Use complete_deadline_at if available, otherwise default to 24 hours
    expires_at = invite.complete_deadline_at if invite.complete_deadline_at else now + timedelta(hours=24)
    
    token_row = models.RepoAccessToken(
        id=uuid.uuid4(),
        candidate_repo_id=cand_repo.id,
        token_hash=token_hash,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(token_row)
    db.commit()
    
    clone_url = f"https://github.com/{cand_repo.repo_full_name}.git?token={token_plain}"
    
    return {
        "clone_url": clone_url,
        "branch": "main",
    }


@router.get("/start/{slug}")
def get_start_page(slug: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).filter(models.AssessmentInvite.start_url_slug == slug).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    assessment = db.query(models.Assessment).get(invite.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    response = {
        "assessment": {
            "title": assessment.title,
            "instructions": assessment.instructions,
            "seed_repo_url": assessment.seed_repo_url,
            "branch": "main",
        },
        "invite": {
            "status": invite.status.value if hasattr(invite.status, "value") else str(invite.status),
            "start_deadline_at": invite.start_deadline_at,
            "complete_deadline_at": invite.complete_deadline_at,
            "started_at": invite.started_at,
            "submitted_at": invite.submitted_at,
        },
    }

    # If a candidate repo exists, include git info
    cand_repo = db.query(models.CandidateRepo).filter(models.CandidateRepo.invite_id == invite.id).first()
    if cand_repo:
        try:
            response["git"] = get_git_clone_info(cand_repo, invite, db)
        except Exception as e:
            # Log error but don't fail the request - git info will just be missing
            # In production, you might want to use proper logging here
            print(f"Error generating git clone info: {e}")
            # Optionally, you could still return the repo URL without token
            if cand_repo.repo_full_name:
                response["git"] = {
                    "clone_url": f"https://github.com/{cand_repo.repo_full_name}.git",
                    "branch": "main",
                }

    return response


@router.post("/start/{slug}")
def start_assessment(slug: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).filter(models.AssessmentInvite.start_url_slug == slug).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    now = datetime.now(timezone.utc)
    
    def to_aware_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if invite.status in [models.InviteStatus.started, models.InviteStatus.submitted]:
        raise HTTPException(status_code=400, detail="Assessment already started or submitted")
    start_deadline = to_aware_utc(invite.start_deadline_at)
    if start_deadline and now > start_deadline:
        invite.status = models.InviteStatus.expired
        db.commit()
        raise HTTPException(status_code=400, detail="Start deadline has passed")

    assessment = db.query(models.Assessment).get(invite.assessment_id)
    seed = db.query(models.SeedRepo).filter(models.SeedRepo.assessment_id == assessment.id).first()

    try:
        gh = GitHubService()
        seed_full_name = gh.ensure_seed_repo(assessment.seed_repo_url)
        clone_result = gh.create_candidate_repo_from_seed(seed_full_name)
    except RuntimeError as e:
        # Missing configuration such as GITHUB_TOKEN or GITHUB_TARGET_OWNER
        raise HTTPException(status_code=500, detail=f"GitHub configuration error: {str(e)}")
    except Exception as e:
        # Upstream GitHub failure or unexpected error
        raise HTTPException(status_code=502, detail=f"Failed to provision candidate repo: {str(e)}")

    # persist candidate repo
    cand_repo = models.CandidateRepo(
        id=uuid.uuid4(),
        invite_id=invite.id,
        repo_full_name=clone_result.repo_full_name,
        git_provider="github",
        pinned_main_sha=clone_result.pinned_main_sha,
        archived=False,
        created_at=now,
    )
    db.add(cand_repo)

    # set complete deadline
    invite.status = models.InviteStatus.started
    invite.started_at = now
    invite.complete_deadline_at = now + timedelta(hours=assessment.complete_within_hours)

    # update seed latest SHA if present
    if seed and not seed.latest_main_sha:
        seed.latest_main_sha = clone_result.pinned_main_sha

    db.commit()
    
    # Get git clone info with fresh token (helper function will commit the token separately)
    git_info = get_git_clone_info(cand_repo, invite, db)
    
    return {
        "git": git_info,
        "repo": {
            "full_name": cand_repo.repo_full_name,
            "pinned_main_sha": cand_repo.pinned_main_sha,
        },
        "invite": {
            "status": invite.status.value,
            "complete_deadline_at": invite.complete_deadline_at,
        },
    }


@router.post("/submit/{slug}")
def submit_assessment(slug: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).filter(models.AssessmentInvite.start_url_slug == slug).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status != models.InviteStatus.started:
        raise HTTPException(status_code=400, detail="Assessment is not in progress")

    cand_repo = db.query(models.CandidateRepo).filter(models.CandidateRepo.invite_id == invite.id).first()
    if not cand_repo:
        raise HTTPException(status_code=400, detail="Candidate repo not found")

    now = datetime.utcnow()

    # revoke tokens
    tokens = db.query(models.RepoAccessToken).filter(models.RepoAccessToken.candidate_repo_id == cand_repo.id, models.RepoAccessToken.revoked_at.is_(None)).all()
    for t in tokens:
        t.revoked_at = now

    # snapshot submission
    submission = models.Submission(
        id=uuid.uuid4(),
        invite_id=invite.id,
        final_sha=cand_repo.pinned_main_sha,  # TODO: fetch latest main SHA of candidate repo
        submitted_at=now,
    )
    db.add(submission)

    invite.status = models.InviteStatus.submitted
    invite.submitted_at = now

    db.commit()
    return {"status": "submitted", "final_sha": submission.final_sha}


@router.get("/commits/{slug}")
def get_candidate_commits(slug: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).filter(models.AssessmentInvite.start_url_slug == slug).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    cand_repo = db.query(models.CandidateRepo).filter(models.CandidateRepo.invite_id == invite.id).first()
    if not cand_repo:
        raise HTTPException(status_code=404, detail="Candidate repo not found")
    gh = GitHubService()
    try:
        history = gh.get_commit_history(cand_repo.repo_full_name)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch commits: {str(e)}")
    return history


