import re


def normalize_gtin(gtin: str | None) -> str | None:
    if not gtin:
        return None

    # remove non-numeric characters
    cleaned = re.sub(r"\D", "", gtin)

    if not cleaned:
        return None

    # remove leading zeros
    return cleaned.lstrip("0")
