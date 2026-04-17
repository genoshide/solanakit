"""
Async HTTP requester with proxy support, automatic retry, and 401/429 handling.

Typical usage in a bot::

    from genosys.requester import AsyncRequester

    class MyBot:
        def __init__(self, private_key, proxy=None):
            self.requester = AsyncRequester(
                headers={"Content-Type": "application/json"},
                proxy=proxy,
                use_proxy=bool(proxy),
            )
            self.requester.token = "Bearer ..."

        async def checkin(self):
            res = await self.requester.get("https://api.example.com/checkin")
            return res["success"]
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class AsyncRequester:
    """
    Generic async HTTP client for Genoshide bots.

    Parameters
    ----------
    headers : dict
        Base request headers (will be shallow-copied per request).
    proxy : str | None
        Proxy URL, e.g. ``"http://user:pass@1.2.3.4:8080"``.
    use_proxy : bool
        Whether to forward the proxy to requests.
    token : str | None
        Bearer token added as ``Authorization`` header automatically.
    timeout : int
        Total request timeout in seconds (default 120).
    """

    def __init__(
        self,
        headers: dict | None = None,
        proxy: str | None = None,
        use_proxy: bool = False,
        token: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.headers: dict = headers or {}
        self.proxy = proxy
        self.use_proxy = use_proxy
        self.token = token
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public convenience methods
    # ------------------------------------------------------------------

    async def get(self, url: str, **kwargs) -> dict:
        return await self.request(url, "GET", **kwargs)

    async def post(self, url: str, data: Any = None, **kwargs) -> dict:
        return await self.request(url, "POST", data=data, **kwargs)

    # ------------------------------------------------------------------
    # Core request
    # ------------------------------------------------------------------

    async def request(
        self,
        url: str,
        method: str = "GET",
        data: Any = None,
        retries: int = 1,
        is_auth: bool = False,
    ) -> dict:
        """
        Make an HTTP request and return a normalised response dict::

            {"success": bool, "status": int, "data": ..., "error": ...}

        Parameters
        ----------
        url : str
            Full endpoint URL.
        method : str
            HTTP verb (GET / POST / PUT / DELETE …).
        data : Any
            JSON-serialisable payload for non-GET requests.
        retries : int
            Number of extra attempts on transient failures.
        is_auth : bool
            When True, skip adding the ``Authorization`` header
            (used for login endpoints).
        """
        headers = {**self.headers}
        if not is_auth and self.token:
            headers["Authorization"] = (
                self.token if self.token.startswith("Bearer ") else f"Bearer {self.token}"
            )

        attempt = 0
        last_error = ""
        last_status = 0

        while attempt <= retries:
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    kwargs: dict = {
                        "url": url,
                        "headers": headers,
                        "proxy": self.proxy if self.use_proxy else None,
                    }
                    if method.upper() != "GET" and data is not None:
                        kwargs["json"] = data

                    async with session.request(method.upper(), **kwargs) as resp:
                        last_status = resp.status
                        try:
                            body = await resp.json(content_type=None)
                        except Exception:
                            text = await resp.text()
                            return {
                                "success": resp.status < 400,
                                "status": resp.status,
                                "data": text,
                                "error": None,
                            }

                        # Normalise common response envelopes
                        if isinstance(body, dict):
                            # { msg: "ok", data: ... }  style
                            if "msg" in body:
                                if body.get("msg") != "ok":
                                    return {
                                        "success": False,
                                        "status": last_status,
                                        "data": body.get("data"),
                                        "error": body,
                                    }
                                return {
                                    "success": True,
                                    "status": last_status,
                                    "data": body.get("data", body),
                                }
                            # { success: bool, ... }  style
                            if "success" in body:
                                return {
                                    "success": bool(body["success"]),
                                    "status": last_status,
                                    "data": body.get("data"),
                                    "error": body if not body["success"] else None,
                                }

                        return {
                            "success": last_status < 400,
                            "status": last_status,
                            "data": body,
                            "error": None,
                        }

            except aiohttp.ClientResponseError as exc:
                last_error = str(exc)
                last_status = exc.status

                if last_status == 429:
                    print(f"[genosys] Rate limited ({url}), waiting 30 s …")
                    await asyncio.sleep(30)
                elif last_status == 400:
                    return {
                        "success": False,
                        "status": last_status,
                        "data": None,
                        "error": last_error,
                    }

            except Exception as exc:
                last_error = str(exc)
                return {
                    "success": False,
                    "status": last_status,
                    "data": None,
                    "error": last_error,
                }

            attempt += 1
            await asyncio.sleep(1)

        return {
            "success": False,
            "status": last_status,
            "data": None,
            "error": last_error,
        }
