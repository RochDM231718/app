from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload  # <-- ВАЖНО
from app.routers.admin.admin import guard_router, templates, get_db
from app.repositories.admin.user_repository import UserRepository
from app.repositories.admin.achievement_repository import AchievementRepository
from app.services.admin.user_service import UserService
from app.services.admin.achievement_service import AchievementService
from app.models.user import Users
from app.models.achievement import Achievement
from app.models.enums import UserStatus, AchievementStatus, UserRole
from app.infrastructure.tranaslations import TranslationManager

router = guard_router


def get_user_service(db: AsyncSession = Depends(get_db)):
    return UserService(UserRepository(db))


def get_achievement_service(db: AsyncSession = Depends(get_db)):
    return AchievementService(AchievementRepository(db))


def check_moderator(request: Request):
    role = request.session.get('auth_role')
    if role not in [UserRole.MODERATOR, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get('/moderation/users', response_class=HTMLResponse, name='admin.moderation.users')
async def pending_users(request: Request, db: AsyncSession = Depends(get_db)):
    check_moderator(request)

    stmt = select(Users).filter(Users.status == UserStatus.PENDING).order_by(Users.id.desc())
    result = await db.execute(stmt)
    users = result.scalars().all()

    total_count = len(users)
    return templates.TemplateResponse('moderation/users.html',
                                      {'request': request, 'users': users, 'total_count': total_count})


@router.post('/moderation/users/{id}/approve', name='admin.moderation.users.approve')
async def approve_user(id: int, request: Request, service: UserService = Depends(get_user_service)):
    check_moderator(request)
    await service.repository.update(id, {"status": UserStatus.ACTIVE})

    translator = TranslationManager()
    url = request.url_for('admin.moderation.users').include_query_params(
        toast_msg=translator.gettext("admin.toast.user_approved"), toast_type="success")
    return RedirectResponse(url=url, status_code=302)


@router.post('/moderation/users/{id}/reject', name='admin.moderation.users.reject')
async def reject_user(id: int, request: Request, service: UserService = Depends(get_user_service)):
    check_moderator(request)
    await service.repository.update(id, {"status": UserStatus.REJECTED})

    translator = TranslationManager()
    url = request.url_for('admin.moderation.users').include_query_params(
        toast_msg=translator.gettext("admin.toast.user_rejected"), toast_type="success")
    return RedirectResponse(url=url, status_code=302)


@router.get('/moderation/achievements', response_class=HTMLResponse, name='admin.moderation.achievements')
async def pending_achievements(request: Request, db: AsyncSession = Depends(get_db)):
    check_moderator(request)

    stmt = select(Achievement).options(selectinload(Achievement.user)).filter(
        Achievement.status == AchievementStatus.PENDING).order_by(Achievement.created_at.desc())
    result = await db.execute(stmt)
    achievements = result.scalars().all()

    total_count = len(achievements)
    return templates.TemplateResponse('moderation/achievements.html',
                                      {'request': request, 'achievements': achievements, 'total_count': total_count})


@router.post('/moderation/achievements/{id}', name='admin.moderation.achievements.update')
async def update_achievement_status(
        id: int,
        request: Request,
        status: str = Form(...),
        rejection_reason: str = Form(None),
        service: AchievementService = Depends(get_achievement_service)
):
    check_moderator(request)

    data = {"status": status}
    if status == "rejected" and rejection_reason:
        data["rejection_reason"] = rejection_reason
    elif status == "approved":
        data["rejection_reason"] = None

    await service.repo.update(id, data)

    translator = TranslationManager()
    msg = translator.gettext("admin.toast.approved") if status == 'approved' else translator.gettext(
        "admin.toast.rejected")
    url = request.url_for('admin.moderation.achievements').include_query_params(toast_msg=msg, toast_type="success")
    return RedirectResponse(url=url, status_code=302)