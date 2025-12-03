from fastapi import Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, asc, desc
from typing import Optional
from app.routers.admin.admin import guard_router, templates, get_db
from app.models.achievement import Achievement
from app.models.user import Users
from app.models.enums import UserRole, AchievementStatus
from app.services.admin.achievement_service import AchievementService
from app.repositories.admin.achievement_repository import AchievementRepository
from app.infrastructure.tranaslations import TranslationManager

router = guard_router


def get_achievement_service(db: Session = Depends(get_db)):
    return AchievementService(AchievementRepository(db))


def check_access(request: Request):
    role = request.session.get('auth_role')
    if role not in [UserRole.MODERATOR, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get('/pages/search', response_class=JSONResponse, name='admin.pages.search_api')
async def search_documents(request: Request, query: str, status: Optional[str] = None, db: Session = Depends(get_db)):
    check_access(request)
    if not query: return []
    base_query = db.query(Achievement).join(Users)
    base_query = base_query.filter(or_(Achievement.title.ilike(f"%{query}%"), Users.first_name.ilike(f"%{query}%"),
                                       Users.last_name.ilike(f"%{query}%"), Users.email.ilike(f"%{query}%")))
    if status: base_query = base_query.filter(Achievement.status == status)
    documents = base_query.limit(10).all()
    return [{"id": doc.user_id, "title": doc.title, "user": f"{doc.user.first_name} {doc.user.last_name}",
             "status": doc.status.value} for doc in documents]


@router.get('/pages', response_class=HTMLResponse, name="admin.pages.index")
async def index(request: Request, query: Optional[str] = "", status: Optional[str] = None,
                sort: Optional[str] = "created_at", order: Optional[str] = "desc", db: Session = Depends(get_db)):
    check_access(request)
    base_query = db.query(Achievement).join(Users)
    if query: base_query = base_query.filter(
        or_(Achievement.title.ilike(f"%{query}%"), Users.first_name.ilike(f"%{query}%"),
            Users.last_name.ilike(f"%{query}%")))
    if status: base_query = base_query.filter(Achievement.status == status)
    if hasattr(Achievement, sort):
        field = getattr(Achievement, sort)
        base_query = base_query.order_by(asc(field) if order == 'asc' else desc(field))
    else:
        base_query = base_query.order_by(desc(Achievement.created_at))

    total_count = base_query.count()
    documents = base_query.limit(50).all()
    return templates.TemplateResponse('pages/index.html', {'request': request, 'query': query, 'documents': documents,
                                                           'total_count': total_count, 'selected_status': status,
                                                           'statuses': list(AchievementStatus), 'current_sort': sort,
                                                           'current_order': order})


@router.post('/pages/{id}/delete', name='admin.pages.delete')
async def delete_document(id: int, request: Request, service: AchievementService = Depends(get_achievement_service)):
    check_access(request)
    user_id = request.session['auth_id']
    user_role = request.session.get('auth_role')
    service.delete(id, user_id, user_role)

    locale = request.session.get('locale', 'en')
    translator = TranslationManager()

    # Исправлен вызов (kwargs поддерживаются в файле 1)
    url = request.url_for('admin.pages.index').include_query_params(
        toast_msg=translator.gettext("admin.toast.deleted", locale=locale),
        toast_type="success"
    )
    return RedirectResponse(url=url, status_code=302)