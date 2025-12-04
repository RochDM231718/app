import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Database:
    def __init__(self):
        # Получаем URL и меняем драйвер на асинхронный
        # Например: postgresql:// -> postgresql+asyncpg://
        self.database_url = self._get_db_url()

        self.engine = create_async_engine(
            self.database_url,
            echo=True,  # Полезно для отладки
            future=True
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )

    def _get_db_url(self):
        driver = os.getenv("DB_DRIVER", "postgres").lower()
        user = os.getenv("DB_USERNAME", "user")
        password = os.getenv("DB_PASSWORD", "password")
        host = os.getenv("DB_HOST", "localhost")
        name = os.getenv("DB_NAME", "fastkit_db")
        port = os.getenv("DB_PORT", "5432")

        if driver == "postgres":
            # ВАЖНО: добавляем +asyncpg
            return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
        elif driver == "sqlite":
            # Для SQLite нужен aiosqlite
            return f"sqlite+aiosqlite:///{name}"

        raise ValueError("Driver not supported for async example")

    def get_session_maker(self):
        return self.session_factory


# Создаем глобальный экземпляр
db_instance = Database()


# Функция получения сессии для Depends()
async def get_db():
    async with db_instance.session_factory() as session:
        yield session