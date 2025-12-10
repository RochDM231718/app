from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.routers.admin.admin import templates, get_db
from app.services.auth_service import AuthService
from app.services.admin.user_service import UserService
from app.services.admin.user_token_service import UserTokenService
from app.repositories.admin.user_repository import UserRepository
from app.repositories.admin.user_token_repository import UserTokenRepository
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
        # Аутентификация не удалась (неверный пароль, пользователь не найден ИЛИ пользователь не активен)
        # В идеале AuthService должен возвращать причину, но для простоты:
        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'error_msg': translator.gettext("api.auth.invalid_credentials"),
            'form_data': {'email': email}
        })

    if user.status == UserStatus.PENDING:
        return templates.TemplateResponse('auth/sign-in.html', {
            'request': request,
            'error_msg': "Account pending approval or email verification.",
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
        db: AsyncSession = Depends(get_db)
):
    # Примечание: AuthService используется напрямую вместо UserService для регистрации,
    # так как нам нужна специфичная логика отправки писем и генерации токенов,
    # которая теперь реализована в AuthService.register

    from app.schemas.admin.auth import RegisterSchema

    form_data = {'first_name': first_name, 'last_name': last_name, 'email': email}
    translator = TranslationManager()

    if password != password_confirm:
        return templates.TemplateResponse('auth/register.html', {
            'request': request,
            'error_msg': translator.gettext("admin.auth.password_mismatch"),
            'form_data': form_data
        })

    try:
        auth_service = AuthService(db)
        data = RegisterSchema(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=password,
            password_confirm=password_confirm
        )

        # Передаем request для генерации ссылок в письме
        success = await auth_service.register(data, request)

        if success:
            return templates.TemplateResponse('auth/sign-in.html', {
                'request': request,
                'success_msg': "Registration successful. Please check your email to verify your account."
            })
        else:
            return templates.TemplateResponse('auth/register.html', {
                'request': request,
                'error_msg': "Email already exists.",
                'form_data': form_data
            })

    except ValueError as e:
        error_key = str(e)
        error_text = translator.gettext(error_key)  # Если ключ перевода не найден, вернет сам ключ
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


# --- Verify Email ---
@router.get('/verify-email/{token}', response_class=HTMLResponse, name='admin.auth.verify_email')
async def verify_email_route(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    success = await auth_service.verify_email(token)

    if success:
        url = request.url_for('admin.auth.login.form').include_query_params(
            toast_msg="Email verified successfully. You can now login.",
            toast_type="success"
        )
    else:
        url = request.url_for('admin.auth.login.form').include_query_params(
            toast_msg="Invalid or expired verification link.",
            toast_type="error"
        )

    return RedirectResponse(url=url, status_code=302)


# --- Forgot Password ---
@router.get('/forgot-password', response_class=HTMLResponse, name='admin.auth.forgot_password.form')
async def show_forgot_password(request: Request):
    return templates.TemplateResponse('auth/forgot-password.html', {'request': request})


@router.post('/forgot-password', response_class=HTMLResponse, name='admin.auth.forgot_password.send')
async def send_forgot_password(
        request: Request,
        email: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    auth_service = AuthService(db)
    await auth_service.reset_password(email, request)

    # Всегда показываем успех из соображений безопасности
    return templates.TemplateResponse('auth/sign-in.html', {
        'request': request,
        'success_msg': "If an account with that email exists, we sent you a reset link."
    })


# --- Reset Password ---
@router.get('/reset-password/{token}', response_class=HTMLResponse, name='admin.reset-password.form')
async def show_reset_password_form(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    user_token_service = UserTokenService(UserTokenRepository(db))
    try:
        await user_token_service.getResetPasswordToken(token)
    except Exception:
        url = request.url_for('admin.auth.login.form').include_query_params(
            toast_msg="Invalid or expired password reset link.",
            toast_type="error"
        )
        return RedirectResponse(url=url, status_code=302)

    return templates.TemplateResponse('auth/reset-password.html', {'request': request, 'token': token})


@router.post('/reset-password/{token}', response_class=HTMLResponse, name='admin.reset-password.store')
async def reset_password_store(
        token: str,
        request: Request,
        password: str = Form(...),
        password_confirm: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    if password != password_confirm:
        return templates.TemplateResponse('auth/reset-password.html', {
            'request': request,
            'token': token,
            'error_msg': "Passwords do not match"
        })

    auth_service = AuthService(db)
    try:
        await auth_service.complete_reset_password(token, password)

        url = request.url_for('admin.auth.login.form').include_query_params(
            toast_msg="Password has been reset successfully.",
            toast_type="success"
        )
        return RedirectResponse(url=url, status_code=302)

    except Exception as e:
        return templates.TemplateResponse('auth/reset-password.html', {
            'request': request,
            'token': token,
            'error_msg': f"Error resetting password: {str(e)}"
        })