from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_context
from app.services.invite_service import create_invitation, accept_invitation, validate_invite_token, send_invite_email
from app.models.invitation import Invitation
from app.models.user import User

router = APIRouter(prefix="/invitations", tags=["Invitations"])


class SendInviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"  # Default role


@router.post("/send")
async def send_invite(
    request: SendInviteRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Send an invitation to join the organization."""
    user = context["user"]
    organization = context["organization"]
    role = context["role"]

    # Check permissions: only owner or admin can send invites
    if role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Validate role
    if request.role not in ["owner", "admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    invitation = create_invitation(
        db=db,
        email=request.email,
        organization_id=organization.id,
        role=request.role,
        invited_by_user_id=user.id
    )

    # Send email
    await send_invite_email(
        email=request.email,
        invite_token=invitation.invite_token,
        organization_name=organization.name,
        invited_by_name=user.email  # Or user name if available
    )

    return {"message": "Invitation sent successfully", "invitation_id": str(invitation.id)}


@router.post("/{token}/accept")
def accept_invite(
    token: str,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Accept an invitation."""
    user = context["user"]

    invitation_id = validate_invite_token(token)
    if not invitation_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    membership = accept_invitation(db, invitation_id, user)

    return {
        "message": "Invitation accepted successfully",
        "organization_id": str(membership.organization_id),
        "role": membership.role
    }


@router.get("/{token}")
def get_invite_details(token: str, db: Session = Depends(get_db)):
    """Get invitation details for the accept page."""
    invitation_id = validate_invite_token(token)
    if not invitation_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Invitation is not pending")

    return {
        "email": invitation.email,
        "organization_name": invitation.organization.name,
        "role": invitation.role,
        "invited_by": invitation.invited_by.email,
        "expires_at": invitation.expires_at
    }