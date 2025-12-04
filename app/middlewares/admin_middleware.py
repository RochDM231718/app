from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from sqlalchemy import select, func
from app.infrastructure.tranaslations import current_locale
from app.infrastructure.database.connection import db_instance  # Импортируем глобальный объект Database
from app.models.user import Users
from app.models.achievement import Achievement
from app.models.enums import UserStatus, AchievementStatus


class GlobalContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Получаем локаль
        try:
            locale = request.session.get('locale', 'en')
        except AssertionError:
            locale = 'en'

        # Устанавливаем контекстную переменную
        token = current_locale.set(locale)

        # 2. Получаем асинхронную сессию вручную
        # Так как мы в middleware, Dependency Injection здесь не работает стандартным образом
        async with db_instance.session_factory() as db:
            try:
                # Асинхронный подсчет пользователей (PENDING)
                query_users = select(func.count()).select_from(Users).where(Users.status == UserStatus.PENDING)
                result_users = await db.execute(query_users)
                pending_users = result_users.scalar()

                # Асинхронный подсчет документов (PENDING)
                query_ach = select(func.count()).select_from(Achievement).where(
                    Achievement.status == AchievementStatus.PENDING)
                result_ach = await db.execute(query_ach)
                pending_achievements = result_ach.scalar()

                # Сохраняем в state для использования в шаблонах (layout.html)
                request.state.app_name = "Sirius Achievements"
                request.state.pending_users_count = pending_users
                request.state.pending_achievements_count = pending_achievements

            except Exception as e:
                print(f"Middleware DB Error: {e}")
                # Если ошибка БД, ставим нули, чтобы админка открылась
                request.state.pending_users_count = 0
                request.state.pending_achievements_count = 0

            # Продолжаем обработку запроса
            response = await call_next(request)

            # Сбрасываем контекст локали после запроса
            current_locale.reset(token)

            return response


async def auth(request: Request):
    """
    Проверка авторизации для защищенных роутов.
    Если пользователь не авторизован - редирект на логин.
    """
    if not request.session.get("auth_id"):
        from fastapi import HTTPException

        # Если это AJAX запрос, возвращаем 401 вместо редиректа
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Иначе редирект
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})