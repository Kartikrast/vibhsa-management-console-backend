from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import UserCreate, UserLogin, Token, GoogleAuthRequest, MeResponse
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.core.security import hash_password
from app.services.auth_service import authenticate_user, issue_tokens
from app.utils.slug import generate_slug
from app.services.google_oauth import verify_google_token
from app.core.dependencies import get_current_context




router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup", response_model=Token)
def signup(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    # 1. Check if user already exists
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # 2. Generate org slug and check uniqueness
    org_slug = generate_slug(payload.organization_name)

    existing_org = (
        db.query(Organization)
        .filter(Organization.slug == org_slug)
        .first()
    )
    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already in use",
        )

    # 3. Create user
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        auth_provider="local",
    )
    db.add(user)
    db.flush()

    # 4. Create organization
    organization = Organization(
        name=payload.organization_name,
        slug=org_slug,
    )
    db.add(organization)
    db.flush()

    # 5. Create membership
    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=organization.id,
        role="owner",
    )
    db.add(membership)

    # 6. Commit
    db.commit()

    # 7. Issue tokens
    return issue_tokens(
        db=db,
        user=user,
        organization_id=organization.id,
    )


@router.post("/login", response_model=Token)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    # 1) Authenticate credentials
    user = authenticate_user(
        db=db,
        email=payload.email,
        password=payload.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # 2) Pick active organization (MVP: first active)
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of any active organization",
        )

    # 3) Issue tokens
    return issue_tokens(
        db=db,
        user=user,
        organization_id=membership.organization_id,
    )

@router.post("/google", response_model=Token)
def google_auth(
    payload: GoogleAuthRequest,
    db: Session = Depends(get_db),
):
    # 1) Verify Google token
    try:
        google_data = verify_google_token(payload.token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    email = google_data.get("email")
    google_user_id = google_data.get("sub")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    # 2) Find existing user
    user = (
        db.query(User)
        .filter(
            (User.provider_user_id == google_user_id)
            | (User.email == email)
        )
        .first()
    )

    # 3) Create user if new
    if not user:
        user = User(
            email=email,
            hashed_password=None,
            auth_provider="google",
            provider_user_id=google_user_id,
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Create organization for first-time Google user
        org_slug = generate_slug(payload.organization_name)
        if db.query(Organization).filter(Organization.slug == org_slug).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name already in use",
            )

        organization = Organization(
            name=payload.organization_name,
            slug=org_slug,
            is_active=True,
        )
        db.add(organization)
        db.flush()

        membership = OrganizationMembership(
            user_id=user.id,
            organization_id=organization.id,
            role="owner",
            is_active=True,
        )
        db.add(membership)
        db.commit()

        return issue_tokens(
            db=db,
            user=user,
            organization_id=organization.id,
        )

    # 4) Existing user → pick active org
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no active organization",
        )

    return issue_tokens(
        db=db,
        user=user,
        organization_id=membership.organization_id,
    )

@router.get("/me", response_model=MeResponse)
def get_me(context=Depends(get_current_context)):
    user = context["user"]
    organization = context["organization"]
    role = context["role"]

    return MeResponse(
        id=user.id,
        email=user.email,
        auth_provider=user.auth_provider,
        organization=organization,
        role=role,
    )
