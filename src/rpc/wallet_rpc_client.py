from typing import Dict
from src.rpc.rpc_client import RpcClient


class WalletRpcClient(RpcClient):
    """
    Client to Chia RPC, connects to a local wallet. Uses HTTP/JSON, and converts back from
    JSON into native python objects before returning. All api calls use POST requests.
    Note that this is not the same as the peer protocol, or wallet protocol (which run Chia's
    protocol on top of TCP), it's a separate protocol on top of HTTP thats provides easy access
    to the full node.
    """

    async def get_wallet_summaries(self) -> Dict:
        return await self.fetch("get_wallet_summaries", {})

    async def get_wallet_balance(self, wallet_id: str) -> Dict:
        return await self.fetch("get_wallet_balance", {"wallet_id": wallet_id})

    async def log_in(self, fingerprint) -> Dict:
        return await self.fetch(
            "log_in",
            {
                "host": "https://backup.chia.net",
                "fingerprint": fingerprint,
                "type": "start",
            },
        )

    async def log_in_and_restore(self, fingerprint, file_path) -> Dict:
        return await self.fetch(
            "log_in",
            {
                "host": "https://backup.chia.net",
                "fingerprint": fingerprint,
                "type": "restore_backup",
                "file_path": file_path,
            },
        )

    async def log_in_and_skip(self, fingerprint) -> Dict:
        return await self.fetch(
            "log_in",
            {
                "host": "https://backup.chia.net",
                "fingerprint": fingerprint,
                "type": "skip",
            },
        )

    async def get_keys(self) -> Dict:
        return await self.fetch("get_public_keys", {})
