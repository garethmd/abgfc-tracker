"""Seed the database for local development.

uv run python -m scripts.seed            # reference data + coach login
uv run python -m scripts.seed --demo     # ...plus the demo 2026/27 season
uv run python -m scripts.seed --reset    # drop everything first (dev only)
"""

import argparse
import subprocess
import sys

from app.config import get_settings
from app.db.session import SessionLocal, engine
from app.repositories.seasons import SeasonRepository
from app.services.bootstrap import seed_demo_season, seed_reference_data, seed_user


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="seed the demo season")
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()
    settings = get_settings()

    if args.reset:
        import app.models  # noqa: F401
        from app.db.base import Base

        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    with SessionLocal() as db:
        seed_reference_data(db)
        seed_user(db, settings.coach_username, settings.coach_password)
        if args.demo:
            if SeasonRepository(db).get_by_name("2026/27"):
                print("Demo season already present; skipping")
            else:
                seed_demo_season(db)
                print("Seeded demo season 2026/27")
        db.commit()
    print(f"Ready. Login: {settings.coach_username} / {settings.coach_password}")


if __name__ == "__main__":
    main()
