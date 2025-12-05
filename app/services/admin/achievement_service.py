from typing import List
from fastapi import UploadFile
import shutil
from pathlib import Path
import uuid
import os
from datetime import datetime
import aiofiles
import structlog  # Импорт

from app.repositories.admin.achievement_repository import AchievementRepository
from app.models.achievement import Achievement
from app.models.enums import AchievementStatus
from app.schemas.admin.achievements import AchievementCreate

logger = structlog.get_logger()  # Инициализация


class AchievementService:
    def __init__(self, repo: AchievementRepository):
        self.repo = repo

    def get_user_achievements(self, user_id: int, page: int = 1):
        return self.repo.get_by_user(user_id, page)

    async def create(self, user_id: int, obj_in: AchievementCreate, file: UploadFile):
        file_path = await self._save_file(file)

        achievement_data = {
            "user_id": user_id,
            "title": obj_in.title,
            "description": obj_in.description,
            "file_path": file_path,
            "status": AchievementStatus.PENDING,
            "created_at": datetime.now()
        }

        ach = await self.repo.create(achievement_data)
        logger.info("Achievement uploaded", id=ach.id, user_id=user_id, title=ach.title)
        return ach

    async def delete(self, id: int, user_id: int, user_role: str):
        achievement = await self.repo.find(id)

        if not achievement:
            return False

        is_owner = (achievement.user_id == user_id)
        is_admin = (user_role in ['moderator', 'super_admin'])

        if is_owner or is_admin:
            try:
                full_path = Path(achievement.file_path)
                if full_path.exists():
                    full_path.unlink()
            except Exception as e:
                logger.error("Error deleting file", path=achievement.file_path, error=str(e))

            await self.repo.delete(id)
            logger.info("Achievement deleted", id=id, user_id=user_id)
            return True

        logger.warning("Delete achievement denied", id=id, user_id=user_id)
        return False

    async def update_status(self, id: int, status: str, rejection_reason: str = None):
        data = {"status": status}
        if status == "rejected" and rejection_reason:
            data["rejection_reason"] = rejection_reason
        elif status == "approved":
            data["rejection_reason"] = None

        await self.repo.update(id, data)
        logger.info("Achievement status updated", id=id, status=status)

    async def _save_file(self, file: UploadFile) -> str:
        upload_dir = Path("static/uploads/achievements")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_extension = file.filename.split('.')[-1] if '.' in file.filename else "dat"
        unique_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = upload_dir / unique_name

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        return f"static/uploads/achievements/{unique_name}"