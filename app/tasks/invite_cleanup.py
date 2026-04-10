"""
Background task to clean up expired invitations.
"""
import logging
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.invitation import Invitation, InviteStatus

logger = logging.getLogger(__name__)


def cleanup_expired_invitations():
    """
    Mark expired pending invitations as expired.
    Run periodically to clean up old invites.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        expired_count = db.query(Invitation).filter(
            Invitation.status == InviteStatus.PENDING,
            Invitation.expires_at < now
        ).update({"status": InviteStatus.EXPIRED})

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired invitations")

        db.commit()
    except Exception as e:
        logger.error(f"Error cleaning up expired invitations: {e}")
        db.rollback()
    finally:
        db.close()