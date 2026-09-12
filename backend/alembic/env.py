from logging.config import fileConfig

from sqlalchemy import create_engine

import app.models  # noqa: F401  (registers every table on Base.metadata)
from alembic import context
from app.config import get_settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Deliberately NOT app.db.session.make_engine: batch mode rebuilds tables with
    # DROP + CREATE, which SQLite refuses while foreign keys are enforced. The app
    # itself always runs with PRAGMA foreign_keys=ON.
    connectable = create_engine(config.get_main_option("sqlalchemy.url"))
    with connectable.connect() as connection:
        # SQLite can't ALTER most things; batch mode rebuilds tables for us.
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
