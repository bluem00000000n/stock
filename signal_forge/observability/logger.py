"""
Centralized logging system for SIGNAL FORGE ALERT.
Logs to both console and rotating files under runtime/logs/ with UTF-8 support.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_LOGGERS = {}


def setup_logger(
    name: str = "signal_forge",
    log_file: Optional[Path] = None,
    level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """Configures and returns a logger instance with console and rotating file output."""
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    _LOGGERS[name] = logger
    return logger


def get_logger(name: str = "signal_forge") -> logging.Logger:
    """Gets a logger instance using global configuration."""
    if name in _LOGGERS:
        return _LOGGERS[name]
    from signal_forge.config import config
    return setup_logger(name=name, log_file=config.log_file, level=config.log_level)
