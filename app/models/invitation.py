import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, UUID, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
import enum

from app.models.base import Base


class InviteStatus(enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    role = Column(String, nullable=False, default="member")  # e.g., "owner", "admin", "member"
    invited_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(Enum(InviteStatus), nullable=False, default=InviteStatus.PENDING)
    invite_token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = relationship("Organization", back_populates="invitations")
    invited_by = relationship("User", back_populates="sent_invitations")