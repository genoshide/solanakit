import asyncio
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

import aiofiles
import jwt as pyjwt
from colorama import Fore, Style

_LOCK = asyncio.Lock()
_TOKENS_FILE = "tokens.json"

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def load_data(file_path: str) -> list:
    """Read lines from a text file, stripping blank lines and \\r."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line for line in f.read().replace("\r", "").split("\n") if line.strip()]
        if not lines:
            print(f"[genosys] No data found in {file_path}")
        return lines
    except Exception as e:
        print(f"[genosys] Error loading file {file_path}: {e}")
        return []


async def save_json(identifier: str, value, filename: str = _TOKENS_FILE) -> None:
    """Async-safe write of a key→value entry into a JSON file."""
    async with _LOCK:
        data: dict = {}
        if os.path.exists(filename):
            try:
                async with aiofiles.open(filename, "r", encoding="utf-8") as f:
                    data = json.loads(await f.read())
            except Exception:
                data = {}
        data[identifier] = value
        async with aiofiles.open(filename, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=4))


def load_token_data(identifier: str, filename: str = _TOKENS_FILE):
    """Return the stored token data for *identifier*, or None."""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f).get(identifier)
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def is_token_expired(token: str) -> dict:
    """
    Returns ``{"isExpired": bool, "expirationDate": str}``.
    Treats missing / malformed tokens as expired.
    """
    def _now_str():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not token or token.count(".") != 2:
        return {"isExpired": True, "expirationDate": _now_str()}

    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return {"isExpired": True, "expirationDate": _now_str()}

        is_expired = time.time() > exp
        expiration = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S")
        return {"isExpired": is_expired, "expirationDate": expiration}
    except Exception as e:
        print(f"[genosys] Token check error: {e}")
        return {"isExpired": True, "expirationDate": _now_str()}


# ---------------------------------------------------------------------------
# Random / sleep helpers
# ---------------------------------------------------------------------------

def random_float(min_value: float, max_value: float, decimals: int = 2) -> float:
    """Return a random float between *min_value* and *max_value*."""
    return round(random.uniform(min_value, max_value), decimals)


def sleep(seconds=None) -> None:
    """
    Sleep for *seconds*.  If *seconds* is a list ``[min, max]``, pick random.
    If None, defaults to a random 1-5 s delay.
    """
    if isinstance(seconds, (int, float)):
        time.sleep(seconds)
        return
    if isinstance(seconds, (list, tuple)) and len(seconds) == 2:
        delay = random.uniform(seconds[0], seconds[1])
    else:
        delay = random.uniform(1, 5)
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

_ASCII_BANNER = r"""
  ________                           .__    .__    .___
 /  _____/  ____   ____   ____  _____|  |__ |__| __| _/____
/   \  ____/ __ \ /    \ /  _ \/  ___/  |  \|  |/ __ |/ __ \
\    \_\  \  ___/|   |  (  <_> )___ \|   Y  \  / /_/ \  ___/
 \______  /\___  >___|  /\____/____  >___|  /__\____ |\___  >
        \/     \/     \/           \/     \/        \/    \/
"""


def print_banner(title: str = "", subtitle: str = "") -> None:
    """Print the Genoshide ASCII banner with optional title and subtitle."""
    print(Fore.LIGHTGREEN_EX + Style.BRIGHT + _ASCII_BANNER + Style.RESET_ALL)
    print(
        f"{Fore.GREEN}==================[ {Style.BRIGHT}Genoshide{Style.NORMAL} ]"
        f"=================={Style.RESET_ALL}"
    )
    if title:
        print(f"{Fore.WHITE}>> {title} <<{Style.RESET_ALL}")
    if subtitle:
        print(f"{Fore.WHITE}>> {subtitle} <<{Style.RESET_ALL}")
    print(Fore.GREEN + "------------------------------------------------------------" + Style.RESET_ALL)
    print()
