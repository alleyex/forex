import logging
import os
from typing import Optional


def setup_logging(level: Optional[int] = None, level_name: Optional[str] = None) -> None:
    resolved_level: Optional[int] = level
    if resolved_level is None:
        env_level = (level_name or os.getenv("LOG_LEVEL", "INFO")).upper()
        resolved_level = getattr(logging, env_level, logging.INFO)

    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
