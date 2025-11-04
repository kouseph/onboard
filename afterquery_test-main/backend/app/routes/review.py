from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import html
import re

from app.database import get_db
from app import models
from app.services.github_service import GitHubService
from app.schemas import ReviewCommentOut, FollowUpEmailOut, SettingOut, DiffFile, InlineCommentOut
from app.services.email_service import EmailService
from uuid import uuid4, UUID
from datetime import datetime, timezone
from app.models import FollowUpEmail, Setting
import json


router = APIRouter(prefix="/review", tags=["review"])


@router.get("/invite/{invite_id}")
def get_review_for_invite(invite_id: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    assessment = db.query(models.Assessment).get(invite.assessment_id)
    candidate = db.query(models.Candidate).get(invite.candidate_id)
    candidate_repo = db.query(models.CandidateRepo).filter(models.CandidateRepo.invite_id == invite.id).first()
    submission = db.query(models.Submission).filter(models.Submission.invite_id == invite.id).first()

    commits = []
    if candidate_repo:
        try:
            gh = GitHubService()
            commits = gh.get_commit_history(candidate_repo.repo_full_name)
        except Exception as e:
            commits = []  # Or put [{'message': f'Error: {e}', ...}] for debug

    diff_summary = {
        "against": {
            "seed_repo": assessment.seed_repo_url,
            "branch": "main",
        },
        "files_changed": [],
    }

    return {
        "invite": {
            "id": str(invite.id),
            "status": invite.status.value if hasattr(invite.status, "value") else str(invite.status),
            "started_at": invite.started_at,
            "submitted_at": invite.submitted_at,
        },
        "assessment": {
            "id": str(assessment.id),
            "title": assessment.title,
            "seed_repo_url": assessment.seed_repo_url,
        },
        "candidate": {
            "id": str(candidate.id),
            "email": candidate.email,
            "full_name": candidate.full_name,
        },
        "repo": candidate_repo and {
            "full_name": candidate_repo.repo_full_name,
            "pinned_main_sha": candidate_repo.pinned_main_sha,
            "archived": candidate_repo.archived,
        },
        "submission": submission and {
            "final_sha": submission.final_sha,
            "submitted_at": submission.submitted_at,
        },
        "commits": commits,
        "diff": diff_summary,
    }


@router.get("/comments/{invite_id}", response_model=list[ReviewCommentOut])
def get_review_comments(invite_id: str, db: Session = Depends(get_db)):
    rows = db.query(models.ReviewComment).filter(models.ReviewComment.invite_id == invite_id).order_by(models.ReviewComment.created_at).all()
    return rows

@router.post("/comments/{invite_id}", response_model=ReviewCommentOut)
def add_review_comment(invite_id: str, payload: dict, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    comment = models.ReviewComment(
        id=uuid4(),
        invite_id=invite_id,
        user_type=payload["user_type"],
        author_email=payload["author_email"],
        author_name=payload.get("author_name"),
        message=payload["message"],
        created_at=datetime.now(timezone.utc),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Send notification email
    email_svc = EmailService()
    assessment = db.query(models.Assessment).get(invite.assessment_id)
    candidate = db.query(models.Candidate).get(invite.candidate_id)
    if payload["user_type"] == "admin":
        # Notify candidate
        target_email = candidate.email
        name = candidate.full_name
        email_svc.send_email(
            to=target_email,
            subject=f"Admin replied to your project: {assessment.title}",
            html=f"<p>You have a new message from the admin regarding your assessment <strong>{assessment.title}</strong>.</p><blockquote>{payload['message']}</blockquote>",
        )
    else:
        # Notify admin (can use a static/admin email for now)
        admin_email = "admin@yourdomain.com"  # Replace with real admin email or config
        email_svc.send_email(
            to=admin_email,
            subject=f"Candidate replied: {assessment.title}",
            html=f"<p>{payload.get('author_name') or payload.get('author_email')} replied regarding <strong>{assessment.title}</strong>:</p><blockquote>{payload['message']}</blockquote>",
        )

    return comment

@router.post("/followup/{invite_id}", response_model=FollowUpEmailOut)
def send_followup_email(invite_id: str, body: dict = {}, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    assessment = db.query(models.Assessment).get(invite.assessment_id)
    candidate = db.query(models.Candidate).get(invite.candidate_id)

    # Get template (prefer passed-in, else settings, else fallback)
    template_subject = body.get("subject")
    template_body = body.get("body")
    if not template_subject or not template_body:
        settings_row = db.query(Setting).filter(Setting.key == "followup_template").first()
        default_subj = "Follow-Up Interview Invitation"
        default_body = "We'd like to schedule a follow-up interview. Please reply with your availability."
        if settings_row:
            # stored as {"subject": s, "body": b}
            try:
                parsed = json.loads(settings_row.value)
                template_subject = template_subject or parsed.get("subject", default_subj)
                template_body = template_body or parsed.get("body", default_body)
            except Exception:
                template_subject = template_subject or default_subj
                template_body = template_body or default_body
        else:
            template_subject = template_subject or default_subj
            template_body = template_body or default_body
    # Send email
    email_svc = EmailService()
    email_svc.send_email(
        to=candidate.email,
        subject=template_subject,
        html=template_body,
    )
    # Store history
    rec = FollowUpEmail(
        id=uuid4(),
        invite_id=invite_id,
        sent_at=datetime.now(timezone.utc),
        template_subject=template_subject,
        template_body=template_body,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec

@router.get("/followup/{invite_id}", response_model=list[FollowUpEmailOut])
def followup_email_history(invite_id: str, db: Session = Depends(get_db)):
    rows = db.query(FollowUpEmail).filter(FollowUpEmail.invite_id == invite_id).order_by(FollowUpEmail.sent_at.desc()).all()
    return rows

@router.get("/followup-template", response_model=SettingOut)
def get_followup_template(db: Session = Depends(get_db)):
    row = db.query(Setting).filter(Setting.key == "followup_template").first()
    if not row:
        from uuid import uuid4
        # Create if doesn't exist
        val = json.dumps({"subject": "Follow-Up Interview Invitation", "body": "We'd like to schedule a follow-up interview. Please reply with your availability."})
        row = Setting(id=uuid4(), key="followup_template", value=val)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row

@router.put("/followup-template", response_model=SettingOut)
def set_followup_template(body: dict, db: Session = Depends(get_db)):
    row = db.query(Setting).filter(Setting.key == "followup_template").first()
    val = json.dumps({"subject": body.get("subject", "Follow-Up Interview Invitation"), "body": body.get("body", "We'd like to schedule a follow-up interview. Please reply with your availability.")})
    if not row:
        from uuid import uuid4
        row = Setting(id=uuid4(), key="followup_template", value=val)
        db.add(row)
    else:
        row.value = val
    db.commit()
    db.refresh(row)
    return row

@router.get("/diff/{invite_id}", response_model=list[DiffFile])
def get_diff(invite_id: str, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    cand_repo = db.query(models.CandidateRepo).filter(models.CandidateRepo.invite_id == invite.id).first()
    if not cand_repo:
        return []
    gh = GitHubService()
    try:
        comp = gh.compare_commits(cand_repo.repo_full_name, cand_repo.pinned_main_sha, "main")
    except Exception as e:
        # If base commit isn't present (e.g., force-push or history mismatch),
        # return an empty diff instead of hard error to avoid blocking review UX.
        msg = str(e)
        if "404" in msg and "compare" in msg:
            return []
        raise HTTPException(status_code=502, detail=f"Failed to compute diff: {str(e)}")

    files = comp.get("files", [])
    result = []
    for f in files:
        result.append({
            "filename": f.get("filename"),
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("changes", 0),
            "status": f.get("status"),
            "patch": f.get("patch"),
        })
    return result

@router.get("/inline-comments/{invite_id}", response_model=list[InlineCommentOut])
def list_inline_comments(invite_id: str, db: Session = Depends(get_db)):
    rows = db.query(models.ReviewInlineComment).filter(models.ReviewInlineComment.invite_id == invite_id).order_by(models.ReviewInlineComment.created_at).all()
    return rows

@router.post("/inline-comments/{invite_id}", response_model=InlineCommentOut)
def add_inline_comment(invite_id: str, body: dict, db: Session = Depends(get_db)):
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    from uuid import uuid4
    from datetime import datetime, timezone
    row = models.ReviewInlineComment(
        id=uuid4(),
        invite_id=invite_id,
        file_path=body.get("file_path"),
        line=body.get("line"),
        message=body.get("message"),
        author_email=body.get("author_email") or "admin@yourdomain.com",
        author_name=body.get("author_name") or "Admin",
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/inline-comments/{comment_id}")
def delete_inline_comment(comment_id: str, db: Session = Depends(get_db)):
    """Delete an inline comment by ID."""
    try:
        comment_uuid = UUID(comment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid comment ID format")
    
    comment = db.query(models.ReviewInlineComment).filter(models.ReviewInlineComment.id == comment_uuid).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Inline comment not found")
    
    db.delete(comment)
    db.commit()
    return {"status": "deleted", "id": comment_id}


@router.post("/send-inline-comments/{invite_id}")
def send_inline_comments_email(invite_id: str, db: Session = Depends(get_db)):
    """Send inline comments and git diff via email to the candidate."""
    invite = db.query(models.AssessmentInvite).get(invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    
    assessment = db.query(models.Assessment).get(invite.assessment_id)
    candidate = db.query(models.Candidate).get(invite.candidate_id)
    
    # Get all inline comments
    inline_comments = db.query(models.ReviewInlineComment).filter(
        models.ReviewInlineComment.invite_id == invite_id
    ).order_by(
        models.ReviewInlineComment.file_path,
        models.ReviewInlineComment.line
    ).all()
    
    if not inline_comments:
        raise HTTPException(status_code=400, detail="No inline comments found to send")
    
    # Get git diff
    cand_repo = db.query(models.CandidateRepo).filter(
        models.CandidateRepo.invite_id == invite.id
    ).first()
    
    diff_files = []
    if cand_repo:
        gh = GitHubService()
        try:
            comp = gh.compare_commits(cand_repo.repo_full_name, cand_repo.pinned_main_sha, "main")
            files = comp.get("files", [])
            for f in files:
                diff_files.append({
                    "filename": f.get("filename"),
                    "patch": f.get("patch"),
                    "status": f.get("status"),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                })
        except Exception as e:
            # If diff fetch fails, continue without diff in email
            pass
    
    # Group comments by file
    comments_by_file = {}
    for comment in inline_comments:
        file_path = comment.file_path
        if file_path not in comments_by_file:
            comments_by_file[file_path] = []
        comments_by_file[file_path].append(comment)
    
    # Build HTML email
    html_parts = [
        f"<h2>Review Comments for {html.escape(assessment.title)}</h2>",
        f"<p>Hi {html.escape(candidate.full_name or 'there')},</p>",
        "<p>Below are the inline comments on your submission:</p>",
    ]
    
    # Add inline comments section
    html_parts.append("<h3>Inline Comments</h3>")
    for file_path, comments in comments_by_file.items():
        html_parts.append(f'<div style="margin-bottom: 20px; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">')
        html_parts.append(f'<strong style="color: #0066cc; font-family: monospace;">{html.escape(file_path)}</strong>')
        html_parts.append('<ul style="margin-top: 10px; padding-left: 20px;">')
        for comment in comments:
            line_info = f"Line {comment.line}" if comment.line else "General comment"
            escaped_message = html.escape(comment.message).replace('\n', '<br>')
            escaped_author = html.escape(comment.author_name or 'Admin')
            html_parts.append(
                f'<li style="margin-bottom: 10px;">'
                f'<strong>{line_info}:</strong> {escaped_message}'
                f'<br><small style="color: #666;">{escaped_author} - {comment.created_at.strftime("%Y-%m-%d %H:%M")}</small>'
                f'</li>'
            )
        html_parts.append('</ul>')
        html_parts.append('</div>')
    
    # Add git diff section
    if diff_files:
        html_parts.append("<h3>Git Diff</h3>")
        html_parts.append("<p>Below is the diff between the seed repository and your submission:</p>")
        for diff_file in diff_files:
            html_parts.append(f'<div style="margin-bottom: 20px; border: 1px solid #ddd; padding: 10px; border-radius: 4px;">')
            html_parts.append(
                f'<strong style="color: #0066cc; font-family: monospace;">{html.escape(diff_file["filename"])}</strong> '
                f'<span style="color: #666;">(+{diff_file["additions"]} -{diff_file["deletions"]})</span>'
            )
            if diff_file.get("patch"):
                # Parse unified diff and render with old/new line numbers (like DiffViewer in frontend)
                patch_lines = diff_file["patch"].split("\n")
                old_line = 0
                new_line = 0
                
                # Start table for diff with line numbers
                patch_html = '''
                <table style="width: 100%; border-collapse: collapse; font-family: monospace; font-size: 12px; background: #f5f5f5;">
                    <thead>
                        <tr style="background: #e5e5e5; border-bottom: 1px solid #ccc;">
                            <th style="padding: 4px 8px; text-align: right; width: 60px; color: #666; font-size: 11px;">old</th>
                            <th style="padding: 4px 8px; text-align: right; width: 60px; color: #666; font-size: 11px;">new</th>
                            <th style="padding: 4px 8px; text-align: center; width: 30px; color: #666; font-size: 11px;">±</th>
                            <th style="padding: 4px 8px; text-align: left; color: #666; font-size: 11px;">code</th>
                        </tr>
                    </thead>
                    <tbody>
                '''
                
                for line in patch_lines:
                    raw_line = line
                    if raw_line.startswith("@@"):
                        # Hunk header: @@ -a,b +c,d @@
                        m = re.match(r'@@\s-(\d+)(?:,\d+)?\s\+(\d+)(?:,\d+)?\s@@', raw_line)
                        if m:
                            old_line = int(m.group(1))
                            new_line = int(m.group(2))
                        
                        # Render hunk header row
                        escaped_header = html.escape(raw_line)
                        patch_html += f'''
                        <tr style="background: #e5e5e5;">
                            <td colspan="4" style="padding: 4px 8px; color: #666; font-size: 11px; font-weight: bold;">
                                {escaped_header}
                            </td>
                        </tr>
                        '''
                        continue
                    
                    # Determine line type and display numbers
                    display_old = None
                    display_new = None
                    bg_color = ""
                    text_color = ""
                    sign = raw_line[0] if raw_line else " "
                    
                    if raw_line.startswith("+"):
                        # Addition - show only new line number
                        display_old = None
                        display_new = new_line
                        new_line += 1
                        bg_color = "#e6ffed"
                        text_color = "#22863a"
                    elif raw_line.startswith("-"):
                        # Deletion - show only old line number
                        display_old = old_line
                        display_new = None
                        old_line += 1
                        bg_color = "#ffeef0"
                        text_color = "#cb2431"
                    else:
                        # Context line - show both line numbers
                        display_old = old_line
                        display_new = new_line
                        old_line += 1
                        new_line += 1
                        bg_color = ""
                        text_color = ""
                    
                    # Get content (remove + or - prefix for display)
                    content = raw_line[1:] if raw_line.startswith(("+", "-")) else raw_line
                    escaped_content = html.escape(content)
                    
                    # Render line with line numbers
                    old_cell = f'<td style="padding: 2px 8px; text-align: right; color: #999; font-size: 11px;">{display_old if display_old is not None else ""}</td>'
                    new_cell = f'<td style="padding: 2px 8px; text-align: right; color: #999; font-size: 11px;">{display_new if display_new is not None else ""}</td>'
                    sign_cell = f'<td style="padding: 2px 8px; text-align: center; color: #999; font-size: 11px;">{html.escape(sign)}</td>'
                    content_cell = f'<td style="padding: 2px 8px; background: {bg_color}; color: {text_color if text_color else "inherit"}; white-space: pre-wrap; word-wrap: break-word;">{escaped_content}</td>'
                    
                    patch_html += f'<tr style="border-bottom: 1px solid #eee;">{old_cell}{new_cell}{sign_cell}{content_cell}</tr>\n'
                
                patch_html += '''
                    </tbody>
                </table>
                '''
                html_parts.append(patch_html)
            else:
                html_parts.append("<p style='color: #666;'>No patch available for this file.</p>")
            html_parts.append('</div>')
    
    html_body = "<html><body style='font-family: Arial, sans-serif; line-height: 1.6; color: #333;'>" + "".join(html_parts) + "</body></html>"
    
    # Send email
    email_svc = EmailService()
    email_svc.send_email(
        to=candidate.email,
        subject=f"Inline Comments - {assessment.title}",
        html=html_body,
    )
    
    return {"status": "sent", "comments_count": len(inline_comments), "diff_files_count": len(diff_files)}


