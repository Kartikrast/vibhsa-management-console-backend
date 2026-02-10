import re

def generate_slug(name: str) -> str:
    """
    Convert organization name to URL-safe slug.
    Example: 'Vibhsa Test Store' -> 'vibhsa-test-store'
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower())
    return slug.strip("-")
