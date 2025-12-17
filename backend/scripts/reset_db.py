import argparse
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import Base, engine, get_db_path
from app.demo_seed import seed_demo_data


def reset_database(seed: bool = True) -> None:
    db_path = get_db_path()
    if engine.url.drivername.startswith("sqlite"):
        if not db_path:
            raise RuntimeError("SQLite database path could not be resolved.")
        path = Path(db_path)
        engine.dispose()
        if path.exists():
            print(f"[reset_db] Removing existing sqlite file: {path}")
            path.unlink()
        else:
            print(f"[reset_db] No existing sqlite file at {path}, skipping delete.")
    else:
        print(f"[reset_db] Non-sqlite database configured: {engine.url}. Skipping file delete.")

    # Recreate tables
    print("[reset_db] Creating database schema...")
    Base.metadata.create_all(bind=engine)

    if seed:
        print("[reset_db] Seeding demo data...")
        seed_demo_data()
    print("[reset_db] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset local development database.")
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Reset schema without seeding demo data.",
    )
    args = parser.parse_args()
    reset_database(seed=not args.no_seed)
