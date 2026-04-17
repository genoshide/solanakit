"""
genosys
=========
Python toolkit for blockchain testnet & automation bots.

Quick start
-----------
::

    from genosys import logger, load_data, print_banner
    from genosys import AsyncRequester
    from genosys import gen_ua, get_or_create_session_ua
    from genosys import is_token_expired, save_json, load_token_data
    from genosys import sleep, random_float

    # Web3 helpers (requires: pip install genosys[web3])
    from solanakit.web3_utils import (
        check_balance, send_token, transfer_erc20, sign_message, approve_token
    )

    # Multi-process runner
    from solanakit.runner import run_batch_workers

    # Retry decorators
    from solanakit.retry import async_retry, sync_retry, RetryError

    # File logger (Python logging + RotatingFileHandler)
    from solanakit.log import get_logger, setup_logging, disable_console_logging
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__: str = version("solanakit")
except PackageNotFoundError:
    __version__ = "0.0.0"

# Core logger
from solanakit.logger import logger

# Utils
from solanakit.utils import (
    load_data,
    save_json,
    load_token_data,
    is_token_expired,
    sleep,
    random_float,
    print_banner,
)

# User agents
from solanakit.user_agents import (
    gen_ua,
    get_or_create_session_ua,
    get_platform_from_ua,
)

# Async HTTP requester
from solanakit.requester import AsyncRequester

# Retry decorators
from solanakit.retry import async_retry, sync_retry, RetryError

# File logger + global shortcuts
from solanakit.log import (
    get_logger,
    setup_logging,
    disable_console_logging,
    debug,
    info,
    warning,
    warn,
    error,
    critical,
)

__all__ = [
    # logger
    "logger",
    # utils
    "load_data",
    "save_json",
    "load_token_data",
    "is_token_expired",
    "sleep",
    "random_float",
    "print_banner",
    # user agents
    "gen_ua",
    "get_or_create_session_ua",
    "get_platform_from_ua",
    # requester
    "AsyncRequester",
    # retry
    "async_retry",
    "sync_retry",
    "RetryError",
    # file logger
    "get_logger",
    "setup_logging",
    "disable_console_logging",
    "debug",
    "info",
    "warning",
    "warn",
    "error",
    "critical",
    # version
    "__version__",
]

