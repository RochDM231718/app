from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.infrastructure.database.connection import Base
from app.models.enums import UserTokenType


class UserToken(Base):
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    token = Column(String, unique=True, nullable=False)
    type = Column(Enum(UserTokenType, name="user_token_type"), nullable=False)

    # Изменено: добавлено timezone=True для соответствия типу TIMESTAMP WITH TIME ZONE в БД
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Изменено: timezone=True и безопасное создание времени UTC (aware datetime)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("Users")