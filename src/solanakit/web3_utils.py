"""
Web3 utility functions shared across all Genoshide on-chain bots.

Requires the ``web3`` extra::

    pip install genosys[web3]
"""

from __future__ import annotations

import time
from decimal import Decimal, getcontext
from threading import Lock

getcontext().prec = 28

# Per-address nonce locks so concurrent workers don't collide.
_wallet_locks: dict[str, Lock] = {}

# Minimal ERC-20 ABI — enough for balance, decimals, approve, transfer.
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]


def _get_wallet_lock(address: str) -> Lock:
    if address not in _wallet_locks:
        _wallet_locks[address] = Lock()
    return _wallet_locks[address]


def _wait_for_receipt(w3, tx_hash, timeout: int = 120):
    """Poll for a TX receipt until *timeout* seconds. Returns receipt or None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is not None:
                return receipt
        except Exception:
            pass
        time.sleep(2)
    return None


def check_balance(params: dict) -> str:
    """
    Return the human-readable token (or native ETH) balance as a string.

    Parameters
    ----------
    params : dict
        - ``provider``       : RPC URL (str)
        - ``wallet_address`` : wallet address directly (str) — preferred
        - ``privateKey``     : hex private key (str) — fallback if wallet_address absent
        - ``address``        : *optional* ERC-20 contract address (str)
        - ``abi``            : *optional* contract ABI override (list)

    Either ``wallet_address`` or ``privateKey`` must be provided.
    Returns ``"0"`` on any error.
    """
    try:
        from web3 import Web3
    except ImportError:
        raise ImportError("Install the web3 extra: pip install genosys[web3]")

    from datetime import datetime

    token_address = params.get("address")
    provider_url = params.get("provider")
    abi = params.get("abi", ERC20_ABI)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not provider_url:
        return "0"

    # Resolve wallet address — prefer explicit address, fallback to deriving from key
    wallet_address: str | None = params.get("wallet_address")
    if not wallet_address:
        private_key = params.get("privateKey")
        if not private_key:
            return "0"
        try:
            w3_tmp = Web3(Web3.HTTPProvider(provider_url))
            wallet_address = w3_tmp.eth.account.from_key(private_key).address
        except Exception:
            return "0"

    try:
        w3 = Web3(Web3.HTTPProvider(provider_url))
        short = f"{wallet_address[:6]}...{wallet_address[-4:]}"

        for _ in range(3):
            try:
                if token_address:
                    contract = w3.eth.contract(
                        address=Web3.to_checksum_address(token_address), abi=abi
                    )
                    raw = contract.functions.balanceOf(wallet_address).call()
                    dec = contract.functions.decimals().call()
                    human = Decimal(raw) / Decimal(10**dec)
                else:
                    raw = w3.eth.get_balance(wallet_address)
                    human = Decimal(raw) / Decimal(10**18)
                return format(human, ".4f")
            except Exception as err:
                msg = str(err)
                if "busy" in msg.lower() or "service" in msg.lower():
                    time.sleep(1)
                else:
                    return "0"

        print(f"{now} | ERROR | {short} | balance check failed after retries")
        return "0"

    except Exception as err:
        print(f"[genosys] check_balance error: {err}")
        return "0"


def send_token(params: dict) -> dict:
    """
    Send native ETH (or the chain's base token) to a recipient.

    Parameters
    ----------
    params : dict
        - ``provider``          : RPC URL
        - ``private_key``       : hex private key
        - ``recipient_address`` : destination wallet
        - ``amount``            : amount in ether units (float / str)
        - ``chain_id``          : chain ID (int or str, default 1)
        - ``explorer_url``      : prefix for tx URL in success message

    Returns ``{"success": bool, "tx": str|None, "message": str}``.
    """
    try:
        from eth_account import Account
        from web3 import Web3
    except ImportError:
        raise ImportError("Install the web3 extra: pip install genosys[web3]")

    recipient = params.get("recipient_address")
    amount = params.get("amount")
    private_key = params.get("private_key")
    provider_url = params.get("provider")
    chain_id = int(params.get("chain_id", 1))
    explorer_url = params.get("explorer_url", "")

    w3 = Web3(Web3.HTTPProvider(provider_url))
    account = Account.from_key(private_key)
    wallet_address = account.address

    try:
        amount_wei = w3.to_wei(str(amount), "ether")
        balance = w3.eth.get_balance(wallet_address)

        if balance < w3.to_wei("0.0001", "ether"):
            return {"tx": None, "success": False, "message": "Insufficient ETH for transfer"}

        gas = 21000
        gas_price = w3.to_wei("1", "gwei")
        min_required = amount_wei + (gas * gas_price)

        if balance < min_required:
            need = w3.from_wei(min_required, "ether")
            have = w3.from_wei(balance, "ether")
            return {
                "tx": None,
                "success": False,
                "message": f"Insufficient ETH. Need {need}, have {have}",
            }

        nonce = w3.eth.get_transaction_count(wallet_address, "pending")
        tx = {
            "to": Web3.to_checksum_address(recipient),
            "value": amount_wei,
            "gas": gas,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": chain_id,
        }

        signed = Account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hex = w3.to_hex(tx_hash)

        receipt = _wait_for_receipt(w3, tx_hash)
        if not receipt:
            return {
                "tx": tx_hex,
                "success": False,
                "message": f"TX sent but not confirmed after 120 s. Check: {explorer_url}{tx_hex}",
            }

        return {
            "tx": tx_hex,
            "success": True,
            "message": f"Sent {amount} ETH! TX: {explorer_url}{tx_hex}",
        }

    except Exception as err:
        msg = str(err)
        if "replacement transaction underpriced" in msg or "replay" in msg.lower():
            msg = "Nonce/gas conflict — try again"
        elif "not in the chain after" in msg:
            msg = "Transaction timed out before confirmation"
        return {"tx": None, "success": False, "message": f"Send error: {msg}"}


def sign_message(private_key: str, message: str) -> str:
    """
    Sign a text message with a private key and return the signature hex.

    This is the standard login/auth pattern used across all testnet bots::

        signature = sign_message(private_key, "pharos")
        # POST /user/login?address=0x...&signature=0x...

    Parameters
    ----------
    private_key : str
        Hex private key (with or without ``0x`` prefix).
    message : str
        Plain-text message to sign (e.g. ``"pharos"``, ``"sign in"``).

    Returns
    -------
    str
        Signature as a ``0x``-prefixed hex string.
    """
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError:
        raise ImportError("Install the web3 extra: pip install genosys[web3]")

    msg = encode_defunct(text=message)
    signed = Account.sign_message(msg, private_key=private_key)
    return signed.signature.hex()


def transfer_erc20(params: dict) -> dict:
    """
    Transfer ERC-20 tokens (USDC, USDT, WETH, …) from one wallet to another.

    Parameters
    ----------
    params : dict
        - ``provider``          : RPC URL
        - ``private_key``       : hex private key of the sender
        - ``token_address``     : ERC-20 contract address
        - ``recipient_address`` : destination wallet
        - ``amount``            : amount in human units (e.g. ``10.5`` for 10.5 USDC)
        - ``chain_id``          : chain ID (int or str, default 1)
        - ``explorer_url``      : optional TX explorer prefix
        - ``abi``               : optional ABI override (default ERC20_ABI)

    Returns
    -------
    dict
        ``{"success": bool, "tx": str | None, "message": str}``
    """
    try:
        from eth_account import Account
        from web3 import Web3
    except ImportError:
        raise ImportError("Install the web3 extra: pip install genosys[web3]")

    private_key     = params.get("private_key")
    token_address   = params.get("token_address")
    recipient       = params.get("recipient_address")
    amount          = params.get("amount")
    provider_url    = params.get("provider")
    chain_id        = int(params.get("chain_id", 1))
    explorer_url    = params.get("explorer_url", "")
    abi             = params.get("abi", ERC20_ABI)

    w3 = Web3(Web3.HTTPProvider(provider_url))
    account = Account.from_key(private_key)
    wallet_address = account.address

    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address), abi=abi
        )

        decimals = contract.functions.decimals().call()
        raw_amount = int(Decimal(str(amount)) * Decimal(10 ** decimals))

        token_balance = contract.functions.balanceOf(wallet_address).call()
        if token_balance < raw_amount:
            have = Decimal(token_balance) / Decimal(10 ** decimals)
            return {
                "tx": None,
                "success": False,
                "message": f"Insufficient token balance. Have {have}, need {amount}",
            }

        with _get_wallet_lock(wallet_address):
            nonce = w3.eth.get_transaction_count(wallet_address, "pending")
            tx = contract.functions.transfer(
                Web3.to_checksum_address(recipient), raw_amount
            ).build_transaction({
                "from": wallet_address,
                "nonce": nonce,
                "gas": 100_000,
                "gasPrice": w3.to_wei("1", "gwei"),
                "chainId": chain_id,
            })

            signed = Account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            tx_hex = w3.to_hex(tx_hash)

        receipt = _wait_for_receipt(w3, tx_hash)
        if not receipt:
            return {
                "tx": tx_hex,
                "success": False,
                "message": f"TX sent but not confirmed after 120 s. Check: {explorer_url}{tx_hex}",
            }

        return {
            "tx": tx_hex,
            "success": True,
            "message": f"Transferred {amount} tokens! TX: {explorer_url}{tx_hex}",
        }

    except Exception as err:
        msg = str(err)
        if "replacement transaction underpriced" in msg or "replay" in msg.lower():
            msg = "Nonce/gas conflict — try again"
        elif "not in the chain after" in msg:
            msg = "Transaction timed out before confirmation"
        return {"tx": None, "success": False, "message": f"Transfer error: {msg}"}


def approve_token(
    token_address: str,
    amount: int,
    wallet_address: str,
    w3,
    router,
    private_key: str,
) -> None:
    """
    Approve *router* to spend *amount* of *token_address* on behalf of *wallet_address*.
    No-op if allowance is already sufficient.
    """
    contract = w3.eth.contract(
        address=w3.to_checksum_address(token_address), abi=ERC20_ABI
    )
    current = contract.functions.allowance(wallet_address, router.address).call()
    if current >= amount:
        return

    tx = contract.functions.approve(router.address, amount).build_transaction(
        {
            "from": wallet_address,
            "nonce": w3.eth.get_transaction_count(wallet_address),
            "gas": 60000,
            "gasPrice": w3.to_wei("1", "gwei"),
        }
    )
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
