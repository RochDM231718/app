from sqlalchemy import Column, Integer, String, ForeignKey, Enum as SQLAlchemyEnum, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func  # Импорт func
from app.infrastructure.database.connection import Base
from app.models.enums import AchievementStatus


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    description = Column(String)
    file_path = Column(String)
    status = Column(SQLAlchemyEnum(AchievementStatus), default=AchievementStatus.PENDING)
    rejection_reason = Column(String, nullable=True)

    # Поле для сортировки
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="achievements")