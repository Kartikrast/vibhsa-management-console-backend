from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from app.models.walmart_report_request import WalmartReportRequest, WalmartReportNotification
from app.models.marketplace_account import MarketplaceAccount
from app.marketplaces.walmart.client import WalmartClient, WalmartRateLimitError
from app.core.dependencies import get_current_context


def create_walmart_report_request(
    db: Session,
    organization_id: UUID,
    marketplace_account_id: UUID,
    report_type: str,
    report_version: str,
    data_start_time: datetime,
    data_end_time: datetime,
    row_filters: Optional[dict] = None,
    exclude_columns: Optional[List[str]] = None,
) -> WalmartReportRequest:
    """
    Create a new Walmart report request.
    """
    # Get marketplace account
    account = db.query(MarketplaceAccount).filter(
        and_(
            MarketplaceAccount.id == marketplace_account_id,
            MarketplaceAccount.organization_id == organization_id,
            MarketplaceAccount.marketplace == "walmart",
            MarketplaceAccount.is_active.is_(True),
        )
    ).first()

    if not account:
        raise ValueError("Walmart marketplace account not found")

    # Create client and submit request
    client = WalmartClient(account)

    try:
        response = client.create_report_request(
            db=db,
            report_type=report_type,
            report_version=report_version,
            data_start_time=data_start_time,
            data_end_time=data_end_time,
            row_filters=row_filters,
            exclude_columns=exclude_columns,
        )
    except WalmartRateLimitError as e:
        # Re-raise with additional context
        raise e

    # Create database record
    report_request = WalmartReportRequest(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        external_request_id=response.get("requestId"),
        report_type=report_type,
        report_version=report_version,
        data_start_time=data_start_time,
        data_end_time=data_end_time,
        status="SUBMITTED",
        request_payload={
            "reportType": report_type,
            "reportVersion": report_version,
            "dataStartTime": data_start_time.isoformat(),
            "dataEndTime": data_end_time.isoformat(),
            "rowFilters": row_filters,
            "excludeColumns": exclude_columns,
        },
        response_payload=response,
    )

    db.add(report_request)
    db.commit()
    db.refresh(report_request)

    return report_request


def list_walmart_report_requests(
    db: Session,
    organization_id: UUID,
    marketplace_account_id: Optional[UUID] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[WalmartReportRequest]:
    """
    List Walmart report requests for an organization.
    """
    query = db.query(WalmartReportRequest).filter(
        WalmartReportRequest.organization_id == organization_id
    )

    if marketplace_account_id:
        query = query.filter(WalmartReportRequest.marketplace_account_id == marketplace_account_id)

    if status:
        query = query.filter(WalmartReportRequest.status == status)

    query = query.order_by(WalmartReportRequest.created_at.desc())

    return query.limit(limit).offset(offset).all()


def get_walmart_report_request(
    db: Session,
    organization_id: UUID,
    report_request_id: UUID,
) -> WalmartReportRequest:
    """
    Get a specific Walmart report request.
    """
    report_request = db.query(WalmartReportRequest).filter(
        and_(
            WalmartReportRequest.id == report_request_id,
            WalmartReportRequest.organization_id == organization_id,
        )
    ).first()

    if not report_request:
        raise ValueError("Walmart report request not found")

    return report_request


def refresh_walmart_report_status(
    db: Session,
    organization_id: UUID,
    report_request_id: UUID,
) -> WalmartReportRequest:
    """
    Refresh the status of a Walmart report request by querying the API.
    """
    report_request = get_walmart_report_request(db, organization_id, report_request_id)
    account = report_request.marketplace_account
    client = WalmartClient(account)

    if report_request.status in ["READY", "FAILED"]:
        if report_request.status == "READY":
            report_request.completed_at = datetime.now(timezone.utc)
            # Try to get download URL
            try:
                download_response = client.get_report_download_url(db=db, request_id=report_request.external_request_id)
                report_request.download_url = download_response.get("downloadURL")
                report_request.expires_at = datetime.fromisoformat(download_response.get("expiresAt").replace('Z', '+00:00')) if download_response.get("expiresAt") else None
            except Exception:
                # if it fails, we can try again later, so we won't mark it as failed
                pass
                
        elif report_request.status == "FAILED":
            report_request.failed_at = datetime.now(timezone.utc)
            report_request.error = response.get("error", "Unknown error")

        db.commit()
        db.refresh(report_request)
        return report_request

    try:
        response = client.get_report_status(db=db, request_id=report_request.external_request_id)
    except WalmartRateLimitError as e:
        raise e

    # Update status based on response
    status = response.get("requestStatus", "UNKNOWN")
    report_request.status = status
    report_request.response_payload = response
    report_request.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report_request)
    return report_request


def handle_walmart_report_webhook(
    db: Session,
    event_type: str,
    event_id: str,
    request_id: str,
    payload: dict,
) -> WalmartReportRequest:
    """
    Handle Walmart report webhook notification.
    """
    # Find the report request by external ID
    report_request = db.query(WalmartReportRequest).filter(
        WalmartReportRequest.external_request_id == request_id
    ).first()

    if not report_request:
        raise ValueError(f"Walmart report request with ID {request_id} not found")

    # Check for duplicate event
    existing_notification = db.query(WalmartReportNotification).filter(
        WalmartReportNotification.event_id == event_id
    ).first()

    if existing_notification:
        return report_request  # Already processed

    # Update report status
    if event_type == "report.completed":
        report_request.status = "READY"
        report_request.completed_at = datetime.now(timezone.utc)
        report_request.download_url = payload.get("downloadUrl")
        if payload.get("expiresAt"):
            report_request.expires_at = datetime.fromisoformat(payload["expiresAt"].replace('Z', '+00:00'))
    elif event_type == "report.failed":
        report_request.status = "FAILED"
        report_request.failed_at = datetime.now(timezone.utc)
        report_request.error = payload.get("error", "Report failed")

    report_request.response_payload = payload
    report_request.updated_at = datetime.now(timezone.utc)

    # Create notification record for idempotency
    notification = WalmartReportNotification(
        walmart_report_request_id=report_request.id,
        event_id=event_id,
        event_type=event_type,
        payload=payload,
    )

    db.add(notification)
    db.commit()
    db.refresh(report_request)

    return report_request