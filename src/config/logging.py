import logging
import os
from typing import Optional


def setup_logging(
    level: Optional[int] = None,
    level_name: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    resolved_level: Optional[int] = level
    if resolved_level is None:
        env_level = (level_name or os.getenv("LOG_LEVEL", "INFO")).upper()
        resolved_level = getattr(logging, env_level, logging.INFO)

    resolved_log_file = log_file or os.getenv("LOG_FILE")
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if resolved_log_file:
        handlers.append(logging.FileHandler(resolved_log_file, encoding="utf-8"))

    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s [%(process)d:%(threadName)s]: %(message)s",
        handlers=handlers,
        force=True,
    )
