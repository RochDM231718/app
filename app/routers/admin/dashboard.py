from fastapi import Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.routers.admin.admin import guard_router, templates, get_db
from app.models.user import Users
from app.models.achievement import Achievement
from app.models.enums import UserRole, UserStatus, AchievementStatus

router = guard_router


@router.get('/dashboard', response_class=HTMLResponse, name='admin.dashboard')
async def dashboard(request: Request, db: Session = Depends(get_db)):
    auth_role = request.session.get('auth_role')
    auth_id = request.session.get('auth_id')

    stats = {}
    chart_data = {}

    if auth_role in [UserRole.SUPER_ADMIN, UserRole.MODERATOR]:
        # Общая статистика
        stats['users_total'] = db.query(Users).count()
        stats['users_active'] = db.query(Users).filter(Users.status == UserStatus.ACTIVE).count()
        stats['users_pending'] = db.query(Users).filter(Users.status == UserStatus.PENDING).count()
        stats['users_rejected'] = db.query(Users).filter(Users.status == UserStatus.REJECTED).count()
        stats['users_deleted'] = db.query(Users).filter(Users.status == UserStatus.DELETED).count()

        stats['docs_total'] = db.query(Achievement).count()
        stats['docs_pending'] = db.query(Achievement).filter(Achievement.status == AchievementStatus.PENDING).count()
        stats['docs_approved'] = db.query(Achievement).filter(Achievement.status == AchievementStatus.APPROVED).count()
        stats['docs_rejected'] = db.query(Achievement).filter(Achievement.status == AchievementStatus.REJECTED).count()

        # [ГРАФИК] Подготовка данных за последние 7 дней
        today = datetime.now()
        seven_days_ago = today - timedelta(days=6)

        # Получаем всех пользователей за неделю
        recent_users = db.query(Users).filter(Users.created_at >= seven_days_ago).all()

        # Группируем по дням (Python-side для кросс-базовой совместимости)
        daily_counts = {}
        date_labels = []

        # Инициализируем нулями
        for i in range(7):
            day = (seven_days_ago + timedelta(days=i)).strftime("%Y-%m-%d")
            daily_counts[day] = 0
            date_labels.append(day)

        # Считаем
        for user in recent_users:
            # Предполагаем, что created_at есть в модели (если нет - добавьте или используйте id)
            if hasattr(user, 'created_at') and user.created_at:
                day = user.created_at.strftime("%Y-%m-%d")
                if day in daily_counts:
                    daily_counts[day] += 1

        chart_data = {
            "labels": date_labels,
            "data": [daily_counts[lbl] for lbl in date_labels]
        }

    else:
        # Статистика студента
        stats['my_total'] = db.query(Achievement).filter(Achievement.user_id == auth_id).count()
        stats['my_approved'] = db.query(Achievement).filter(
            Achievement.user_id == auth_id,
            Achievement.status == AchievementStatus.APPROVED
        ).count()
        stats['my_pending'] = db.query(Achievement).filter(
            Achievement.user_id == auth_id,
            Achievement.status == AchievementStatus.PENDING
        ).count()
        stats['my_rejected'] = db.query(Achievement).filter(
            Achievement.user_id == auth_id,
            Achievement.status == AchievementStatus.REJECTED
        ).count()

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'stats': stats,
        'chart_data': chart_data  # Передаем данные для графика
    })