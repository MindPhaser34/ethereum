# Ethereum Node with Monitoring Stack

Ethereum full node (Geth + Nimbus) with Prometheus metrics exporter and Grafana dashboard.
Two deployment options: Docker Compose (local development) and Helm chart (Kubernetes).

## Components

| Service | Version | Port | Description |
|---------|---------|------|-------------|
| Geth | v1.16.8 | 8545 (RPC), 8546 (WS), 30303 (P2P), 6060 (Metrics) | Execution layer client |
| Nimbus | multiarch-v25.12.0 | 5052 (REST), 9000 (P2P), 8001 (Metrics) | Consensus layer client |
| ETH Exporter | - | 9333 | Prometheus metrics exporter |
| Prometheus | v3.5.1 | 9090 | Metrics collection |
| Grafana | 12.3.1 | 3000 | Visualization |

## Project Structure

```
eth/
├── docker-compose.yaml          # Docker Compose (nodes + monitoring)
├── helm/
│   └── ethereum-node/           # Helm chart (Kubernetes)
│       ├── Chart.yaml
│       ├── values.yaml          # Production defaults
│       └── templates/
├── monitoring/
│   ├── eth-exporter/            # Custom Prometheus exporter (Python)
│   ├── prometheus/              # Prometheus config
│   └── grafana/                 # Dashboards & datasources
```

---

## Quick Start (Docker Compose)

Full stack: Geth + Nimbus + ETH Exporter + Prometheus + Grafana.

```bash
# Create data directories
mkdir -p ./nimbus-data ./geth-data
chmod 700 ./nimbus-data
chown 1000:1000 ./nimbus-data

# Generate JWT secret
openssl rand -hex 32 > jwt.hex

# Start all services
docker compose up -d

# Check status
docker compose ps
```

### Access

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Geth RPC**: http://localhost:8545
- **Nimbus REST API**: http://localhost:5052

---

## Quick Start (Helm / Kubernetes)

Helm chart `ethereum-node` deploys Geth + Nimbus into Kubernetes (without monitoring).

```bash
# Lint
helm lint helm/ethereum-node

# Deploy with production defaults (PVC storage)
helm upgrade --install eth-node helm/ethereum-node

# Or deploy with local profile (hostPath, reduced resources)
helm upgrade --install eth-node helm/ethereum-node \
  -f helm/ethereum-node/values.local.yaml
```

### Helm chart features

- **Network**: `mainnet` (default), `sepolia`, or `hoodi` — single parameter for both Geth and Nimbus
- **Archive mode**: `archiveNode: true` for full historical state (Geth `gcmode=archive` + Nimbus `history=archive`)
- **Storage**: `pvc` (production, 2Ti Geth / 500Gi Nimbus) or `hostPath` (local testing)
- **Beacon**: built-in Nimbus (`beacon.enabled: true`)
- **Ingress**: single nginx Ingress resource with explicit per-path backend routing (no rewrite)
- **JWT**: fixed secret or auto-generated on each deploy

### Ingress patterns (no rewrite)

Ingress paths are proxied as-is. Configure paths to match backend API prefixes.

Single host + explicit prefixes:

```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: eth.example.com
      paths:
        - path: /
          service: geth
          port: 8545
          pathType: Prefix
        - path: /eth/v1
          service: nimbus
          port: 5052
          pathType: Prefix
```

Dedicated hosts (cleanest separation):

```yaml
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: rpc.eth.example.com
      paths:
        - path: /
          service: geth
          port: 8545
          pathType: Prefix
    - host: beacon.eth.example.com
      paths:
        - path: /
          service: nimbus
          port: 5052
          pathType: Prefix
```

### Smoke test

```bash
kubectl port-forward svc/eth-node-ethereum-node-geth 8545:8545

curl -s http://127.0.0.1:8545 \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","method":"web3_clientVersion","params":[],"id":1}'
```

## Metrics

Metrics are available in the Docker Compose stack via ETH Exporter + Prometheus + Grafana.

### Block & Sync

| Metric | Description |
|--------|-------------|
| `eth_block_number` | Current block number (execution layer) |
| `eth_external_block_number` | External block number from Etherscan |
| `eth_sync_lag` | Blocks behind external chain |
| `eth_syncing` | Node syncing status (1=syncing, 0=synced) |
| `eth_beacon_head_slot` | Beacon chain head slot |
| `eth_beacon_sync_distance` | Slots behind in beacon sync |

### Network

| Metric | Description |
|--------|-------------|
| `eth_peer_count` | Number of connected peers (execution) |
| `eth_beacon_peer_count` | Number of connected peers (consensus) |

### Gas & Mempool

| Metric | Description |
|--------|-------------|
| `eth_gas_price_gwei` | Current gas price in Gwei |
| `eth_base_fee_gwei` | Base fee per gas in Gwei |
| `eth_pending_transactions` | Number of pending transactions |
| `eth_queued_transactions` | Number of queued transactions |

### Chain Info

| Metric | Description |
|--------|-------------|
| `eth_chain_id` | Network chain ID |
| `eth_latest_block_timestamp` | Timestamp of latest block |
| `eth_block_time_seconds` | Time since last block |

### Beacon Chain

| Metric | Description |
|--------|-------------|
| `eth_beacon_finalized_epoch` | Last finalized epoch |
| `eth_beacon_justified_epoch` | Last justified epoch |
| `eth_beacon_participation_rate` | Network participation rate |

### Client Info

| Metric | Description |
|--------|-------------|
| `eth_client_info` | Geth client version info |
| `eth_beacon_client_info` | Nimbus client version info |

## Grafana Dashboard

Dashboard is auto-provisioned and available at:
`Dashboards → Ethereum → Ethereum Node Dashboard`

### Sections:
1. **Block & Sync Status** - Node vs external block height comparison
2. **Sync Progress** - Sync lag and beacon chain distance
3. **Network** - Peer connections for both execution and consensus layers
4. **Gas & Mempool** - Gas prices and pending transactions
5. **Beacon Chain** - Finality, epochs, and participation
6. **Errors & Health** - RPC error tracking

## Architecture

### Docker Compose (full stack)

```
┌─────────────────┐     ┌──────────────────┐
│      Geth       │────▶│                  │
│  (Execution)    │ RPC │   ETH Exporter   │      ┌─────────────┐
└─────────────────┘     │     (Python)     │─────▶│  Prometheus │
                        │                  │      └──────┬──────┘
┌─────────────────┐     │                  │             │
│     Nimbus      │────▶│                  │             │
│  (Consensus)    │ REST└──────────────────┘             ▼
└─────────────────┘                               ┌─────────────┐
                                                  │   Grafana   │
                                                  └─────────────┘
```

### Helm chart (Kubernetes)

```
                       ┌──────────────┐
                       │   Ingress    │
                       │   (nginx)    │
                       └──────┬───────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
       ┌────────────────┐         ┌──────────────┐
       │  Geth Service  │         │Nimbus Service│
       │  (ClusterIP)   │         │ (ClusterIP)  │
       └───────┬────────┘         └──────┬───────┘
               │                         │
               ▼                         ▼
       ┌────────────────┐         ┌──────────────┐
       │     Geth       │         │    Nimbus    │
       │  StatefulSet   │         │ StatefulSet  │
       │  (Execution)   │         │ (Consensus)  │
       └───────┬────────┘         └──────┬───────┘
               │       JWT Secret        │
               └────────────┬────────────┘
                            │
                    ┌───────┴───────┐
                    │  PVC/hostPath │
                    └───────────────┘
```

## Ports

### Docker Compose

| Port | Service | Protocol |
|------|---------|----------|
| 8545 | Geth JSON-RPC | HTTP |
| 8546 | Geth WebSocket | WS |
| 30303 | Geth P2P | TCP/UDP |
| 6060 | Geth Metrics | HTTP |
| 5052 | Nimbus REST API | HTTP |
| 9000 | Nimbus P2P | TCP/UDP |
| 8001 | Nimbus Metrics | HTTP |
| 9090 | Prometheus | HTTP |
| 9333 | ETH Exporter | HTTP |
| 3000 | Grafana | HTTP |

### Helm chart (Kubernetes)

| Port | Service | Protocol |
|------|---------|----------|
| 8545 | Geth JSON-RPC | HTTP |
| 8546 | Geth WebSocket | WS |
| 8551 | Geth Auth-RPC | HTTP |
| 30303 | Geth P2P | TCP/UDP |
| 5052 | Nimbus REST API | HTTP |
| 9000 | Nimbus P2P | TCP/UDP |

## Troubleshooting

### Docker Compose

```bash
# Logs
docker logs geth
docker logs nimbus
docker compose logs -f

# Verify metrics
curl http://localhost:9333/metrics
curl http://localhost:9090/api/v1/targets

# Restart
docker compose restart
```

### Kubernetes (Helm)

```bash
# Pod status
kubectl get pods
kubectl describe pod eth-node-ethereum-node-geth-0

# Logs
kubectl logs -f statefulset/eth-node-ethereum-node-geth
kubectl logs -f statefulset/eth-node-ethereum-node-nimbus

# RPC check
kubectl port-forward svc/eth-node-ethereum-node-geth 8545:8545
curl -s http://127.0.0.1:8545 \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}'

# Ingress
kubectl get ingress
kubectl describe ingress eth-node-ethereum-node

# Redeploy after chart changes
helm upgrade --install eth-node helm/ethereum-node \
  -f helm/ethereum-node/values.local.yaml
```

## License

MIT
