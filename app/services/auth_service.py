from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Request
from passlib.context import CryptContext
from app.models.enums import UserTokenType, UserRole, UserStatus
from app.models.user import Users
from app.repositories.admin.user_token_repository import UserTokenRepository
from app.schemas.admin.user_tokens import UserTokenCreate
from app.schemas.admin.auth import RegisterSchema
from app.services.admin.user_token_service import UserTokenService
from app.routers.admin.admin import templates
from mailbridge import MailBridge
from app.infrastructure.jwt_handler import create_access_token, create_refresh_token, refresh_access_token
import os
import structlog

logger = structlog.get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

mailer = MailBridge(provider='smtp',
                    host=os.getenv('MAIL_HOST'),
                    port=os.getenv('MAIL_PORT'),
                    username=os.getenv('MAIL_USERNAME'),
                    password=os.getenv('MAIL_PASSWORD'),
                    use_tls=True,
                    from_email=os.getenv('MAIL_USERNAME')
                    )


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, email: str, password: str, role: str):
        stmt = select(Users).where(Users.email == email)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if not user:
            logger.warning("Login failed: user not found", email=email)
            return None

        if not self.verify_password(password, user.hashed_password):
            logger.warning("Login failed: wrong password", email=email)
            return None

        # Проверка, активен ли пользователь (например, подтверждена ли почта)
        if not user.is_active:
            logger.warning("Login failed: user inactive", email=email)
            return None

        logger.info("User logged in", user_id=user.id, email=user.email, role=user.role.value)
        return user

    async def api_authenticate(self, email: str, password: str, role: str = "User"):
        user = await self.authenticate(email, password, role)
        if not user:
            return None

        token_data = {"sub": str(user.id), "role": user.role.value}

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        }

    # Обновленный метод регистрации
    async def register(self, data: RegisterSchema, request: Request) -> bool:
        stmt = select(Users).where(Users.email == data.email)
        result = await self.db.execute(stmt)
        if result.scalars().first():
            logger.warning("Registration failed: email exists", email=data.email)
            return False

        hashed_pw = pwd_context.hash(data.password)

        new_user = Users(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            hashed_password=hashed_pw,
            role=UserRole.GUEST,
            status=UserStatus.PENDING,
            is_active=False  # Пользователь неактивен до подтверждения почты
        )

        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)  # Получаем ID для создания токена

        # Создание токена подтверждения
        user_token_service = UserTokenService(UserTokenRepository(self.db))
        token_data = UserTokenCreate(user_id=new_user.id, type=UserTokenType.EMAIL_VERIFICATION)
        user_token = await user_token_service.create(data=token_data)

        # Отправка письма (теперь с await)
        try:
            await self._send_verification_email(new_user, user_token, request)
        except Exception as e:
            logger.error("Failed to send verification email", error=str(e))
            # Можно вернуть False или продолжить, но лучше залогировать ошибку

        logger.info("New user registered, verification email sent", email=data.email)
        return True

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    async def user(self, request: Request):
        if 'auth_id' in request.session:
            stmt = select(Users).where(Users.id == request.session['auth_id'])
            result = await self.db.execute(stmt)
            user = result.scalars().first()
            if not user:
                return None
            return user

        return None

    async def reset_password(self, email: str, request: Request) -> bool:
        stmt = select(Users).where(Users.email == email)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if not user:
            return False

        user_token_data = UserTokenCreate(user_id=user.id, type=UserTokenType.RESET_PASSWORD)
        user_token_service = UserTokenService(UserTokenRepository(self.db))
        user_token = await user_token_service.create(data=user_token_data)

        # Отправка письма (теперь с await)
        try:
            await self._send_reset_password_email(user, user_token, request)
            logger.info("Password reset email sent", email=email)
        except Exception as e:
            logger.error("Failed to send reset password email", error=str(e))
            return False

        return True

    # Новый метод для завершения сброса пароля (установка нового)
    async def complete_reset_password(self, token: str, new_password: str) -> bool:
        user_token_service = UserTokenService(UserTokenRepository(self.db))

        try:
            # getResetPasswordToken проверяет тип токена и срок действия
            user_token = await user_token_service.getResetPasswordToken(token)
        except Exception as e:
            logger.warning("Reset password failed: invalid token", token=token, error=str(e))
            raise e

        hashed_pw = pwd_context.hash(new_password)

        stmt = select(Users).where(Users.id == user_token.user_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if user:
            user.hashed_password = hashed_pw
            await self.db.commit()

            # Удаляем токен после использования
            await user_token_service.delete(user_token.id)
            logger.info("Password reset successfully", user_id=user.id)
            return True

        return False

    # Новый метод для подтверждения email
    async def verify_email(self, token: str) -> bool:
        user_token_service = UserTokenService(UserTokenRepository(self.db))
        user_token = await user_token_service.repo.find_by_token(token)

        if not user_token or user_token.type != UserTokenType.EMAIL_VERIFICATION:
            return False

        # Здесь можно добавить проверку expires_at, если необходимо

        stmt = select(Users).where(Users.id == user_token.user_id)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if user:
            user.status = UserStatus.ACTIVE
            user.is_active = True
            await self.db.commit()

            await user_token_service.delete(user_token.id)
            logger.info("Email verified successfully", user_id=user.id)
            return True

        return False

    def api_refresh_token(self, refresh_token: str):
        new_token = refresh_access_token(refresh_token)
        if not new_token:
            return None
        return new_token

    # Метод стал асинхронным и явно управляет соединением
    async def _send_reset_password_email(self, user, user_token, request):
        template = templates.env.get_template('emails/reset_password.html')
        body = template.render({
            'request': request,
            'user': user,
            'url': request.url_for('admin.reset-password.form', token=user_token.token)
        })

        await mailer.connect()
        try:
            await mailer.send(
                to=user.email,
                subject="Reset Password",
                body=body
            )
        finally:
            await mailer.close()

    # Метод стал асинхронным и явно управляет соединением
    async def _send_verification_email(self, user, user_token, request):
        # Убедитесь, что шаблон templates/admin/emails/verify_email.html существует
        template = templates.env.get_template('emails/verify_email.html')
        url = request.url_for('admin.auth.verify_email', token=user_token.token)

        body = template.render({
            'request': request,
            'user': user,
            'url': url
        })

        await mailer.connect()
        try:
            await mailer.send(
                to=user.email,
                subject="Verify your account",
                body=body
            )
        finally:
            await mailer.close()