"""
File-based logging for long-running Genoshide bots.

Provides a Python ``logging.Logger`` with coloured console output and an
optional rotating log file — useful for bots that run unattended overnight.

This is a companion to ``genosys.logger`` (the print-based, account-indexed
logger used in multi-wallet bots).  Use this module when you want standard
Python logging with file rotation instead.

Global shortcuts (no setup needed)::

    from genosys.log import info, warning, error, debug, critical

    info("Bot started")
    warning("Proxy timeout, retrying...")
    error("TX rejected: %s", err)

Per-module logger::

    from genosys.log import get_logger, setup_logging

    log = get_logger(__name__, log_file="bot.log")
    log.info("Bot started")
    log.warning("Proxy failed, retrying...")
    log.error("TX rejected: %s", error_msg)

    # Or configure the root logger once at startup
    setup_logging(log_file="mybot.log", log_level="INFO")
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional


# ---------------------------------------------------------------------------
# Colour formatter (console only — no ANSI codes in log files)
# ---------------------------------------------------------------------------

class _ColorFormatter(logging.Formatter):
    """Adds ANSI colour codes to console log output."""

    _GREY     = "\x1b[38;20m"
    _CYAN     = "\x1b[36;20m"
    _YELLOW   = "\x1b[33;20m"
    _RED      = "\x1b[31;20m"
    _BOLD_RED = "\x1b[31;1m"
    _RESET    = "\x1b[0m"

    _FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"

    _LEVEL_COLORS = {
        logging.DEBUG:    _GREY,
        logging.INFO:     _CYAN,
        logging.WARNING:  _YELLOW,
        logging.ERROR:    _RED,
        logging.CRITICAL: _BOLD_RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self._LEVEL_COLORS.get(record.levelno, self._GREY)
        fmt = logging.Formatter(
            color + self._FMT + self._RESET,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        return fmt.format(record)


_PLAIN_FMT = logging.Formatter(
    "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Create and return a configured ``logging.Logger``.

    Parameters
    ----------
    name : str
        Logger name — use ``__name__`` to get per-module loggers.
    level : str
        Log level: ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``,
        ``"CRITICAL"`` (default ``"INFO"``).
    log_file : str | None
        Path to a rotating log file.  If *None*, logs only to the console.
    max_bytes : int
        Max size of each log file before rotation (default 10 MB).
    backup_count : int
        Number of rotated backup files to keep (default 5).

    Returns
    -------
    logging.Logger

    Example
    -------
    ::

        log = get_logger(__name__, log_file="mybot.log")
        log.info("Account %s started", address)
    """
    log = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls / re-imports
    if log.handlers:
        return log

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log.setLevel(numeric_level)

    # Console handler — coloured
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(_ColorFormatter())
    log.addHandler(console)

    # File handler — plain text, rotating
    if log_file:
        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(numeric_level)
        fh.setFormatter(_PLAIN_FMT)
        log.addHandler(fh)

    return log


def setup_logging(
    log_file: str = "bot.log",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    silence: tuple = ("httpx", "httpcore", "hpack", "asyncio", "urllib3"),
) -> None:
    """
    Configure the **root logger** with a rotating file handler.

    Call this once at bot startup.  All subsequent ``get_logger()`` calls
    will inherit the root level and the file handler.

    Parameters
    ----------
    log_file : str
        Path to the rotating log file (default ``"bot.log"``).
    log_level : str
        Minimum log level (default ``"INFO"``).
    max_bytes : int
        Max file size before rotation (default 10 MB).
    backup_count : int
        Number of backup files to keep (default 5).
    silence : tuple[str, ...]
        Noisy library loggers to suppress to WARNING level.

    Example
    -------
    ::

        # main.py
        from genosys.log import setup_logging
        setup_logging(log_file="mybot.log", log_level="INFO")
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Silence noisy third-party libraries
    for lib in silence:
        logging.getLogger(lib).setLevel(logging.WARNING)

    root = logging.getLogger()

    # Add file handler only once (idempotent)
    has_file = any(isinstance(h, RotatingFileHandler) for h in root.handlers)
    if not has_file:
        if root.level == logging.NOTSET or root.level > numeric_level:
            root.setLevel(numeric_level)
        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(numeric_level)
        fh.setFormatter(_PLAIN_FMT)
        root.addHandler(fh)


def disable_console_logging() -> None:
    """
    Strip every ``StreamHandler`` from every logger.

    Useful when a Rich Live / curses dashboard takes over the terminal and
    raw print output would corrupt the display.
    """
    def _strip(log: logging.Logger) -> None:
        for h in log.handlers[:]:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler):
                log.removeHandler(h)

    _strip(logging.getLogger())
    for child in logging.Logger.manager.loggerDict.values():
        if isinstance(child, logging.Logger):
            _strip(child)


# ---------------------------------------------------------------------------
# Global shortcuts — use without creating a logger instance
# ---------------------------------------------------------------------------
#
#   from genosys.log import info, warning, error, debug, critical
#
#   info("Bot started")
#   warning("Proxy timeout — retrying...")
#   error("TX failed: %s", err)
#   debug("Response: %s", data)
#   critical("Kill switch triggered!")
#
# All calls go through the "genosys" root logger which inherits any
# handlers configured via setup_logging().

_root = get_logger("genosys")

debug    = _root.debug
info     = _root.info
warning  = _root.warning
warn     = _root.warning   # alias — same as warning
error    = _root.error
critical = _root.critical
