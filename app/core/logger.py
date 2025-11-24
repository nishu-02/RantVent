import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

import structlog
from structlog.dev import ConsoleRenderer
from fastapi import FastAPI, Request, Response


LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

SLOW_REQUEST_MS = 1000


SHARED = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging():
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

    #
    # CONSOLE
    #
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            ConsoleRenderer(),
        ],
        foreign_pre_chain=SHARED,
    ))
    root.addHandler(console)

    #
    # daily.log (INFO + WARNING)
    #
    daily = TimedRotatingFileHandler(
        str(LOGS_DIR / "daily.log"),
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    daily.setLevel(logging.INFO)
    daily.addFilter(lambda record: record.levelno < logging.ERROR)
    daily.setFormatter(structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=SHARED,
    ))
    root.addHandler(daily)

    #
    # errors.log (ERROR + CRITICAL)
    #
    errors = TimedRotatingFileHandler(
        str(LOGS_DIR / "errors.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    errors.setLevel(logging.ERROR)
    errors.addFilter(lambda record: record.levelno >= logging.ERROR)
    errors.setFormatter(structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
        foreign_pre_chain=SHARED,
    ))
    root.addHandler(errors)

    #
    # Structlog config
    #
    structlog.configure(
        processors=[
            *SHARED,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


configure_logging()

logger = structlog.get_logger("app")
reqlog = structlog.get_logger("app.requests")


async def logging_middleware(request: Request, call_next):
    start = time.time()
    req_id = str(int(datetime.utcnow().timestamp() * 1_000_000))

    log = reqlog.bind(
        request_id=req_id,
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None,
    )

    try:
        response = await call_next(request)
        ms = (time.time() - start) * 1000

        if response.status_code >= 500:
            log.error("request_failed", status=response.status_code, ms=ms)
        elif response.status_code >= 400:
            log.warning("request_client_error", status=response.status_code, ms=ms)
        elif ms >= SLOW_REQUEST_MS:
            log.warning("request_slow", ms=ms)

        response.headers["X-Request-ID"] = req_id
        return response

    except Exception:
        ms = (time.time() - start) * 1000
        log.error("request_crashed", ms=ms, exc_info=True)
        raise


def register_logger(app: FastAPI):
    app.middleware("http")(logging_middleware)

    @app.on_event("startup")
    async def _startup():
        logger.info("startup")

    @app.on_event("shutdown")
    async def _shutdown():
        logger.info("shutdown")
