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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Инициализацию mailer можно оставить глобальной
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
        # Асинхронный запрос
        stmt = select(Users).where(Users.email == email)
        result = await self.db.execute(stmt)
        user = result.scalars().first()

        if not user:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

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

    async def register(self, data: RegisterSchema) -> bool:
        stmt = select(Users).where(Users.email == data.email)
        result = await self.db.execute(stmt)
        if result.scalars().first():
            return False

        hashed_pw = pwd_context.hash(data.password)

        new_user = Users(
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            hashed_password=hashed_pw,
            role=UserRole.GUEST,
            status=UserStatus.PENDING,
            is_active=True
        )

        self.db.add(new_user)
        await self.db.commit()
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
        # Передаем асинхронную сессию в репозиторий
        user_token_service = UserTokenService(UserTokenRepository(self.db))
        # Важно: если create в UserTokenService стал async, тут нужен await
        user_token = await user_token_service.create(data=user_token_data)

        self._send_reset_password_email(user, user_token, request)

        return True

    def api_refresh_token(self, refresh_token: str):
        new_token = refresh_access_token(refresh_token)
        if not new_token:
            return None
        return new_token

    def _send_reset_password_email(self, user, user_token, request):
        template = templates.env.get_template('emails/reset_password.html')
        mailer.send(to=user.email,
                    subject="Reset Password",
                    body=template.render({
                        'request': request,
                        'user': user,
                        'url': request.url_for('admin.reset-password.form', token=user_token.token)
                    }))