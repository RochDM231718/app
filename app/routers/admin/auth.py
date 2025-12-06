from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.routers.admin.admin import templates, get_db
from app.services.auth_service import AuthService
from app.services.admin.user_service import UserService
from app.repositories.admin.user_repository import UserRepository
from app.infrastructure.tranaslations import TranslationManager
from app.models.enums import UserStatus
import time

router = APIRouter(
    prefix="/admin",
    tags=["admin_auth"]
)

def get_user_service(db: AsyncSession = Depends(get_db)):
    return UserService(UserRepository(db))

@router.get('/login', response_class=HTMLResponse, name='admin.auth.login.form')
async def show_login(request: Request):
    if request.session.get('auth_id'):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    return templates.TemplateResponse('auth/sign-in.html', {'request': request})

@router.post('/login', response_class=HTMLResponse, name='admin.auth.login')
async def login(
        request: Request,
        email: str = Form(...),
        password: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    last_attempt = request.session.get('last_login_attempt')
    current_time = time.time()

    if last_attempt and current_time - last_attempt < 2.0:
        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'error_msg': "Too many attempts. Please wait.",
            'form_data': {'email': email}
        })

    request.session['last_login_attempt'] = current_time

    auth_service = AuthService(db)
    user = await auth_service.authenticate(email, password, role="admin")

    translator = TranslationManager()

    if not user:
        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'error_msg': translator.gettext("api.auth.invalid_credentials"),
            'form_data': {'email': email}
        })

    if user.status == UserStatus.PENDING:
        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'error_msg': "Account pending approval.",
            'form_data': {'email': email}
        })

    if user.status == UserStatus.REJECTED:
        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'error_msg': "Registration rejected.",
            'form_data': {'email': email}
        })

    if user.status == UserStatus.DELETED:
        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'error_msg': "Account deleted.",
            'form_data': {'email': email}
        })

    request.session['auth_id'] = user.id
    request.session['auth_role'] = user.role.value
    request.session['auth_name'] = f"{user.first_name} {user.last_name}"

    url = request.url_for('admin.dashboard').include_query_params(
        toast_msg=translator.gettext("admin.toast.welcome"),
        toast_type="success"
    )
    return RedirectResponse(url=url, status_code=302)

@router.get('/logout', name='admin.auth.logout')
async def logout(request: Request):
    request.session.clear()
    translator = TranslationManager()
    url = request.url_for('admin.auth.login.form').include_query_params(
        toast_msg=translator.gettext("admin.toast.logged_out"),
        toast_type="info"
    )
    return RedirectResponse(url=url, status_code=302)

@router.get('/register', response_class=HTMLResponse, name='admin.auth.register.form')
async def show_register(request: Request):
    if request.session.get('auth_id'):
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    return templates.TemplateResponse('auth/register.html', {'request': request})

@router.post('/register', response_class=HTMLResponse, name='admin.auth.register.store')
async def register_store(
        request: Request,
        first_name: str = Form(...),
        last_name: str = Form(...),
        email: str = Form(...),
        password: str = Form(...),
        password_confirm: str = Form(...),
        service: UserService = Depends(get_user_service)
):
    form_data = {'first_name': first_name, 'last_name': last_name, 'email': email}
    translator = TranslationManager()

    if password != password_confirm:
        return templates.TemplateResponse('auth/register.html', {
            'request': request,
            'error_msg': translator.gettext("admin.auth.password_mismatch"),
            'form_data': form_data
        })

    try:
        await service.register_user(first_name, last_name, email, password)

        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'success_msg': translator.gettext("admin.toast.registered")
        })

    except ValueError as e:
        error_key = str(e)
        error_text = translator.gettext(error_key)
        return templates.TemplateResponse('auth/register.html', {
            'request': request,
            'error_msg': error_text,
            'form_data': form_data
        })
    except Exception as e:
        return templates.TemplateResponse('auth/register.html', {
            'request': request,
            'error_msg': f"Error: {str(e)}",
            'form_data': form_data
        })

@router.get('/forgot-password', response_class=HTMLResponse, name='admin.auth.forgot_password.form')
async def show_forgot_password(request: Request):
    return templates.TemplateResponse('auth/forgot-password.html', {'request': request})