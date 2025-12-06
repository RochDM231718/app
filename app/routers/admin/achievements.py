from fastapi import Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.routers.admin.admin import guard_router, templates, get_db
from app.repositories.admin.achievement_repository import AchievementRepository
from app.services.admin.achievement_service import AchievementService
from app.schemas.admin.achievements import AchievementCreate
from app.models.achievement import Achievement
from app.infrastructure.tranaslations import TranslationManager

router = guard_router


def get_service(db: AsyncSession = Depends(get_db)):
    return AchievementService(AchievementRepository(db))


@router.get('/achievements', response_class=HTMLResponse, name="admin.achievements.index")
async def index(request: Request, page: int = 1, service: AchievementService = Depends(get_service),
                db: AsyncSession = Depends(get_db)):
    current_user_id = request.session['auth_id']

    achievements = await service.get_user_achievements(current_user_id, page)

    stmt = select(func.count()).select_from(Achievement).filter(Achievement.user_id == current_user_id)
    result = await db.execute(stmt)
    total_count = result.scalar()

    return templates.TemplateResponse('achievements/index.html',
                                      {'request': request, 'achievements': achievements, 'total_count': total_count})


@router.get('/achievements/create', response_class=HTMLResponse, name='admin.achievements.create')
async def create(request: Request):
    return templates.TemplateResponse('achievements/create.html', {'request': request})


@router.post('/achievements', response_class=HTMLResponse, name='admin.achievements.store')
async def store(request: Request, title: str = Form(...), description: str = Form(None), file: UploadFile = File(...),
                service: AchievementService = Depends(get_service)):
    try:
        user_id = request.session['auth_id']
        achievement_data = AchievementCreate(title=title, description=description)

        await service.create(user_id, achievement_data, file)

        translator = TranslationManager()
        locale = request.session.get('locale', 'en')
        url = request.url_for('admin.achievements.index').include_query_params(
            toast_msg=translator.gettext("admin.toast.achievement_uploaded", locale=locale), toast_type="success")
        return RedirectResponse(url=url, status_code=302)
    except Exception as e:
        return templates.TemplateResponse('achievements/create.html',
                                          {'request': request, 'error_msg': f"Error uploading: {str(e)}"})


@router.post('/achievements/{id}/delete', name='admin.achievements.delete')
async def delete(id: int, request: Request, service: AchievementService = Depends(get_service)):
    user_id = request.session['auth_id']
    user_role = request.session.get('auth_role', 'guest')

    await service.delete(id, user_id, user_role)

    translator = TranslationManager()
    locale = request.session.get('locale', 'en')
    url = request.url_for('admin.achievements.index').include_query_params(
        toast_msg=translator.gettext("admin.toast.achievement_deleted", locale=locale), toast_type="success")
    return RedirectResponse(url=url, status_code=302)