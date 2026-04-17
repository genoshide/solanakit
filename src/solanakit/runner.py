"""
Multi-process batch runner used by all Genoshide bots.

Typical usage::

    from genosys.runner import run_batch_workers

    async def my_worker(account_data, account_index, proxy):
        bot = MyBot(account_data, account_index, proxy)
        return await bot.run()

    asyncio.run(
        run_batch_workers(
            worker_fn=my_worker,
            private_keys=load_data("private_key.txt"),
            proxies=load_data("proxies.txt"),
            max_workers=10,
            loop_interval_minutes=8,
            use_proxy=True,
        )
    )
"""

from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ProcessPoolExecutor
from typing import Callable

from eth_account import Account


# ---------------------------------------------------------------------------
# Internal sync wrapper — runs inside a child process
# ---------------------------------------------------------------------------

def _sync_worker(payload: dict) -> tuple[int, bool, str]:
    """
    Called by ProcessPoolExecutor in a child process.
    *payload* must be picklable (no lambdas / closures).
    """
    if not isinstance(payload, dict) or "account_data" not in payload:
        return -1, False, f"Malformed payload: {payload}"

    idx = payload["account_index"]
    worker_module: str = payload["worker_module"]
    worker_name: str = payload["worker_name"]

    async def _run():
        # Dynamically import the worker function so it works across processes.
        import importlib

        mod = importlib.import_module(worker_module)
        fn: Callable = getattr(mod, worker_name)
        try:
            await fn(
                payload["account_data"],
                payload["account_index"],
                payload.get("proxy"),
            )
            return idx, True, "Completed"
        except Exception as exc:  # noqa: BLE001
            return idx, False, f"Exception: {repr(exc)}"

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def build_worker_payloads(
    private_keys: list[str],
    proxies: list[str],
    use_proxy: bool,
    worker_module: str,
    worker_name: str,
) -> list[dict]:
    """
    Build a list of picklable payloads, one per private key.
    """
    items = []
    for i, pk in enumerate(private_keys):
        key = pk if pk.startswith("0x") else f"0x{pk}"
        address = Account.from_key(key).address
        proxy = proxies[i % len(proxies)] if use_proxy and proxies else None
        items.append(
            {
                "account_data": {"privateKey": pk, "address": address},
                "account_index": i + 1,
                "proxy": proxy,
                "worker_module": worker_module,
                "worker_name": worker_name,
            }
        )
    return items


async def run_batch_workers(
    worker_module: str,
    worker_name: str,
    private_keys: list[str],
    proxies: list[str] | None = None,
    max_workers: int = 10,
    loop_interval_minutes: int | None = None,
    use_proxy: bool = False,
) -> None:
    """
    Run *worker_fn* for every private key in parallel batches.

    Parameters
    ----------
    worker_module : str
        Dotted module path that contains the async worker function,
        e.g. ``"mybot.worker"``.
    worker_name : str
        Name of the async function inside that module,
        e.g. ``"run_account"``.
    private_keys : list[str]
        List of hex private keys.
    proxies : list[str] | None
        Proxy URLs.  Reused round-robin if fewer than keys.
    max_workers : int
        Max parallel processes.
    loop_interval_minutes : int | None
        If set, repeat indefinitely with this pause between cycles.
    use_proxy : bool
        Whether to pass proxies to workers.
    """
    proxies = proxies or []

    if not private_keys:
        print("\033[31m[genosys] private_key list is empty — aborting.\033[0m")
        sys.exit(1)

    if use_proxy and not proxies:
        print("\033[31m[genosys] USE_PROXY=True but proxy list is empty — aborting.\033[0m")
        sys.exit(1)

    if use_proxy and len(private_keys) > len(proxies):
        print(
            f"\033[33m[genosys] {len(private_keys)} keys but {len(proxies)} proxies "
            f"— proxies will be reused.\033[0m"
        )

    payloads = build_worker_payloads(
        private_keys, proxies, use_proxy, worker_module, worker_name
    )

    loop = asyncio.get_running_loop()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        while True:
            print(
                f"\033[34m[genosys] Starting run for {len(private_keys)} accounts …\033[0m"
            )

            for batch_start in range(0, len(payloads), max_workers):
                batch = payloads[batch_start: batch_start + max_workers]
                futures = [
                    loop.run_in_executor(executor, _sync_worker, item)
                    for item in batch
                ]
                results = await asyncio.gather(*futures, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        print(f"\033[31m[genosys] Worker crashed: {repr(result)}\033[0m")
                        continue
                    if not result:
                        print("\033[31m[genosys] Worker returned empty result.\033[0m")
                        continue
                    idx, success, message = result
                    status = "\033[32mOK\033[0m" if success else "\033[31mFAIL\033[0m"
                    print(f"[genosys] Account {idx:>3} | {status} | {message}")

            if loop_interval_minutes is None:
                break

            print(
                f"\033[35m[genosys] Cycle done. Next in {loop_interval_minutes} min …\033[0m"
            )
            await asyncio.sleep(loop_interval_minutes * 60)
