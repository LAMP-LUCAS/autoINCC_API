"""Structured logging configuration for AutoINCC.

Provides standardized logging handlers and formatters for console and file outputs.
"""

import logging
import sys
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> None:
    """Configures structured root logging for the entire application.

    Args:
        log_level (Optional[str]): Logging level string (e.g. 'DEBUG', 'INFO').
            If None, defaults to 'INFO'.
    """
    level_name = (log_level or "INFO").upper()
    numeric_level = getattr(logging, level_name, logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Reset existing handlers on root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    else:
        for handler in root_logger.handlers:
            handler.setLevel(numeric_level)


def get_logger(name: str) -> logging.Logger:
    """Returns a namespaced logger instance.

    Args:
        name (str): Logger name, typically `__name__`.

    Returns:
        logging.Logger: Configured logger.
    """
    return logging.getLogger(name)
