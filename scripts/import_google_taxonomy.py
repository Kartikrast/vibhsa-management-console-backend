import hashlib
from pathlib import Path
from sqlalchemy.orm import Session
import sys
from pathlib import Path

from sqlalchemy.orm import Session

# Ensure project root is on sys.path when running as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import SessionLocal
from app.models.google_taxonomy import GoogleTaxonomy


# ==========================================
# CONFIG
# ==========================================
BASE_DIR = ROOT_DIR
FILE_PATH = BASE_DIR / "data" / "google_taxonomy.txt"


def calculate_depth(path: str) -> int:
    return len([segment.strip() for segment in path.split(">")])


def generate_deterministic_id(path: str) -> int:
    """
    Generate stable integer ID from full path.
    """
    hash_object = hashlib.sha256(path.encode("utf-8"))
    return int(hash_object.hexdigest(), 16) % (10**9)


def import_google_taxonomy():
    if not FILE_PATH.exists():
        print("❌ Taxonomy file not found.")
        return

    db: Session = SessionLocal()

    try:
        with open(FILE_PATH, "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]

        all_paths = set(lines)

        inserted = 0
        skipped = 0

        for full_path in lines:
            depth = calculate_depth(full_path)
            google_id = generate_deterministic_id(full_path)

            # Leaf detection:
            is_leaf = not any(
                other.startswith(full_path + " >")
                for other in all_paths
            )

            existing = (
                db.query(GoogleTaxonomy)
                .filter(GoogleTaxonomy.full_path == full_path)
                .first()
            )

            if existing:
                skipped += 1
                continue

            taxonomy = GoogleTaxonomy(
                google_taxonomy_id=google_id,
                full_path=full_path,
                level_depth=depth,
                is_leaf=is_leaf,
            )

            db.add(taxonomy)
            inserted += 1

        db.commit()

        print("===================================")
        print("✅ Google Taxonomy Import Complete")
        print(f"Inserted: {inserted}")
        print(f"Skipped: {skipped}")
        print("===================================")

    except Exception as e:
        db.rollback()
        print("❌ Error occurred:", str(e))

    finally:
        db.close()


if __name__ == "__main__":
    import_google_taxonomy()
