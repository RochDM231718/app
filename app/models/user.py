from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLAlchemyEnum, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.infrastructure.database.connection import Base
from app.models.enums import UserRole, UserStatus


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    first_name = Column(String)
    last_name = Column(String)

    # native_enum=False заставляет SQLAlchemy использовать VARCHAR вместо CREATE TYPE
    # Это решает проблему "type ... does not exist" в asyncpg
    role = Column(SQLAlchemyEnum(UserRole, native_enum=False), default=UserRole.GUEST)
    status = Column(SQLAlchemyEnum(UserStatus, native_enum=False), default=UserStatus.PENDING)

    is_active = Column(Boolean, default=True)
    phone_number = Column(String, nullable=True)
    avatar_path = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    achievements = relationship("Achievement", back_populates="user")