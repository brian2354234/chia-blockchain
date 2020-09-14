import aiohttp
import asyncio
import time
from time import struct_time, localtime

from typing import List, Optional

from src.server.connection import NodeType
from src.types.header_block import HeaderBlock
from src.rpc.full_node_rpc_client import FullNodeRpcClient
from src.rpc.wallet_rpc_client import WalletRpcClient
from src.util.byte_types import hexstr_to_bytes
from src.util.config import str2bool
from src.util.config import load_config
from src.util.default_root import DEFAULT_ROOT_PATH
from src.wallet.util.wallet_types import WalletType
from src.cmds.units import units
from src.util.chech32 import encode_puzzle_hash


def make_parser(parser):
    parser.add_argument(
        "-wp",
        "--wallet-rpc-port",
        help="Set the port where the Wallet is hosting the RPC interface."
        + " See the rpc_port under wallet in config.yaml."
        + "Defaults to 9256",
        type=int,
        default=9256,
    )
    parser.set_defaults(function=show)

async def print_balances(wallet_client):
    summaries_response = await wallet_client.get_wallets()
    if "wallet_summaries" not in summaries_response:
        print("Wallet summary cannot be displayed")
    else:
        print("Balances")
        for wallet_id, summary in summaries_response[
            "wallet_summaries"
        ].items():
            balances_response = await wallet_client.get_wallet_balance(
                wallet_id
            )
            if "wallet_balance" not in balances_response:
                print("Balances cannot be displayed")
                continue
            balances = balances_response["wallet_balance"]
            typ = WalletType(int(summary["type"])).name
            if "name" in summary:
                print(f"Wallet ID {wallet_id} type {typ} {summary['name']}")
                print(
                    f"   -Confirmed: {balances['confirmed_wallet_balance']/units['colouredcoin']}"
                )
                print(
                    f"   -Unconfirmed: {balances['unconfirmed_wallet_balance']/units['colouredcoin']}"
                )
                print(
                    f"   -Spendable: {balances['spendable_balance']/units['colouredcoin']}"
                )
                print(
                    f"   -Frozen: {balances['frozen_balance']/units['colouredcoin']}"
                )
                print(
                    f"   -Pending change: {balances['pending_change']/units['colouredcoin']}"
                )
            else:
                print(f"Wallet ID {wallet_id} type {typ}")
                print(
                    f"   -Confirmed: {balances['confirmed_wallet_balance']/units['chia']} TXCH"
                )
                print(
                    f"   -Unconfirmed: {balances['unconfirmed_wallet_balance']/units['chia']} TXCH"
                )
                print(
                    f"   -Spendable: {balances['spendable_balance']/units['chia']} TXCH"
                )
                print(
                    f"   -Frozen: {balances['frozen_balance']/units['chia']} TXCH"
                )
                print(
                    f"   -Pending change: {balances['pending_change']/units['chia']} TXCH"
                )

async def wallet_loop(wallet_client):
    fingerprint = None
    while True:
        # if fingerprint is None:
        fingerprints = await wallet_client.get_public_keys()
        if len(fingerprints) == 0:
            print("No keys loaded. Run 'chia keys generate' or import a key.")
            return
        if len(fingerprints) == 1:
            fingerprint = fingerprints[0]
            log_in_response = await wallet_client.log_in(fingerprint)
        else:
            print("Choose wallet key:")
            for i, fp in enumerate(fingerprints):
                print(f"{i+1}) {fp}")
            val = None
            while val is None:
                val = input("Enter number to pick press q to quite: ")
                if val == "q":
                    return
                if not val.isdigit():
                    val = None
                else:
                    index = int(val) - 1
                    if index >= len(fingerprints):
                        print("Invalid value")
                        val = None
                        continue
                    else:
                        fingerprint = fingerprints[index][0]
            log_in_response = await wallet_client.log_in(fingerprint)

        if log_in_response["success"] is False:
            if log_in_response["error"] == "not_initialized":
                use_cloud = True
                if "backup_path" in log_in_response:
                    path = log_in_response["backup_path"]
                    print(
                        f"Backup file from backup.chia.net downloaded and written to: {path}"
                    )
                    val = input(
                        "Do you want to use this file to restore from backup? (Y/N) "
                    )
                    if val.lower() == "y":
                        log_in_response = await wallet_client.log_in_and_restore(
                            fingerprint, path
                        )
                    else:
                        use_cloud = False

                if "backup_path" not in log_in_response or use_cloud is False:
                    if use_cloud is True:
                        val = input(
                            "No online backup file found, \n Press S to skip restore from backup"
                            " \n Press F to use your own backup file: "
                        )
                    else:
                        val = input(
                            "Cloud backup declined, \n Press S to skip restore from backup"
                            " \n Press F to use your own backup file: "
                        )

                    if val.lower() == "s":
                        log_in_response = await wallet_client.log_in_and_skip(
                            fingerprint
                        )
                    elif val.lower() == "f":
                        val = input(
                            "Please provide the full path to your backup file: "
                        )
                        log_in_response = await wallet_client.log_in_and_restore(
                            fingerprint, val
                        )

        if "success" not in log_in_response or log_in_response["success"] is False:
            if "error" in log_in_response:
                error = log_in_response["error"]
                print(f"Error: {log_in_response[error]}")
            return
        print_balances(wallet_client)


async def show_async(args, parser):
    try:
        config = load_config(DEFAULT_ROOT_PATH, "config.yaml")
        self_hostname = config["self_hostname"]
        if "wallet_rpc_port" not in args or args.wallet_rpc_port is None:
            wallet_rpc_port = config["wallet"]["rpc_port"]
        else:
            wallet_rpc_port = args.wallet_rpc_port
        wallet_client = await WalletRpcClient.create(self_hostname, wallet_rpc_port)
        await wallet_loop(wallet_client)

    except Exception as e:
        if isinstance(e, aiohttp.client_exceptions.ClientConnectorError):
            print(f"Connection error. Check if wallet is running at {args.wallet_rpc_port}")
        else:
            print(f"Exception from 'wallet' {e}")

    wallet_client.close()
    await wallet_client.await_closed()


def show(args, parser):
    return asyncio.run(show_async(args, parser))
