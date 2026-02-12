from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization_membership import OrganizationMembership
from app.schemas.auth import Token
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
)

def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None

    if not user.hashed_password:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    if not user.is_active:
        return None

    return user


def issue_tokens(
    db: Session,
    user: User,
    organization_id,
) -> Token:
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )

    if not membership:
        raise ValueError("User does not belong to this organization")

    access_token = create_access_token(
        subject=user.id,
        organization_id=organization_id,
        role=membership.role,
    )

    refresh_token = create_refresh_token(subject=user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )
