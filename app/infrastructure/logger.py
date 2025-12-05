import logging
import sys
import structlog
import os
import gzip
import shutil
import hashlib
from logging.handlers import TimedRotatingFileHandler
from structlog.types import Processor


def calculate_sha256(file_path: str) -> str:
    """Вычисляет SHA256 хэш файла (для целостности)."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def archive_and_hash_rotator(source: str, dest: str):
    """
    Кастомный ротатор для логов:
    1. Сжимает старый лог в .gz
    2. Считает хэш архива и сохраняет в .sha256
    3. Удаляет исходный незащищенный файл
    """
    dest_gz = dest + ".gz"

    # 1. Сжимаем файл
    try:
        with open(source, 'rb') as f_in:
            with gzip.open(dest_gz, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # 2. Вычисляем хэш созданного архива
        file_hash = calculate_sha256(dest_gz)

        # 3. Сохраняем хэш
        with open(dest_gz + ".sha256", "w") as f_hash:
            f_hash.write(file_hash)

        # 4. Удаляем исходный файл (если сжатие прошло успешно)
        if os.path.exists(source):
            os.remove(source)

    except Exception as e:
        # Если ошибка, пишем в stderr, чтобы не потерять инфо
        sys.stderr.write(f"Error rotating logs: {e}\n")


def setup_logging(json_logs: bool = False, log_level: str = "INFO", log_file: str = "app.log"):
    """
    Настройка логгера с поддержкой ротации и хэширования.
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # --- Консоль ---
    if json_logs:
        console_renderer = structlog.processors.JSONRenderer()
    else:
        console_renderer = structlog.dev.ConsoleRenderer(colors=True)

    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            console_renderer,
        ],
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)

    # --- Файл с ротацией и хэшированием ---
    root_logger = logging.getLogger()
    root_logger.handlers = []
    root_logger.setLevel(log_level.upper())
    root_logger.addHandler(console_handler)

    if log_file:
        # Используем TimedRotatingFileHandler
        # when="midnight" — ротация каждую ночь в 00:00
        # backupCount=30 — хранить логи за 30 дней
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )

        # Подключаем наш кастомный ротатор
        file_handler.rotator = archive_and_hash_rotator
        # namer нужен, чтобы правильно сформировать имя перед передачей в rotator
        file_handler.namer = lambda name: name

        if json_logs:
            file_renderer = structlog.processors.JSONRenderer()
        else:
            file_renderer = structlog.dev.ConsoleRenderer(colors=False)

        file_formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                file_renderer,
            ],
        )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Перехват логов Uvicorn
    for _log in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        logger = logging.getLogger(_log)
        logger.handlers = []
        logger.propagate = True