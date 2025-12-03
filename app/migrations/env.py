from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from app.infrastructure.database.connection import Base

# Импорт моделей (на всякий случай оставляем, чтобы не ломалось в будущем)
from app.models.user import Users
from app.models.user_token import UserToken
from app.models.page import Page
from app.models.achievement import Achievement

target_metadata = Base.metadata
config = context.config
fileConfig(config.config_file_name)

def get_url():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_USERNAME = os.getenv("DB_USERNAME", "user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
    DB_NAME = os.getenv("DB_NAME", "fastkit_db")
    DB_PORT = os.getenv("DB_PORT", "5432")
    return f"postgresql+psycopg2://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

# ЗАПУСКАЕМ ТОЛЬКО ОНЛАЙН, ЧТОБЫ ИЗБЕЖАТЬ ОШИБОК STAMP
run_migrations_online()