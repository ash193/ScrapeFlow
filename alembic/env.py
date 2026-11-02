import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.database import Base

# import the models so SQLAlchemy registers their tables
# Without this import, Base.metadata may be empty
import app.db_models # noqa: F401

# alembic's configuration object
config = context.config

# configure logging using alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# tell alembic which SQLAlchemy models define our scheme
target_metadata = Base.metadata

def get_database_url():
    # use a dedicated migration URL supplied by the shell
    # or docker compose
    # We deliberately do not load .env automatically
    # This helps avoid accidentally using the local
    # development database
    url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("DATABASE_URL")
    
    if not url:
        raise RuntimeError(
            "ALEMBIC_DATABASE_URL must be set to run migrations"
        )
    
    return url

def run_migrations_offline() -> None:
    # offline mode generates SQL without connecting
    # directly to PostgreSQL
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # create a connection using our selected database URL
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool
    )
    
    try:
        with connectable.connect() as connection:
            # compare actual PostgreSQL scheme with our models
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            
            with context.begin_transaction():
                context.run_migrations()
                
    finally:
        connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

