from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    UserCreate, UserLogin, Token, GoogleAuthRequest, MeResponse,
    OrganizationListItem, SwitchOrgRequest, RefreshTokenRequest,
    CreateOrgRequest, CreateOrgResponse, OrganizationInfo,
)
from app.models.user import User
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.core.security import hash_password, decode_token
from app.services.auth_service import authenticate_user, issue_tokens
from app.utils.slug import generate_slug
from app.services.google_oauth import verify_google_token
from app.core.dependencies import get_current_context, get_current_user




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
    db = context.get("db")

    # Fetch all orgs for the switcher
    if db:
        memberships = (
            db.query(OrganizationMembership)
            .join(Organization)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.is_active.is_(True),
                Organization.is_active.is_(True),
            )
            .all()
        )
    else:
        memberships = []

    org_list = [
        OrganizationListItem(
            id=m.organization.id,
            name=m.organization.name,
            slug=m.organization.slug,
            role=m.role,
            is_current=(m.organization.id == organization.id),
        )
        for m in memberships
    ]

    return MeResponse(
        id=user.id,
        email=user.email,
        auth_provider=user.auth_provider,
        organization=organization,
        role=role,
        organizations=org_list,
    )


@router.get("/organizations", response_model=list[OrganizationListItem])
def list_organizations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(OrganizationMembership)
        .join(Organization)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.is_active.is_(True),
            Organization.is_active.is_(True),
        )
        .all()
    )

    return [
        OrganizationListItem(
            id=m.organization.id,
            name=m.organization.name,
            slug=m.organization.slug,
            role=m.role,
        )
        for m in memberships
    ]


@router.post("/organizations", response_model=CreateOrgResponse)
def create_organization(
    payload: CreateOrgRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org_slug = generate_slug(payload.name)

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

    organization = Organization(
        name=payload.name,
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

    tokens = issue_tokens(
        db=db,
        user=user,
        organization_id=organization.id,
    )

    return CreateOrgResponse(
        organization=OrganizationInfo(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
        ),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/switch-org", response_model=Token)
def switch_organization(
    payload: SwitchOrgRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == payload.organization_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not belong to this organization",
        )

    organization = (
        db.query(Organization)
        .filter(
            Organization.id == payload.organization_id,
            Organization.is_active.is_(True),
        )
        .first()
    )
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is not active",
        )

    return issue_tokens(
        db=db,
        user=user,
        organization_id=organization.id,
    )


@router.post("/refresh", response_model=Token)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        token_data = decode_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if token_data.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = token_data.get("sub")
    org_id = token_data.get("org_id")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive user",
        )

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User no longer belongs to this organization",
        )

    return issue_tokens(
        db=db,
        user=user,
        organization_id=org_id,
    )
