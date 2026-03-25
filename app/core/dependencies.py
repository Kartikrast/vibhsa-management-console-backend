from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership

security = HTTPBearer()


def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Lightweight dependency: validates user only, no org check."""
    try:
        payload = decode_token(token.credentials)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user",
        )

    return user


def get_current_context(
    token: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        payload = decode_token(token.credentials)
        user_id = payload.get("sub")
        org_id = payload.get("org_id")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user",
        )

    organization = db.query(Organization).filter(
        Organization.id == org_id,
        Organization.is_active.is_(True),
    ).first()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid organization",
        )

    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.organization_id == organization.id,
        OrganizationMembership.is_active.is_(True),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to this organization",
        )

    return {
        "user": user,
        "organization": organization,
        "role": membership.role,
        "db": db,
    }
