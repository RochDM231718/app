from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.middlewares.admin_middleware import auth
from app.infrastructure.database.connection import get_database_connection
from app.infrastructure.tranaslations import TranslationManager, current_locale

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
    if locale in ['en', 'ru']:
        request.session['locale'] = locale

    token = current_locale.set(locale)
    translator = TranslationManager()
    msg = translator.gettext('admin.toast.lang_changed')
    current_locale.reset(token)

    referer = request.headers.get("referer")
    redirect_url = referer if referer else "/admin/dashboard"
    url = str(redirect_url)
    separator = '&' if '?' in url else '?'
    url += f"{separator}toast_msg={msg}&toast_type=success"
    return RedirectResponse(url=url, status_code=302)