from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from app.infrastructure.tranaslations import current_locale
from app.infrastructure.database.connection import get_database_connection
from app.models.user import Users
from app.models.achievement import Achievement
from app.models.enums import UserStatus, AchievementStatus


class GlobalContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            locale = request.session.get('locale', 'en')
        except AssertionError:
            locale = 'en'
        token = current_locale.set(locale)

        db_conn = get_database_connection()
        db = db_conn.get_session()

        try:
            pending_users = db.query(Users).filter(Users.status == UserStatus.PENDING).count()
            pending_achievements = db.query(Achievement).filter(Achievement.status == AchievementStatus.PENDING).count()

            request.state.app_name = "Sirius Achievements"
            request.state.pending_users_count = pending_users
            request.state.pending_achievements_count = pending_achievements

            response = await call_next(request)
            return response

        finally:
            db.close()
            current_locale.reset(token)


async def auth(request: Request):
    if not request.session.get("auth_id"):
        from fastapi import HTTPException
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            raise HTTPException(status_code=401, detail="Unauthorized")

        from fastapi.responses import RedirectResponse
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})