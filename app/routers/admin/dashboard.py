from fastapi import Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta
from app.routers.admin.admin import guard_router, templates, get_db
from app.models.user import Users
from app.models.achievement import Achievement
from app.models.enums import UserRole, UserStatus, AchievementStatus

router = guard_router


@router.get('/dashboard', response_class=HTMLResponse, name='admin.dashboard')
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    auth_role = request.session.get('auth_role')
    auth_id = request.session.get('auth_id')

    stats = {}
    chart_data = {}

    if auth_role in [UserRole.SUPER_ADMIN, UserRole.MODERATOR]:
        # --- Асинхронные запросы для статистики администратора ---

        # 1. Пользователи
        # Total
        res = await db.execute(select(func.count()).select_from(Users))
        stats['users_total'] = res.scalar()

        # Active
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.ACTIVE))
        stats['users_active'] = res.scalar()

        # Pending
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.PENDING))
        stats['users_pending'] = res.scalar()

        # Rejected
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.REJECTED))
        stats['users_rejected'] = res.scalar()

        # Deleted
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.DELETED))
        stats['users_deleted'] = res.scalar()

        # 2. Документы
        # Total
        res = await db.execute(select(func.count()).select_from(Achievement))
        stats['docs_total'] = res.scalar()

        # Pending
        res = await db.execute(
            select(func.count()).select_from(Achievement).where(Achievement.status == AchievementStatus.PENDING))
        stats['docs_pending'] = res.scalar()

        # Approved
        res = await db.execute(
            select(func.count()).select_from(Achievement).where(Achievement.status == AchievementStatus.APPROVED))
        stats['docs_approved'] = res.scalar()

        # Rejected
        res = await db.execute(
            select(func.count()).select_from(Achievement).where(Achievement.status == AchievementStatus.REJECTED))
        stats['docs_rejected'] = res.scalar()

        # 3. Данные для графика (за последние 7 дней)
        today = datetime.now()
        seven_days_ago = today - timedelta(days=6)

        # Асинхронно получаем пользователей за неделю
        stmt = select(Users).where(Users.created_at >= seven_days_ago)
        result = await db.execute(stmt)
        recent_users = result.scalars().all()

        # Группировка данных (Python-side)
        daily_counts = {}
        date_labels = []

        # Заполняем дни нулями
        for i in range(7):
            day = (seven_days_ago + timedelta(days=i)).strftime("%Y-%m-%d")
            daily_counts[day] = 0
            date_labels.append(day)

        # Считаем реальные регистрации
        for user in recent_users:
            if user.created_at:
                day = user.created_at.strftime("%Y-%m-%d")
                if day in daily_counts:
                    daily_counts[day] += 1

        chart_data = {
            "labels": date_labels,
            "data": [daily_counts[lbl] for lbl in date_labels]
        }

    else:
        # --- Асинхронная статистика студента ---

        # My Total
        res = await db.execute(select(func.count()).select_from(Achievement).where(Achievement.user_id == auth_id))
        stats['my_total'] = res.scalar()

        # My Approved
        res = await db.execute(select(func.count()).select_from(Achievement).where(
            Achievement.user_id == auth_id,
            Achievement.status == AchievementStatus.APPROVED
        ))
        stats['my_approved'] = res.scalar()

        # My Pending
        res = await db.execute(select(func.count()).select_from(Achievement).where(
            Achievement.user_id == auth_id,
            Achievement.status == AchievementStatus.PENDING
        ))
        stats['my_pending'] = res.scalar()

        # My Rejected
        res = await db.execute(select(func.count()).select_from(Achievement).where(
            Achievement.user_id == auth_id,
            Achievement.status == AchievementStatus.REJECTED
        ))
        stats['my_rejected'] = res.scalar()

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'stats': stats,
        'chart_data': chart_data
    })