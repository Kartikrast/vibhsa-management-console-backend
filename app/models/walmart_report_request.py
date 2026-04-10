from sqlalchemy import String, UUID, ForeignKey, DateTime, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from typing import Optional
import uuid
from app.models.base import Base


class WalmartReportRequest(Base):
    __tablename__ = "walmart_report_requests"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    marketplace_account_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_accounts.id"), nullable=False)

    external_request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)
    report_version: Mapped[str] = mapped_column(String(10), nullable=False, default="v1")

    data_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")  # PENDING, SUBMITTED, PROCESSING, COMPLETED, FAILED

    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    download_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = relationship("Organization", back_populates="walmart_report_requests")
    marketplace_account = relationship("MarketplaceAccount", back_populates="walmart_report_requests")

    notifications = relationship(
        "WalmartReportNotification",
        back_populates="walmart_report_request",
        cascade="all, delete-orphan",
    )


class WalmartReportNotification(Base):
    __tablename__ = "walmart_report_notifications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    walmart_report_request_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("walmart_report_requests.id"), nullable=False)

    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "report.completed", "report.failed"
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    walmart_report_request = relationship("WalmartReportRequest", back_populates="notifications")