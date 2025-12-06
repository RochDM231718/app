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


async def get_chart_data(db: AsyncSession, model, period: str):
    """
    Универсальная функция для генерации данных графика по периодам
    """
    now = datetime.now()
    labels = []
    counts = {}
    start_date = now

    if period == 'day':
        # Последние 24 часа
        start_date = now - timedelta(hours=24)
        date_format = "%H:00"

        current = start_date
        while current <= now:
            label = current.strftime(date_format)
            if label not in labels:
                labels.append(label)
                counts[label] = 0
            current += timedelta(hours=1)

    elif period == 'month':
        # Последние 30 дней
        start_date = now - timedelta(days=30)
        date_format = "%d.%m"

        current = start_date
        while current <= now:
            label = current.strftime(date_format)
            if label not in labels:
                labels.append(label)
                counts[label] = 0
            current += timedelta(days=1)

    elif period == 'all':
        # Последние 12 месяцев (включая текущий)
        # Устанавливаем начало на 1-е число 11 месяцев назад
        start_date = (now.replace(day=1) - timedelta(days=365)).replace(day=1)
        date_format = "%Y-%m"

        current = start_date
        # Итерируемся по месяцам до текущего момента
        while current <= now or current.strftime("%Y-%m") == now.strftime("%Y-%m"):
            label = current.strftime(date_format)
            if label not in labels:
                labels.append(label)
                counts[label] = 0

            # Переход на следующий месяц: добавляем 32 дня и сбрасываем на 1-е число
            # Это надежный способ получить следующий месяц без dateutil
            next_month = (current + timedelta(days=32)).replace(day=1)
            current = next_month

            # Защита от бесконечного цикла (на всякий случай)
            if len(labels) > 24: break

    else:  # 'week' по умолчанию
        start_date = now - timedelta(days=6)
        date_format = "%Y-%m-%d"

        current = start_date
        while current <= now:
            label = current.strftime(date_format)
            if label not in labels:
                labels.append(label)
                counts[label] = 0
            current += timedelta(days=1)

    # Запрос к БД
    stmt = select(model).where(model.created_at >= start_date)
    result = await db.execute(stmt)
    items = result.scalars().all()

    # Группировка данных
    for item in items:
        if item.created_at:
            key = item.created_at.strftime(date_format)

            # Прямое совпадение
            if key in counts:
                counts[key] += 1
            # Для 'all' проверяем месяц, если день не совпал (хотя формат %Y-%m уже это делает)
            elif period == 'all':
                month_key = item.created_at.strftime("%Y-%m")
                if month_key in counts:
                    counts[month_key] += 1

    return {
        "labels": labels,
        "data": [counts[lbl] for lbl in labels]
    }


@router.get('/dashboard', response_class=HTMLResponse, name='admin.dashboard')
async def dashboard(request: Request, period: str = 'week', db: AsyncSession = Depends(get_db)):
    auth_role = request.session.get('auth_role')
    auth_id = request.session.get('auth_id')

    stats = {}
    users_chart = {}
    docs_chart = {}

    if auth_role in [UserRole.SUPER_ADMIN, UserRole.MODERATOR]:
        # --- Статистика ---
        res = await db.execute(select(func.count()).select_from(Users))
        stats['users_total'] = res.scalar()
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.ACTIVE))
        stats['users_active'] = res.scalar()
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.PENDING))
        stats['users_pending'] = res.scalar()
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.REJECTED))
        stats['users_rejected'] = res.scalar()
        res = await db.execute(select(func.count()).select_from(Users).where(Users.status == UserStatus.DELETED))
        stats['users_deleted'] = res.scalar()

        res = await db.execute(select(func.count()).select_from(Achievement))
        stats['docs_total'] = res.scalar()
        res = await db.execute(
            select(func.count()).select_from(Achievement).where(Achievement.status == AchievementStatus.PENDING))
        stats['docs_pending'] = res.scalar()
        res = await db.execute(
            select(func.count()).select_from(Achievement).where(Achievement.status == AchievementStatus.APPROVED))
        stats['docs_approved'] = res.scalar()
        res = await db.execute(
            select(func.count()).select_from(Achievement).where(Achievement.status == AchievementStatus.REJECTED))
        stats['docs_rejected'] = res.scalar()

        # --- Графики ---
        users_chart = await get_chart_data(db, Users, period)
        docs_chart = await get_chart_data(db, Achievement, period)

    else:
        # Студент
        res = await db.execute(select(func.count()).select_from(Achievement).where(Achievement.user_id == auth_id))
        stats['my_total'] = res.scalar()
        res = await db.execute(select(func.count()).select_from(Achievement).where(Achievement.user_id == auth_id,
                                                                                   Achievement.status == AchievementStatus.APPROVED))
        stats['my_approved'] = res.scalar()
        res = await db.execute(select(func.count()).select_from(Achievement).where(Achievement.user_id == auth_id,
                                                                                   Achievement.status == AchievementStatus.PENDING))
        stats['my_pending'] = res.scalar()
        res = await db.execute(select(func.count()).select_from(Achievement).where(Achievement.user_id == auth_id,
                                                                                   Achievement.status == AchievementStatus.REJECTED))
        stats['my_rejected'] = res.scalar()

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'stats': stats,
        'users_chart': users_chart,
        'docs_chart': docs_chart,
        'current_period': period
    })