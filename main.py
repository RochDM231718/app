from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
import os
from starlette.responses import Response, RedirectResponse

from app.infrastructure.custom_static_files import CustomStaticFiles

from app.routers.admin.admin import public_router as admin_common_router
from app.routers.admin.auth import router as admin_auth_router
from app.routers.admin.dashboard import router as admin_dashboard_router
from app.routers.admin.users import router as admin_users_router
from app.routers.admin.pages import router as admin_pages_router
from app.routers.admin.achievements import router as admin_achievements_router
from app.routers.admin.moderation import router as admin_moderation_router

from app.middlewares.admin_middleware import GlobalContextMiddleware
from app.infrastructure.tranaslations import TranslationManager
from app.routers.api.auth import router as api_auth_router

app = FastAPI()

# --- MIDDLEWARE ---
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GlobalContextMiddleware)

# SECURITY FIX: Ensure ADMIN_SECRET_KEY is loaded
admin_secret = os.getenv('ADMIN_SECRET_KEY')
if not admin_secret:
    raise ValueError("CRITICAL SECURITY ERROR: ADMIN_SECRET_KEY is not set in environment variables!")

app.add_middleware(SessionMiddleware, secret_key=admin_secret)

# --- FAVICON FIX ---
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

# --- ROUTERS ---
app.include_router(admin_common_router)
app.include_router(admin_auth_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_users_router)
app.include_router(admin_pages_router)
app.include_router(admin_achievements_router)
app.include_router(admin_moderation_router)

app.include_router(api_auth_router)

# --- STATIC FILES ---
app.mount("/static", CustomStaticFiles(directory="static"), name="static")

# --- HOME ---
@app.get('/')
async def welcome():
    return RedirectResponse(url="/admin/login")