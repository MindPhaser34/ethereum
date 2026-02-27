#!/usr/bin/env python3
"""
Ethereum Prometheus Exporter
Exports Ethereum node metrics (Geth + Nimbus) for Prometheus monitoring
"""

import os
import time
import json
import requests
from prometheus_client import start_http_server, Gauge, Counter, Info

# Configuration from environment
GETH_RPC_HOST = os.getenv('GETH_RPC_HOST', 'geth')
GETH_RPC_PORT = os.getenv('GETH_RPC_PORT', '8545')
NIMBUS_API_HOST = os.getenv('NIMBUS_API_HOST', 'nimbus')
NIMBUS_API_PORT = os.getenv('NIMBUS_API_PORT', '5052')
EXPORTER_PORT = int(os.getenv('EXPORTER_PORT', '9333'))
SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', '15'))

# Prometheus metrics
# Execution layer (Geth)
ETH_BLOCK_HEIGHT = Gauge('ethereum_block_height', 'Current block height of the execution layer')
ETH_SYNCING = Gauge('ethereum_syncing', 'Whether the node is syncing (1=syncing, 0=synced)')
ETH_SYNC_CURRENT_BLOCK = Gauge('ethereum_sync_current_block', 'Current block during sync')
ETH_SYNC_HIGHEST_BLOCK = Gauge('ethereum_sync_highest_block', 'Highest known block')
ETH_PEER_COUNT = Gauge('ethereum_peer_count', 'Number of connected peers')
ETH_GAS_PRICE = Gauge('ethereum_gas_price_gwei', 'Current gas price in Gwei')
ETH_CHAIN_ID = Gauge('ethereum_chain_id', 'Chain ID')

# Consensus layer (Nimbus)
BEACON_HEAD_SLOT = Gauge('ethereum_beacon_head_slot', 'Current head slot')
BEACON_HEAD_EPOCH = Gauge('ethereum_beacon_head_epoch', 'Current head epoch')
BEACON_FINALIZED_SLOT = Gauge('ethereum_beacon_finalized_slot', 'Finalized slot')
BEACON_FINALIZED_EPOCH = Gauge('ethereum_beacon_finalized_epoch', 'Finalized epoch')
BEACON_JUSTIFIED_EPOCH = Gauge('ethereum_beacon_justified_epoch', 'Justified epoch')
BEACON_SYNC_DISTANCE = Gauge('ethereum_beacon_sync_distance', 'Distance to sync target')
BEACON_IS_SYNCING = Gauge('ethereum_beacon_is_syncing', 'Whether beacon is syncing')
BEACON_PEER_COUNT = Gauge('ethereum_beacon_peer_count', 'Beacon peer count')

# External blockchain height
EXTERNAL_BLOCK_HEIGHT = Gauge('ethereum_external_block_height', 'Current block height from external API')
SYNC_LAG = Gauge('ethereum_sync_lag', 'Blocks behind external chain')

# Version info
GETH_VERSION = Info('ethereum_geth', 'Geth node information')
NIMBUS_VERSION = Info('ethereum_nimbus', 'Nimbus node information')

# Error counter
RPC_ERRORS = Counter('ethereum_rpc_errors_total', 'Total number of RPC errors')


def geth_rpc_call(method, params=None):
    """Make JSON-RPC call to Geth"""
    url = f"http://{GETH_RPC_HOST}:{GETH_RPC_PORT}"
    headers = {'content-type': 'application/json'}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or []
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()
        if 'error' in result and result['error']:
            raise Exception(f"RPC Error: {result['error']}")
        return result.get('result')
    except Exception as e:
        RPC_ERRORS.inc()
        print(f"Geth RPC call failed for {method}: {e}")
        return None


def nimbus_api_call(endpoint):
    """Make REST API call to Nimbus"""
    url = f"http://{NIMBUS_API_HOST}:{NIMBUS_API_PORT}{endpoint}"
    headers = {'Accept': 'application/json'}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        RPC_ERRORS.inc()
        print(f"Nimbus API call failed for {endpoint}: {e}")
        return None


def get_external_block_height():
    """Get current block height from public Ethereum RPC"""
    # List of public RPC endpoints to try
    public_rpcs = [
        'https://cloudflare-eth.com',
        'https://eth.llamarpc.com',
        'https://rpc.ankr.com/eth',
    ]

    headers = {'content-type': 'application/json'}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": []
    }

    for rpc_url in public_rpcs:
        try:
            response = requests.post(
                rpc_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            if data.get('result'):
                return int(data['result'], 16)
        except Exception as e:
            print(f"Failed to get block from {rpc_url}: {e}")
            continue

    print("Failed to get external block height from all sources")
    return None


def collect_geth_metrics():
    """Collect Geth execution layer metrics"""
    # Get block number
    block_number = geth_rpc_call('eth_blockNumber')
    local_height = None
    if block_number:
        local_height = int(block_number, 16)
        ETH_BLOCK_HEIGHT.set(local_height)

    # Get syncing status
    syncing = geth_rpc_call('eth_syncing')
    if syncing is False:
        ETH_SYNCING.set(0)
    elif syncing:
        ETH_SYNCING.set(1)
        if 'currentBlock' in syncing:
            ETH_SYNC_CURRENT_BLOCK.set(int(syncing['currentBlock'], 16))
        if 'highestBlock' in syncing:
            ETH_SYNC_HIGHEST_BLOCK.set(int(syncing['highestBlock'], 16))

    # Get peer count
    peer_count = geth_rpc_call('net_peerCount')
    if peer_count:
        ETH_PEER_COUNT.set(int(peer_count, 16))

    # Get gas price
    gas_price = geth_rpc_call('eth_gasPrice')
    if gas_price:
        # Convert from Wei to Gwei
        ETH_GAS_PRICE.set(int(gas_price, 16) / 1e9)

    # Get chain ID
    chain_id = geth_rpc_call('eth_chainId')
    if chain_id:
        ETH_CHAIN_ID.set(int(chain_id, 16))

    # Get client version
    version = geth_rpc_call('web3_clientVersion')
    if version:
        GETH_VERSION.info({
            'version': version,
            'client': 'geth'
        })

    return local_height


def collect_nimbus_metrics():
    """Collect Nimbus consensus layer metrics"""
    # Get sync status
    sync_status = nimbus_api_call('/eth/v1/node/syncing')
    if sync_status and 'data' in sync_status:
        data = sync_status['data']
        BEACON_HEAD_SLOT.set(int(data.get('head_slot', 0)))
        BEACON_SYNC_DISTANCE.set(int(data.get('sync_distance', 0)))
        BEACON_IS_SYNCING.set(1 if data.get('is_syncing', False) else 0)

    # Get finality checkpoints
    finality = nimbus_api_call('/eth/v1/beacon/states/head/finality_checkpoints')
    if finality and 'data' in finality:
        data = finality['data']
        if 'finalized' in data:
            BEACON_FINALIZED_EPOCH.set(int(data['finalized'].get('epoch', 0)))
        if 'current_justified' in data:
            BEACON_JUSTIFIED_EPOCH.set(int(data['current_justified'].get('epoch', 0)))

    # Get peer count
    peers = nimbus_api_call('/eth/v1/node/peer_count')
    if peers and 'data' in peers:
        connected = int(peers['data'].get('connected', 0))
        BEACON_PEER_COUNT.set(connected)

    # Get node version
    version = nimbus_api_call('/eth/v1/node/version')
    if version and 'data' in version:
        NIMBUS_VERSION.info({
            'version': version['data'].get('version', 'unknown'),
            'client': 'nimbus'
        })

    # Calculate head epoch from slot (32 slots per epoch)
    if sync_status and 'data' in sync_status:
        head_slot = int(sync_status['data'].get('head_slot', 0))
        BEACON_HEAD_EPOCH.set(head_slot // 32)


def collect_external_height(local_height):
    """Collect external block height and calculate sync lag"""
    external_height = get_external_block_height()
    if external_height:
        EXTERNAL_BLOCK_HEIGHT.set(external_height)
        if local_height:
            lag = external_height - local_height
            SYNC_LAG.set(max(0, lag))


def collect_metrics():
    """Collect all metrics"""
    print("Collecting metrics...")

    local_height = collect_geth_metrics()
    collect_nimbus_metrics()
    collect_external_height(local_height)

    print(f"Metrics collected. Local height: {local_height}")


def main():
    """Main function"""
    print(f"Starting Ethereum Prometheus Exporter on port {EXPORTER_PORT}")
    print(f"Connecting to Geth at {GETH_RPC_HOST}:{GETH_RPC_PORT}")
    print(f"Connecting to Nimbus at {NIMBUS_API_HOST}:{NIMBUS_API_PORT}")

    # Start HTTP server for Prometheus
    start_http_server(EXPORTER_PORT)
    print(f"Exporter running on http://0.0.0.0:{EXPORTER_PORT}/metrics")

    # Collect metrics in a loop
    while True:
        try:
            collect_metrics()
        except Exception as e:
            print(f"Error collecting metrics: {e}")
            RPC_ERRORS.inc()

        time.sleep(SCRAPE_INTERVAL)


if __name__ == '__main__':
    main()
