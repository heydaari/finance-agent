import logging
import os


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def stage(logger: logging.Logger, request_id: str | None, name: str, **details: object) -> None:
    request_part = f"request_id={request_id} " if request_id else ""
    detail_part = " ".join(f"{key}={value!r}" for key, value in details.items())
    logger.info("stage=%s %s%s", name, request_part, detail_part)
