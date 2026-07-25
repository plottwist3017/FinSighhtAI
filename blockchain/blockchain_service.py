"""
blockchain_service.py
Handles Monad Testnet interactions for FinSighht AI.

web3 is an optional dependency — all imports are lazy so the app runs
fine without it (blockchain features are simply disabled).
Secrets are read from .env locally and from st.secrets on Streamlit Cloud.
"""

from __future__ import annotations

import hashlib
from typing import Any
from utils.config import get_config

# Minimal ABI – only the two functions + event we use
CONTRACT_ABI: list[dict] = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "snapshotHash", "type": "bytes32"},
            {"internalType": "string",  "name": "month",        "type": "string"},
        ],
        "name": "saveSnapshot",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getSnapshots",
        "outputs": [
            {"internalType": "bytes32[]", "name": "hashes",     "type": "bytes32[]"},
            {"internalType": "string[]",  "name": "months",     "type": "string[]"},
            {"internalType": "uint256[]", "name": "timestamps", "type": "uint256[]"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "internalType": "address", "name": "wallet",       "type": "address"},
            {"indexed": True,  "internalType": "bytes32", "name": "snapshotHash", "type": "bytes32"},
            {"indexed": False, "internalType": "string",  "name": "month",        "type": "string"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp",    "type": "uint256"},
        ],
        "name": "SnapshotSaved",
        "type": "event",
    },
]


# ---------------------------------------------------------------------------
# web3 availability check (lazy)
# ---------------------------------------------------------------------------
def _web3_available() -> bool:
    try:
        import web3  # noqa: F401
        return True
    except ImportError:
        return False


def _get_web3():
    """Return a connected Web3 instance or raise ImportError."""
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware

    w3 = Web3(Web3.HTTPProvider(get_config("MONAD_RPC_URL", "https://testnet-rpc.monad.xyz")))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_connected() -> bool:
    """Return True only if web3 is installed AND the RPC responds."""
    if not _web3_available():
        return False
    try:
        return _get_web3().is_connected()
    except Exception:
        return False


def get_wallet_address() -> str:
    return get_config("WALLET_ADDRESS")


def hash_snapshot(snapshot_text: str) -> bytes:
    """Return a 32-byte SHA-256 digest of the snapshot text."""
    return hashlib.sha256(snapshot_text.encode("utf-8")).digest()


def save_snapshot_to_chain(snapshot_text: str, month: str) -> dict[str, Any]:
    """
    Hash the snapshot and store it on Monad Testnet.
    Returns: {tx_hash, block_number, snapshot_hash_hex, status}
    Raises on any failure.
    """
    if not _web3_available():
        raise ImportError("web3 is not installed. Run: pip install web3")

    from web3 import Web3

    contract_address = get_config("CONTRACT_ADDRESS")
    private_key      = get_config("PRIVATE_KEY")
    rpc_url          = get_config("MONAD_RPC_URL", "https://testnet-rpc.monad.xyz")

    w3 = _get_web3()

    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Monad RPC at {rpc_url}")
    if not contract_address:
        raise ValueError("CONTRACT_ADDRESS is not set in .env")
    if not private_key:
        raise ValueError("PRIVATE_KEY is not set in .env")

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=CONTRACT_ABI,
    )

    snap_bytes32 = hash_snapshot(snapshot_text)
    account = w3.eth.account.from_key(private_key)
    nonce = w3.eth.get_transaction_count(account.address)

    tx = contract.functions.saveSnapshot(snap_bytes32, month).build_transaction({
        "from":     account.address,
        "nonce":    nonce,
        "gas":      200_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed  = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    return {
        "tx_hash":           receipt.transactionHash.hex(),
        "block_number":      receipt.blockNumber,
        "snapshot_hash_hex": "0x" + snap_bytes32.hex(),
        "status":            receipt.status,
    }


def get_on_chain_snapshots() -> list[dict[str, Any]]:
    """Fetch all snapshots for the configured wallet. Returns [] on any failure."""
    contract_address = get_config("CONTRACT_ADDRESS")
    wallet_address   = get_config("WALLET_ADDRESS")
    if not _web3_available() or not contract_address or not wallet_address:
        return []
    try:
        from web3 import Web3

        w3 = _get_web3()
        if not w3.is_connected():
            return []

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=CONTRACT_ABI,
        )
        wallet = Web3.to_checksum_address(wallet_address)
        hashes, months, timestamps = contract.functions.getSnapshots().call({"from": wallet})

        return [
            {
                "hash":      "0x" + h.hex() if isinstance(h, (bytes, bytearray)) else str(h),
                "month":     m,
                "timestamp": t,
            }
            for h, m, t in zip(hashes, months, timestamps)
        ]
    except Exception:
        return []
