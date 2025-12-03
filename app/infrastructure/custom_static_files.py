import os
import typing
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Маппинг MIME-типов, который работает в большинстве браузеров
FONT_MIME_TYPES = {
    "woff": "application/font-woff",  # Более старый, но совместимый MIME
    "woff2": "font/woff2",  # Современный стандарт
    "ttf": "application/x-font-ttf",
    "otf": "application/x-font-opentype",
    "eot": "application/vnd.ms-fontobject",
    "svg": "image/svg+xml"
}


class CustomStaticFiles(StaticFiles):
    """Кастомный класс для обслуживания статических файлов с исправленными MIME-типами."""

    def lookup_path(self, path: str) -> tuple[str, typing.Optional[os.stat_result]]:
        return super().lookup_path(path)

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)

        ext = path.split(".")[-1].lower()

        if ext in FONT_MIME_TYPES:
            # 1. Принудительно устанавливаем правильный MIME-тип
            response.headers["Content-Type"] = FONT_MIME_TYPES[ext]

            # 2. Принудительно устанавливаем заголовок CORS для шрифтов
            response.headers["Access-Control-Allow-Origin"] = "*"

            # 3. Отключаем кэширование для устранения проблем
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

        return response