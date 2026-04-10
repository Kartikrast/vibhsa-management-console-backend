import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.invitation import Invitation, InviteStatus
from app.models.organization_membership import OrganizationMembership
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)

# Email configuration - only if SMTP is configured
if settings.SMTP_USERNAME and settings.SMTP_PASSWORD and settings.EMAIL_FROM:
    mail_conf = ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USERNAME,
        MAIL_PASSWORD=settings.SMTP_PASSWORD,
        MAIL_FROM=settings.EMAIL_FROM,
        MAIL_PORT=settings.SMTP_PORT,
        MAIL_SERVER=settings.SMTP_SERVER,
        MAIL_FROM_NAME=settings.EMAIL_FROM_NAME,
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
    )
    fm = FastMail(mail_conf)
else:
    fm = None


def generate_invite_token(invitation_id: UUID) -> str:
    """Generate a JWT token for the invitation."""
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {"invitation_id": str(invitation_id), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def validate_invite_token(token: str) -> Optional[UUID]:
    """Validate the invite token and return invitation_id if valid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        invitation_id: str = payload.get("invitation_id")
        if invitation_id is None:
            return None
        return UUID(invitation_id)
    except JWTError:
        return None


async def send_invite_email(email: str, invite_token: str, organization_name: str, invited_by_name: str):
    """Send invitation email."""
    if not fm:
        logger.warning("Email not configured, skipping invite email to %s", email)
        # For development: print the email content to console
        invite_url = f"{settings.APP_URL}/accept-invite/{invite_token}"
        email_content = f"""
To: {email}
Subject: Invitation to join {organization_name}

Hi,

{invited_by_name} has invited you to join {organization_name} on Vibhsa Management Console.

Click the link below to accept the invitation:

{invite_url}

This link will expire in 7 days.

Best regards,
Vibhsa Team
        """
        print("=== INVITATION EMAIL (not sent - email not configured) ===")
        print(email_content)
        print("=========================================================")
        return

    invite_url = f"{settings.APP_URL}/accept-invite/{invite_token}"  # Assuming frontend URL

    message = MessageSchema(
        subject=f"Invitation to join {organization_name}",
        recipients=[email],
        body=f"""
        Hi,

        {invited_by_name} has invited you to join {organization_name} on Vibhsa Management Console.

        Click the link below to accept the invitation:

        {invite_url}

        This link will expire in 7 days.

        Best regards,
        Vibhsa Team
        """,
        subtype="plain"
    )

    try:
        await fm.send_message(message)
        logger.info(f"Invitation email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send invitation email to {email}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send invitation email")


def create_invitation(
    db: Session,
    email: str,
    organization_id: UUID,
    role: str,
    invited_by_user_id: UUID
) -> Invitation:
    """Create a new invitation."""
    # Check if user is trying to invite themselves
    inviting_user = db.query(User).filter(User.id == invited_by_user_id).first()
    if inviting_user and inviting_user.email == email:
        logger.warning(f"Cannot send invitation: User {invited_by_user_id} is trying to invite themselves ({email})")
        raise HTTPException(status_code=400, detail="You cannot send an invitation to yourself")

    # Check if user is already a member
    existing_membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id.in_(
            db.query(User.id).filter(User.email == email)
        )
    ).first()
    if existing_membership:
        logger.warning(f"Cannot send invitation: User {email} is already a member of organization {organization_id}")
        raise HTTPException(status_code=400, detail="User is already a member of this organization")

    # Check for pending invitation
    pending_invite = db.query(Invitation).filter(
        Invitation.email == email,
        Invitation.organization_id == organization_id,
        Invitation.status == InviteStatus.PENDING
    ).first()
    if pending_invite:
        logger.warning(f"Cannot send invitation: Pending invitation already exists for {email} in organization {organization_id}")
        raise HTTPException(status_code=400, detail="Pending invitation already exists for this email")

    # Generate ID and token first
    invitation_id = uuid4()
    invite_token = generate_invite_token(invitation_id)

    invitation = Invitation(
        id=invitation_id,
        email=email,
        organization_id=organization_id,
        role=role,
        invited_by_user_id=invited_by_user_id,
        invite_token=invite_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )

    db.add(invitation)
    db.commit()

    return invitation


def accept_invitation(db: Session, invitation_id: UUID, user: User) -> OrganizationMembership:
    """Accept an invitation and create membership."""
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status != InviteStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invitation is not pending")

    if invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = InviteStatus.EXPIRED
        db.commit()
        raise HTTPException(status_code=400, detail="Invitation has expired")

    if invitation.email != user.email:
        raise HTTPException(status_code=400, detail="Invitation email does not match user email")

    # Create membership
    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=invitation.organization_id,
        role=invitation.role
    )
    db.add(membership)

    # Update invitation status
    invitation.status = InviteStatus.ACCEPTED
    db.commit()

    return membership


def get_pending_invitations(db: Session, organization_id: UUID):
    """Get pending invitations for an organization."""
    return db.query(Invitation).filter(
        Invitation.organization_id == organization_id,
        Invitation.status == InviteStatus.PENDING
    ).all()