import json
import random
from pathlib import Path


_CHROME = [f"{v}.0.0.0" for v in range(110, 130)]
_FIREFOX = [f"{v}.0" for v in range(110, 130)]
_SAFARI = ["15.0", "15.1", "15.2", "15.3", "15.4", "15.5", "15.6",
           "16.0", "16.1", "16.2", "16.3", "16.4", "16.5", "17.0"]
_EDGE = _CHROME
_WINDOWS = ["10.0", "11.0"]
_MACOS = [
    "10_15_7", "11_0_0", "11_1_0", "11_2_0", "11_3_0", "11_4_0",
    "11_5_0", "11_6_0", "12_0_0", "12_1_0", "12_2_0", "12_3_0",
    "12_4_0", "12_5_0", "12_6_0", "13_0_0", "13_1_0", "13_2_0",
    "13_3_0", "13_4_0", "13_5_0", "14_0_0",
]
_LINUX = [
    "X11; Linux x86_64",
    "X11; Ubuntu; Linux x86_64",
    "X11; Fedora; Linux x86_64",
]


def gen_ua() -> str:
    """Generate a random realistic browser User-Agent string."""
    browsers = [
        lambda: (
            f"Mozilla/5.0 (Windows NT {random.choice(_WINDOWS)}; Win64; x64)"
            f" AppleWebKit/537.36 (KHTML, like Gecko)"
            f" Chrome/{random.choice(_CHROME)} Safari/537.36"
        ),
        lambda: (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X {random.choice(_MACOS)})"
            f" AppleWebKit/537.36 (KHTML, like Gecko)"
            f" Chrome/{random.choice(_CHROME)} Safari/537.36"
        ),
        lambda: (
            f"Mozilla/5.0 ({random.choice(_LINUX)})"
            f" AppleWebKit/537.36 (KHTML, like Gecko)"
            f" Chrome/{random.choice(_CHROME)} Safari/537.36"
        ),
        lambda: (
            f"Mozilla/5.0 (Windows NT {random.choice(_WINDOWS)}; Win64; x64;"
            f" rv:{random.choice(_FIREFOX)}) Gecko/20100101"
            f" Firefox/{random.choice(_FIREFOX)}"
        ),
        lambda: (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X {random.choice(_MACOS)};"
            f" rv:{random.choice(_FIREFOX)}) Gecko/20100101"
            f" Firefox/{random.choice(_FIREFOX)}"
        ),
        lambda: (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X {random.choice(_MACOS)})"
            f" AppleWebKit/605.1.15 (KHTML, like Gecko)"
            f" Version/{random.choice(_SAFARI)} Safari/605.1.15"
        ),
        lambda: (
            f"Mozilla/5.0 (Windows NT {random.choice(_WINDOWS)}; Win64; x64)"
            f" AppleWebKit/537.36 (KHTML, like Gecko)"
            f" Chrome/{random.choice(_EDGE)} Safari/537.36"
            f" Edg/{random.choice(_EDGE)}"
        ),
    ]
    return random.choice(browsers)()


def get_or_create_session_ua(session_name: str, ua_file: str = "ua_session.json") -> str:
    """
    Return a persistent User-Agent for *session_name*.
    Creates a new one and saves it to *ua_file* if not yet stored.
    """
    path = Path(ua_file)
    try:
        all_uas: dict = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, IOError):
        all_uas = {}

    if session_name in all_uas:
        return all_uas[session_name]

    new_ua = gen_ua()
    all_uas[session_name] = new_ua
    try:
        path.write_text(json.dumps(all_uas, indent=2), encoding="utf-8")
    except IOError:
        pass
    return new_ua


def get_platform_from_ua(user_agent: str) -> str:
    """Return 'ios', 'android', or 'Unknown' based on the UA string."""
    if "iPhone" in user_agent or "iPad" in user_agent:
        return "ios"
    if "Android" in user_agent:
        return "android"
    return "Unknown"
