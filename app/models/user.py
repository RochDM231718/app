from sqlalchemy import Column, Integer, String, Boolean, Enum as SQLAlchemyEnum, DateTime  # <-- Добавлен DateTime
from sqlalchemy.sql import func  # <-- Добавлен func
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
    role = Column(SQLAlchemyEnum(UserRole), default=UserRole.GUEST)
    status = Column(SQLAlchemyEnum(UserStatus), default=UserStatus.PENDING)
    is_active = Column(Boolean, default=True)
    phone_number = Column(String, nullable=True)
    avatar_path = Column(String, nullable=True)

    # НОВОЕ ПОЛЕ
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    achievements = relationship("Achievement", back_populates="user")