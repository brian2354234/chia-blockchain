import asyncio
import time
from pathlib import Path
from secrets import token_bytes

import pytest

from src.protocols import full_node_protocol
from src.simulator.simulator_protocol import FarmNewBlockProtocol, ReorgProtocol
from src.types.peer_info import PeerInfo
from src.util.ints import uint16, uint32, uint64
from src.wallet.trade_manager import TradeManager
from tests.setup_nodes import setup_simulators_and_wallets
from src.consensus.block_rewards import calculate_base_fee, calculate_block_reward
from src.wallet.cc_wallet.cc_wallet import CCWallet
from src.wallet.cc_wallet import cc_wallet_puzzles
from src.wallet.wallet_coin_record import WalletCoinRecord
from typing import List


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


class TestWalletSimulator:
    @pytest.fixture(scope="function")
    async def wallet_node(self):
        async for _ in setup_simulators_and_wallets(1, 1, {}):
            yield _

    @pytest.fixture(scope="function")
    async def two_wallet_nodes(self):
        async for _ in setup_simulators_and_wallets(
            1, 2, {"COINBASE_FREEZE_PERIOD": 0}
        ):
            yield _

    @pytest.fixture(scope="function")
    async def two_wallet_nodes_five_freeze(self):
        async for _ in setup_simulators_and_wallets(
            1, 2, {"COINBASE_FREEZE_PERIOD": 5}
        ):
            yield _

    @pytest.fixture(scope="function")
    async def three_sim_two_wallets(self):
        async for _ in setup_simulators_and_wallets(
            3, 2, {"COINBASE_FREEZE_PERIOD": 0}
        ):
            yield _

    async def time_out_assert(self, timeout: int, function, value, arg=None):
        start = time.time()
        while time.time() - start < timeout:
            if arg is None:
                function_result = await function()
            else:
                function_result = await function(arg)
            if value == function_result:
                return
            await asyncio.sleep(1)
        assert False

    @pytest.mark.asyncio
    async def test_identity_creation(self, two_wallet_nodes):
        num_blocks = 10
        full_nodes, wallets = two_wallet_nodes
        full_node_1, server_1 = full_nodes[0]
        wallet_node, server_2 = wallets[0]
        wallet = wallet_node.wallet_state_manager.main_wallet

        ph = await wallet.get_new_puzzlehash()

        await server_2.start_client(PeerInfo("localhost", uint16(server_1._port)), None)
        for i in range(1, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(ph))

        funds = sum(
            [
                calculate_base_fee(uint32(i)) + calculate_block_reward(uint32(i))
                for i in range(1, num_blocks - 2)
            ]
        )

        await self.time_out_assert(15, wallet.get_confirmed_balance, funds)

        cc_wallet: CCWallet = await CCWallet.create_new_cc(
            wallet_node.wallet_state_manager, wallet, uint64(100)
        )

        for i in range(1, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(ph))

        await self.time_out_assert(15, cc_wallet.get_confirmed_balance, 100)
        await self.time_out_assert(15, cc_wallet.get_unconfirmed_balance, 100)

    @pytest.mark.asyncio
    async def test_did_spend(self, two_wallet_nodes):
        num_blocks = 10
        full_nodes, wallets = two_wallet_nodes
        full_node_1, server_1 = full_nodes[0]
        wallet_node, server_2 = wallets[0]
        wallet_node_2, server_3 = wallets[1]
        wallet = wallet_node.wallet_state_manager.main_wallet
        wallet2 = wallet_node_2.wallet_state_manager.main_wallet

        ph = await wallet.get_new_puzzlehash()

        await server_2.start_client(PeerInfo("localhost", uint16(server_1._port)), None)
        await server_3.start_client(PeerInfo("localhost", uint16(server_1._port)), None)

        for i in range(1, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(ph))

        funds = sum(
            [
                calculate_base_fee(uint32(i)) + calculate_block_reward(uint32(i))
                for i in range(1, num_blocks - 2)
            ]
        )

        await self.time_out_assert(15, wallet.get_confirmed_balance, funds)

        cc_wallet: CCWallet = await CCWallet.create_new_cc(
            wallet_node.wallet_state_manager, wallet, uint64(100)
        )

        for i in range(1, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(ph))

        await self.time_out_assert(15, cc_wallet.get_confirmed_balance, 100)
        await self.time_out_assert(15, cc_wallet.get_unconfirmed_balance, 100)

        assert cc_wallet.cc_info.my_core is not None
        colour = cc_wallet_puzzles.get_genesis_from_core(cc_wallet.cc_info.my_core)

        cc_wallet_2: CCWallet = await CCWallet.create_wallet_for_cc(
            wallet_node_2.wallet_state_manager, wallet2, colour
        )

        assert cc_wallet.cc_info.my_core == cc_wallet_2.cc_info.my_core

        cc_2_hash = await cc_wallet_2.get_new_inner_hash()
        await cc_wallet.cc_spend(uint64(60), cc_2_hash)

        for i in range(1, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(ph))

        await self.time_out_assert(15, cc_wallet.get_confirmed_balance, 40)
        await self.time_out_assert(15, cc_wallet.get_unconfirmed_balance, 40)

        await self.time_out_assert(30, cc_wallet_2.get_confirmed_balance, 60)
        await self.time_out_assert(30, cc_wallet_2.get_unconfirmed_balance, 60)

        cc_hash = await cc_wallet.get_new_inner_hash()
        await cc_wallet_2.cc_spend(uint64(15), cc_hash)

        for i in range(1, num_blocks):
            await full_node_1.farm_new_block(FarmNewBlockProtocol(ph))

        await self.time_out_assert(15, cc_wallet.get_confirmed_balance, 55)
        await self.time_out_assert(15, cc_wallet.get_unconfirmed_balance, 55)