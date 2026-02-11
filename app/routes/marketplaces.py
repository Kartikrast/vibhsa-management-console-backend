from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_context
from app.schemas.marketplace import WalmartConnectRequest
from app.models.marketplace_account import MarketplaceAccount
from app.marketplaces.walmart.client import WalmartClient

router = APIRouter(prefix="/marketplaces", tags=["Marketplaces"])

@router.post("/walmart/connect")
def connect_walmart(
    payload: WalmartConnectRequest,
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    # Prevent duplicate connection
    existing = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Walmart already connected",
        )

    # Create client
    client = WalmartClient(
        client_id=payload.client_id,
        client_secret=payload.client_secret,
    )

    try:
        token_data = client.get_access_token()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Walmart credentials",
        )

    expiry = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])

    account = MarketplaceAccount(
        organization_id=organization.id,
        marketplace="walmart",
        seller_id=payload.seller_id,
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        access_token=token_data["access_token"],
        token_expiry=expiry,
        is_active=True,
    )

    db.add(account)
    db.commit()

    return {"message": "Walmart connected successfully"}

@router.get("/walmart/items")
def fetch_walmart_items(
    context=Depends(get_current_context),
    db: Session = Depends(get_db),
):
    organization = context["organization"]

    account = db.query(MarketplaceAccount).filter(
        MarketplaceAccount.organization_id == organization.id,
        MarketplaceAccount.marketplace == "walmart",
        MarketplaceAccount.is_active.is_(True),
    ).first()

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Walmart not connected",
        )

    client = WalmartClient(account)

    data = client.get_items(db=db, limit=10)

    return data
