import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.taxonomy import Color, Material, Size


# ==========================
# COLORS
# ==========================
COLOR_DATA = [
    ("MULTI", "ML", "0"),
    ("BLACK", "BLA", "1"),
    ("CHARCOAL", "CHA", "20"),
    ("PEWTER", "PEW", "30"),
    ("GRAY", "GRA", "40"),
    ("DARK GRAY", "DG", "50"),
    ("HEATHER GRAY", "HG", "60"),
    ("WHITE", "WHI", "100"),
    ("OFF-WHITE", "OW", "110"),
    ("IVORY", "IVO", "130"),
    ("BEIGE", "BEI", "180"),
    ("BROWN", "BRO", "200"),
    ("DARK BROWN", "DBR", "210"),
    ("GREEN", "GRE", "300"),
    ("OLIVE", "OLI", "330"),
    ("BLUE", "BLU", "400"),
    ("NAVY", "NAV", "410"),
    ("RED", "RED", "600"),
    ("PINK", "PIN", "650"),
    ("YELLOW", "YEL", "700"),
    ("ORANGE", "ORA", "800"),
    ("SILVER", "SVR", "900"),
]

# ==========================
# MATERIALS
# ==========================
MATERIAL_DATA = [
    ("Pure Cotton", "PC"),
    ("Wool", "WL"),
    ("Rexine", "RX"),
    ("Rubber", "RB"),
    ("Mixed Cotton", "MXC"),
    ("Silk", "SK"),
    ("Foam", "FM"),
    ("Leather", "LTH"),
    ("Polyester", "POL"),
    ("Iron", "IRN"),
    ("Steel", "STL"),
    ("Aluminium", "ALU"),
    ("Copper", "CPR"),
    ("Brass", "BRS"),
    ("Plastic", "PLS"),
    ("PVC", "PVC"),
    ("Polycarbonate", "PCARB"),
    ("Polypropylene", "PP"),
    ("Polyethylene", "PE"),
    ("ABS Plastic", "ABS"),
    ("Acrylic", "ACR"),
    ("Nylon", "NYL"),
    ("Silicone", "SIL"),
    ("Resin", "RSN"),
    ("Teflon", "TFL"),
]

# ==========================
# SIZES
# ==========================
SIZE_DATA = [
    ("Extra Small", "XS"),
    ("Small", "S"),
    ("Medium", "M"),
    ("Large", "L"),
    ("Extra Large", "XL"),
    ("Double XL", "XXL"),
    ("Triple XL", "XXXL"),
    ("One Size", "OS"),
]


def seed_master_data():
    db: Session = SessionLocal()

    try:
        # Colors
        for name, short_code, nrf in COLOR_DATA:
            existing = db.query(Color).filter(Color.short_code == short_code).first()
            if not existing:
                db.add(Color(name=name, short_code=short_code, nrf_code=nrf))

        # Materials
        for name, short_code in MATERIAL_DATA:
            existing = db.query(Material).filter(Material.short_code == short_code).first()
            if not existing:
                db.add(Material(name=name, short_code=short_code))

        # Sizes
        for name, short_code in SIZE_DATA:
            existing = db.query(Size).filter(Size.short_code == short_code).first()
            if not existing:
                db.add(Size(name=name, short_code=short_code))

        db.commit()
        print("✅ Master data seeded successfully")

    except Exception as e:
        db.rollback()
        print("❌ Error:", e)

    finally:
        db.close()


if __name__ == "__main__":
    seed_master_data()
