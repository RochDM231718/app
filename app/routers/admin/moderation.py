from fastapi import Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.routers.admin.admin import guard_router, templates, get_db
from app.repositories.admin.user_repository import UserRepository
from app.services.admin.user_service import UserService
from app.repositories.admin.achievement_repository import AchievementRepository
from app.services.admin.achievement_service import AchievementService
from app.models.user import Users
from app.models.enums import UserRole
from app.infrastructure.tranaslations import TranslationManager

router = guard_router


def get_user_service(db: Session = Depends(get_db)):
    return UserService(UserRepository(db))


def get_achievement_service(db: Session = Depends(get_db)):
    return AchievementService(AchievementRepository(db))


async def ensure_moderator(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get('auth_id')
    if not user_id: raise HTTPException(status_code=403, detail="Not authenticated")
    user = db.query(Users).get(user_id)
    if not user: raise HTTPException(status_code=403, detail="User not found")
    if user.role not in [UserRole.MODERATOR, UserRole.SUPER_ADMIN]: raise HTTPException(status_code=403,
                                                                                        detail="Access denied")
    return user


@router.get('/moderation/users', response_class=HTMLResponse, name='admin.moderation.users')
async def pending_users(request: Request, service: UserService = Depends(get_user_service),
                        admin=Depends(ensure_moderator)):
    users = service.get_pending_users()
    total_count = len(users) if users else 0
    return templates.TemplateResponse('moderation/users.html',
                                      {'request': request, 'users': users, 'total_count': total_count})


@router.post('/moderation/users/{id}/approve', name='admin.moderation.users.approve')
async def approve_user(id: int, request: Request, service: UserService = Depends(get_user_service),
                       admin=Depends(ensure_moderator)):
    service.approve_user(id)

    translator = TranslationManager()
    url = request.url_for('admin.moderation.users').include_query_params(
        toast_msg=translator.gettext("admin.toast.user_approved"), toast_type="success")
    return RedirectResponse(url=url, status_code=302)


@router.post('/moderation/users/{id}/reject', name='admin.moderation.users.reject')
async def reject_user(id: int, request: Request, service: UserService = Depends(get_user_service),
                      admin=Depends(ensure_moderator)):
    service.reject_registration(id)

    translator = TranslationManager()
    url = request.url_for('admin.moderation.users').include_query_params(
        toast_msg=translator.gettext("admin.toast.user_rejected"), toast_type="success")
    return RedirectResponse(url=url, status_code=302)


@router.get('/moderation/achievements', response_class=HTMLResponse, name='admin.moderation.achievements')
async def pending_achievements(request: Request, service: AchievementService = Depends(get_achievement_service),
                               admin=Depends(ensure_moderator)):
    achievements = service.get_all_pending()
    total_count = len(achievements) if achievements else 0
    return templates.TemplateResponse('moderation/achievements.html',
                                      {'request': request, 'achievements': achievements, 'total_count': total_count})


@router.post('/moderation/achievements/{id}/update', name='admin.moderation.achievements.update')
async def update_achievement_status(id: int, request: Request, status: str = Form(...),
                                    rejection_reason: Optional[str] = Form(None),
                                    service: AchievementService = Depends(get_achievement_service),
                                    admin=Depends(ensure_moderator)):
    service.update_status(id, status, rejection_reason)

    translator = TranslationManager()
    msg = translator.gettext("admin.toast.approved") if status == 'approved' else translator.gettext(
        "admin.toast.rejected")
    url = request.url_for('admin.moderation.achievements').include_query_params(toast_msg=msg, toast_type="success")
    return RedirectResponse(url=url, status_code=302)