import uuid
from typing import List
from fastapi import UploadFile
import shutil
from pathlib import Path
from app.schemas.admin.users import UserCreate, UserUpdate, UserOut
from app.schemas.admin.user_tokens import UserTokenCreate, UserTokenType
from app.services.admin.base_crud_service import BaseCrudService, ModelType, CreateSchemaType
from app.services.admin.user_token_service import UserTokenService
from app.repositories.admin.user_repository import UserRepository
from app.repositories.admin.user_token_repository import UserTokenRepository
from app.models.user import Users
from passlib.context import CryptContext
from mailbridge import MailBridge
from app.routers.admin.admin import templates
from starlette.requests import Request
import secrets
import string
import os
import re  # <-- Добавили RE для проверки паролей
from app.models.enums import UserStatus, UserRole

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
mailer = MailBridge(provider='smtp',
                    host=os.getenv('MAIL_HOST'),
                    port=os.getenv('MAIL_PORT'),
                    username=os.getenv('MAIL_USERNAME'),
                    password=os.getenv('MAIL_PASSWORD'),
                    use_tls=True,
                    from_email=os.getenv('MAIL_USERNAME')
                    )


class UserService(BaseCrudService[Users, UserCreate, UserUpdate]):
    def __init__(self, repo: UserRepository):
        super().__init__(repo)
        self.request = None

    def set_request(self, request: Request):
        self.request = request

    def get(self, filters: dict = None) -> List[ModelType]:
        users = super().get(filters)
        return [UserOut.model_validate(user) for user in users]

    def create(self, obj_in: CreateSchemaType) -> ModelType:
        # Логика создания АДМИНОМ (генерирует пароль)
        result = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
        obj_in.hashed_password = bcrypt_context.hash(result)
        user = self.repository.create(obj_in)
        user_token = self._create_user_token_for_reset_password(user_id=user.id)
        self._send_welcome_email(user, result, user_token)
        return user

    # --- МЕТОД РЕГИСТРАЦИИ (С ВАЛИДАЦИЕЙ ПАРОЛЯ) ---
    def register_user(self, first_name: str, last_name: str, email: str, password: str) -> Users:
        """
        Регистрирует студента. Проверяет уникальность Email и сложность пароля.
        """

        # 1. Проверка сложности пароля
        if len(password) < 8:
            raise ValueError("admin.auth.password_too_short")
        if not re.search(r"[A-Z]", password):
            raise ValueError("admin.auth.password_no_upper")
        if not re.search(r"[a-z]", password):
            raise ValueError("admin.auth.password_no_lower")
        if not re.search(r"\d", password):
            raise ValueError("admin.auth.password_no_digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValueError("admin.auth.password_no_special")

        # 2. Проверка уникальности Email
        if self.repository.getDb().query(Users).filter(Users.email == email).first():
            raise ValueError("admin.auth.email_registered")

        # 3. Создание пользователя
        new_user = Users(
            first_name=first_name,
            last_name=last_name,
            email=email,
            hashed_password=bcrypt_context.hash(password),
            role=UserRole.STUDENT,
            status=UserStatus.PENDING,
            is_active=True
        )

        self.repository.db.add(new_user)
        self.repository.db.commit()

        return new_user

    # -------------------------------------------------

    def update_password(self, id: str, password: str):
        self.repository.update_password(id, bcrypt_context.hash(password))

    def delete(self, id: int) -> bool:
        user = self.repository.find(id)
        if not user:
            return False

        self.repository.update(id, {
            "status": "deleted",
            "is_active": False
        })
        return True

    def force_delete(self, id: int) -> bool:
        return self.repository.hard_delete(id)

    def reject_registration(self, user_id: int):
        self.repository.update(user_id, {
            "status": "rejected",
            "is_active": False
        })

    def save_avatar(self, user_id: int, file: UploadFile) -> str:
        upload_dir = Path("static/uploads/avatars")
        upload_dir.mkdir(parents=True, exist_ok=True)

        filename_parts = file.filename.split('.')
        file_extension = filename_parts[-1] if len(filename_parts) > 1 else "png"

        unique_code = uuid.uuid4().hex[:8]
        filename = f"avatar_{user_id}_{unique_code}.{file_extension}"
        file_path = upload_dir / filename

        for old_file in upload_dir.glob(f"avatar_{user_id}_*"):
            try:
                old_file.unlink()
            except:
                pass

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return f"static/uploads/avatars/{filename}"

    def get_pending_users(self):
        return self.repository.getDb().query(Users).filter(Users.status == UserStatus.PENDING).all()

    def approve_user(self, user_id: int):
        self.repository.update(user_id, {
            "status": UserStatus.ACTIVE,
            "role": UserRole.STUDENT
        })

    def _create_user_token_for_reset_password(self, user_id: int):
        user_token_data = UserTokenCreate(user_id=user_id, type=UserTokenType.RESET_PASSWORD)
        user_token_service = UserTokenService(UserTokenRepository(self.repository.getDb()))
        return user_token_service.create(data=user_token_data)

    def _send_welcome_email(self, user, password: str, user_token):
        template = templates.env.get_template('emails/welcome.html')
        mailer.send(to=user.email,
                    subject="Welcome",
                    body=template.render({
                        'request': self.request,
                        'user': user,
                        'password': password,
                        'url': self.request.url_for('admin.reset-password.form', token=user_token.token)
                    }))