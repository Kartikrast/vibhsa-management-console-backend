from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import get_settings

settings = get_settings()


def verify_google_token(token: str) -> dict:
    """
    Verifies Google ID token and returns user info.
    Raises ValueError if invalid.
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
        return idinfo
    except Exception:
        raise ValueError("Invalid Google token")
