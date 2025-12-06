from app.repositories.admin.user_repository import UserRepository
from app.schemas.admin.users import UserCreate
from app.models.enums import UserRole, UserStatus
from fastapi import UploadFile, Request
from pathlib import Path
import uuid
from passlib.context import CryptContext
import structlog  # Импорт

logger = structlog.get_logger()  # Инициализация
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo
        self.request = None

    def set_request(self, request: Request):
        self.request = request

    @property
    def repository(self):
        return self.repo

    async def find(self, id: int):
        return await self.repo.find(id)

    async def create(self, user_data: UserCreate):
        user_dict = user_data.dict()
        if 'password' in user_dict:
            user_dict['hashed_password'] = pwd_context.hash(user_dict.pop('password'))

        user = await self.repo.create(user_dict)
        logger.info("User created via admin", user_id=user.id, email=user.email)
        return user

    async def register_user(self, first_name, last_name, email, password):
        existing = await self.repo.get(filters={'email': email})
        if existing:
            logger.warning("Register failed: duplicate email", email=email)
            raise ValueError("admin.auth.email_registered")

        hashed_pw = pwd_context.hash(password)

        new_user_data = {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "hashed_password": hashed_pw,
            "role": UserRole.GUEST,
            "status": UserStatus.PENDING,
            "is_active": True
        }

        user = await self.repo.create(new_user_data)
        logger.info("User registered", user_id=user.id, email=email)
        return user

    async def save_avatar(self, user_id: int, file: UploadFile) -> str:
        upload_dir = Path("static/uploads/avatars")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_extension = file.filename.split('.')[-1] if '.' in file.filename else "png"
        unique_name = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
        file_path = upload_dir / unique_name

        content = await file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)

        logger.info("Avatar uploaded", user_id=user_id, path=str(file_path))
        return f"static/uploads/avatars/{unique_name}"

    async def delete(self, id: int):
        logger.info("User soft deleted", user_id=id)
        return await self.repo.update(id, {"status": UserStatus.DELETED})

    async def force_delete(self, id: int):
        user = await self.find(id)
        if user and user.avatar_path:
            try:
                Path(user.avatar_path).unlink(missing_ok=True)
            except Exception:
                pass

        logger.info("User permanently deleted", user_id=id)
        return await self.repo.delete(id)