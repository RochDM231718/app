from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.middlewares.admin_middleware import auth
from app.infrastructure.database.connection import get_database_connection
from app.infrastructure.tranaslations import TranslationManager

public_router = APIRouter(prefix='/admin', tags=['admin'], include_in_schema=False)
guard_router = APIRouter(prefix='/admin', tags=['admin'], include_in_schema=False, dependencies=[Depends(auth)])
templates = Jinja2Templates(directory='templates/admin')
translation_manager = TranslationManager()
templates.env.globals['gettext'] = translation_manager.gettext
db_connection = get_database_connection()


def get_db():
    db = db_connection.get_session()
    try:
        yield db
    finally:
        db.close()


@public_router.get('/')
async def index(request: Request):
    return RedirectResponse(url="/admin/login", status_code=302)


@public_router.get('/lang/{locale}', name='admin.set_language')
async def set_language(request: Request, locale: str):
    print(f"DEBUG: Request to switch language to: {locale}")

    if locale in ['en', 'ru']:
        request.session['locale'] = locale
        print(f"DEBUG: Session 'locale' updated to: {locale}")
    else:
        print(f"DEBUG: Invalid locale requested: {locale}")

    # Создаем менеджер (он уже загружен как синглтон, но это безопасно)
    translator = TranslationManager()

    # Явно передаем locale в gettext, чтобы получить сообщение на НОВОМ языке
    msg = translator.gettext('admin.toast.lang_changed', locale=locale)

    referer = request.headers.get("referer")
    redirect_url = referer if referer else "/admin/dashboard"
    url = str(redirect_url)

    # Очистка URL от старых параметров toast
    if '?' in url:
        base_url, params = url.split('?', 1)
        new_params = [p for p in params.split('&') if not p.startswith('toast_')]
        url = base_url + ('?' + '&'.join(new_params) if new_params else '')

    separator = '&' if '?' in url else '?'
    url += f"{separator}toast_msg={msg}&toast_type=success"

    # Возвращаем редирект с заголовками против кеширования
    response = RedirectResponse(url=url, status_code=302)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response