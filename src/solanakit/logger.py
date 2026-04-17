from datetime import datetime
from colorama import Fore, Style


def logger(self, message: str, log_type: str = "info") -> None:
    """
    Colored console logger compatible with all Genoshide bot patterns.

    Usage:
        from genosys import logger
        from functools import partial

        class MyBot:
            def __init__(self):
                self.account_index = 1
                self.log = partial(logger, self)

        # or standalone:
        logger(None, "System message")
    """
    if self is None:
        print(f"SYSTEM {message}")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    index = self.account_index

    log_type = log_type.lower()
    tag_color = Fore.WHITE
    tag = " LOG   "

    if log_type == "info":
        tag = " INFO  "
        tag_color = Fore.CYAN
    elif log_type in ("warn", "warning"):
        tag = " WARN  "
        tag_color = Fore.YELLOW
    elif log_type == "success":
        tag = "SUCCESS"
        tag_color = Fore.GREEN
    elif log_type == "error":
        tag = " ERROR "
        tag_color = Fore.RED
    elif log_type == "debug":
        tag = " DEBUG "
        tag_color = Fore.MAGENTA
    elif log_type in ("failed", "fail"):
        tag = " FAILED"
        tag_color = Fore.LIGHTRED_EX
    elif log_type == "critical":
        tag = "CRITICAL"
        tag_color = Fore.RED + Style.BRIGHT

    index_colors = [Fore.BLUE, Fore.GREEN, Fore.YELLOW, Fore.MAGENTA, Fore.CYAN]
    index_color = index_colors[index % len(index_colors)]
    index_str = f"{index_color}{str(index).rjust(2)}{Style.RESET_ALL}"

    log_line = (
        f"{Fore.LIGHTBLACK_EX}{now}{Style.RESET_ALL}"
        f" | {tag_color}{tag}{Style.RESET_ALL}"
        f" | {index_str}"
        f" | {message}"
    )
    print(log_line)
