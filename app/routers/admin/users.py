from fastapi import Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload  # <-- ВАЖНО

from app.routers.admin.admin import guard_router, templates, get_db
from app.repositories.admin.user_repository import UserRepository
from app.services.admin.user_service import UserService
from app.models.enums import UserRole, UserStatus
from app.models.user import Users
from app.schemas.admin.users import UserCreate, UserUpdate
from app.infrastructure.tranaslations import TranslationManager

router = guard_router


def get_service(db: AsyncSession = Depends(get_db)):
    return UserService(UserRepository(db))


def check_access(request: Request):
    role = request.session.get('auth_role')
    if role not in [UserRole.MODERATOR, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Access denied")


@router.get('/users/search', response_class=JSONResponse, name='admin.users.search_api')
async def search_users(request: Request, query: str, db: AsyncSession = Depends(get_db)):
    check_access(request)
    if not query:
        return []

    stmt = select(Users).filter(
        or_(
            Users.first_name.ilike(f"%{query}%"),
            Users.last_name.ilike(f"%{query}%"),
            Users.email.ilike(f"%{query}%")
        )
    ).limit(5)

    result = await db.execute(stmt)
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "name": f"{u.first_name} {u.last_name}",
            "email": u.email,
            "avatar": u.avatar_path
        }
        for u in users
    ]


@router.get('/users', response_class=HTMLResponse, name="admin.users.index")
async def index(
        request: Request,
        query: Optional[str] = "",
        role: Optional[str] = None,
        status: Optional[str] = None,
        page: Optional[int] = 1,
        sort: Optional[str] = "id",
        order: Optional[str] = "desc",
        service: UserService = Depends(get_service),
        db: AsyncSession = Depends(get_db)):
    check_access(request)

    filters = {'query': query, 'role': role, 'status': status, 'page': page}

    users = await service.repository.get(filters, sort_by=sort, sort_order=order)

    stmt = select(func.count()).select_from(Users)
    if query:
        stmt = stmt.filter(
            or_(
                Users.first_name.ilike(f"%{query}%"),
                Users.last_name.ilike(f"%{query}%"),
                Users.email.ilike(f"%{query}%")
            )
        )
    if role: stmt = stmt.filter(Users.role == role)
    if status: stmt = stmt.filter(Users.status == status)

    result = await db.execute(stmt)
    total_count = result.scalar()

    return templates.TemplateResponse('users/index.html', {
        'request': request,
        'query': query,
        'users': users,
        'total_count': total_count,
        'selected_role': role,
        'selected_status': status,
        'current_sort': sort,
        'current_order': order,
        'roles': list(UserRole),
        'statuses': list(UserStatus)
    })


@router.get('/users/{id}', response_class=HTMLResponse, name='admin.users.show')
async def show(id: int, request: Request, db: AsyncSession = Depends(get_db),
               service: UserService = Depends(get_service)):
    check_access(request)

    # Явно подгружаем достижения пользователя
    stmt = select(Users).options(selectinload(Users.achievements)).where(Users.id == id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    achievements = user.achievements
    total_docs = len(achievements)

    return templates.TemplateResponse('users/show.html', {
        'request': request,
        'user': user,
        'roles': list(UserRole),
        'achievements': achievements,
        'total_docs': total_docs
    })


@router.post('/users/{id}/role', name='admin.users.update_role')
async def update_role(
        id: int,
        request: Request,
        role: str = Form(...),
        service: UserService = Depends(get_service)
):
    if request.session.get('auth_role') != 'super_admin':
        raise HTTPException(status_code=403, detail="Only Super Admin can change roles")

    if id == request.session.get('auth_id'):
        return RedirectResponse(url=request.url_for('admin.users.show', id=id), status_code=302)

    await service.repository.update(id, {"role": role})

    translator = TranslationManager()
    url = request.url_for('admin.users.show', id=id).include_query_params(
        toast_msg=translator.gettext("admin.toast.profile_updated"),
        toast_type="success"
    )
    return RedirectResponse(url=url, status_code=302)


@router.get('/users/create', response_class=HTMLResponse, name='admin.users.create')
async def create(request: Request):
    check_access(request)
    return templates.TemplateResponse('users/create.html', {'request': request, 'roles': list(UserRole)})


@router.post('/users', response_class=HTMLResponse, name='admin.users.store')
async def store(request: Request, db: AsyncSession = Depends(get_db), service: UserService = Depends(get_service)):
    check_access(request)
    try:
        form = await request.form()
        form_data = dict(form)
        user_data = UserCreate(**form_data)

        service.set_request(request)
        await service.create(user_data)

        translator = TranslationManager()
        url = request.url_for('admin.users.index').include_query_params(
            toast_msg=translator.gettext("admin.toast.user_created"),
            toast_type="success"
        )
        return RedirectResponse(url=url, status_code=302)
    except ValueError as e:
        return templates.TemplateResponse('users/create.html',
                                          {'request': request, 'roles': list(UserRole), 'error_msg': str(e)})


@router.get('/users/{id}/edit', response_class=HTMLResponse, name='admin.users.edit')
async def edit(id: int, request: Request, db: AsyncSession = Depends(get_db),
               service: UserService = Depends(get_service)):
    if id != request.session.get('auth_id'):
        return RedirectResponse(url=request.url_for('admin.users.show', id=id), status_code=302)

    # Явно подгружаем достижения пользователя
    stmt = select(Users).options(selectinload(Users.achievements)).where(Users.id == id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    achievements = user.achievements if user else []
    total_docs = len(achievements)

    return templates.TemplateResponse('users/edit.html', {
        'request': request,
        'user': user,
        'roles': list(UserRole),
        'total_docs': total_docs,
        'achievements': achievements
    })


@router.post('/users/{id}', response_class=HTMLResponse, name='admin.users.update')
async def update(
        id: int,
        request: Request,
        db: AsyncSession = Depends(get_db),
        service: UserService = Depends(get_service)
):
    if id != request.session.get('auth_id'):
        raise HTTPException(status_code=403, detail="You cannot edit other users.")

    try:
        form = await request.form()
        form_data = dict(form)
        avatar_file = form_data.pop('avatar', None)
        form_data.pop('role', None)

        user_data = UserUpdate(**form_data)

        stmt = select(Users).filter(Users.email == user_data.email)
        result = await db.execute(stmt)
        existing_user = result.scalars().first()

        if existing_user and existing_user.id != id:
            raise ValueError("Email already taken")

        update_payload = user_data.dict(exclude_unset=True)

        if avatar_file and hasattr(avatar_file, 'filename') and avatar_file.filename:
            avatar_path = await service.save_avatar(id, avatar_file)
            update_payload["avatar_path"] = avatar_path

        await service.repository.update(id, update_payload)

        translator = TranslationManager()
        url = request.url_for('admin.dashboard').include_query_params(
            toast_msg=translator.gettext("admin.toast.profile_updated"),
            toast_type="success"
        )
        return RedirectResponse(url=url, status_code=302)
    except ValueError as e:
        # При ошибке тоже нужно подгрузить связи, чтобы отрендерить шаблон
        stmt = select(Users).options(selectinload(Users.achievements)).where(Users.id == id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        achievements = user.achievements if user else []
        total_docs = len(achievements)

        return templates.TemplateResponse('users/edit.html', {
            'request': request,
            'user': user,
            'roles': list(UserRole),
            'total_docs': total_docs,
            'achievements': achievements,
            'error_msg': str(e)
        })


@router.post('/users/{user_id}/delete', name='admin.users.delete')
async def delete(user_id: int, request: Request, service: UserService = Depends(get_service)):
    check_access(request)
    if user_id == request.session['auth_id']:
        raise HTTPException(status_code=400, detail="You cannot delete yourself.")

    user = await service.find(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    translator = TranslationManager()

    if user.status.value == 'deleted':
        await service.force_delete(user_id)
        msg = translator.gettext("admin.toast.permanently_deleted")
    else:
        await service.delete(user_id)
        msg = translator.gettext("admin.toast.deleted")

    url = request.url_for('admin.users.index').include_query_params(
        toast_msg=msg,
        toast_type="success"
    )
    return RedirectResponse(url=url, status_code=302)