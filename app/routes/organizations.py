from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_context
from app.core.security import hash_password
from app.models.organization_membership import OrganizationMembership
from app.models.user import User

router = APIRouter(prefix="/organizations", tags=["Organizations"])


class CreateMemberRequest(BaseModel):
    email: str
    password: str
    role: str


class UpdateMemberRoleRequest(BaseModel):
    role: str


@router.get("/{org_id}/members")
def get_members(
    org_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Get all members of an organization."""
    user = context["user"]
    organization = context["organization"]
    role = context["role"]

    if str(organization.id) != str(org_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Only owners/admins can view members
    if role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    memberships = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id
    ).all()

    members = []
    for membership in memberships:
        user_data = db.query(User).filter(User.id == membership.user_id).first()
        members.append({
            "user_id": str(membership.user_id),
            "email": user_data.email,
            "role": membership.role,
            "is_active": membership.is_active,
            "joined_at": membership.created_at
        })

    return {"members": members}


@router.post("/{org_id}/members")
def create_member(
    org_id: UUID,
    request: CreateMemberRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Create a new user + membership directly (no invite link)."""
    user = context["user"]
    organization = context["organization"]
    current_role = context["role"]

    if str(organization.id) != str(org_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # only owner/admin may create members
    if current_role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if request.role not in ["owner", "admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid member role")

    email = request.email.strip().lower()

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        # User exists: ensure not already member
        existing_member = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.user_id == existing_user.id,
        ).first()
        if existing_member:
            raise HTTPException(status_code=400, detail="User is already a member")

        if existing_user.auth_provider != "local":
            raise HTTPException(status_code=400, detail="Cannot assign local password to external auth user")

        existing_user.hashed_password = hash_password(request.password)
        user_obj = existing_user
    else:
        user_obj = User(
            email=email,
            hashed_password=hash_password(request.password),
            auth_provider="local",
            is_active=True,
        )
        db.add(user_obj)
        db.flush()

    membership = OrganizationMembership(
        user_id=user_obj.id,
        organization_id=organization.id,
        role=request.role,
        is_active=True,
    )
    db.add(membership)
    db.commit()

    return {
        "message": "User created and added to organization",
        "user_id": str(user_obj.id),
        "organization_id": str(organization.id),
        "role": request.role,
    }


@router.patch("/{org_id}/members/{user_id}")
def update_member_role(
    org_id: UUID,
    user_id: UUID,
    request: UpdateMemberRoleRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Update a member's role."""
    user = context["user"]
    organization = context["organization"]
    role = context["role"]

    if str(organization.id) != str(org_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Only owners can change roles
    if role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can update member roles")

    # Validate role
    if request.role not in ["owner", "admin", "member"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot change own role if only owner
    if user_id == user.id:
        other_owners = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.role == "owner",
            OrganizationMembership.user_id != user_id
        ).count()
        if other_owners == 0:
            raise HTTPException(status_code=400, detail="Cannot change role: you are the only owner")

    membership.role = request.role
    db.commit()

    return {"message": "Member role updated successfully"}


@router.delete("/{org_id}/members/{user_id}")
def remove_member(
    org_id: UUID,
    user_id: UUID,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    """Remove a member from the organization."""
    user = context["user"]
    organization = context["organization"]
    role = context["role"]

    if str(organization.id) != str(org_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Only owners can remove members
    if role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can remove members")

    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == org_id,
        OrganizationMembership.user_id == user_id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot remove self if only owner
    if user_id == user.id:
        other_owners = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.role == "owner",
            OrganizationMembership.user_id != user_id
        ).count()
        if other_owners == 0:
            raise HTTPException(status_code=400, detail="Cannot remove yourself: you are the only owner")

    db.delete(membership)
    db.commit()

    return {"message": "Member removed successfully"}