# Sybil-Net Architecture

## System Overview

Sybil-Net is a three-layer protocol: a **Machine Learning layer** that detects Sybil attackers, a **Blockchain layer** that enforces penalties, and a **Marketplace layer** that monetises trust.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SYBIL-NET SYSTEM ARCHITECTURE                       │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  LAYER 1 — DATA PIPELINE                                    │
  │                                                             │
  │  Ethereum Mainnet (Alchemy API)                             │
  │         │                                                   │
  │         ▼  50,000+ transactions                             │
  │  ┌─────────────────┐    ┌──────────────────┐               │
  │  │ ingestion.py    │───►│ builder.py        │               │
  │  │ (Alchemy / Syn) │    │ (NetworkX DiGraph)│               │
  │  └─────────────────┘    └────────┬─────────┘               │
  │                                  │                          │
  │                          ┌───────▼──────────┐              │
  │                          │ extractor.py      │              │
  │                          │ (12 node features)│              │
  │                          └───────┬──────────┘              │
  └──────────────────────────────────┼──────────────────────── ┘
                                     │ graph.pkl + features.csv
  ┌──────────────────────────────────┼──────────────────────────┐
  │  LAYER 2 — GNN MODEL             │                          │
  │                                  ▼                          │
  │              ┌──────────────────────────────────┐          │
  │              │         GraphSAGE                 │          │
  │              │   3-layer SAGEConv + BatchNorm    │          │
  │              │                                   │          │
  │              │  Node features + Graph topology   │          │
  │              │         ↓ (37,122 params)         │          │
  │              │  Sybil Score per wallet (0–100)   │          │
  │              └──────────────────────────────────┘          │
  │                          │                                  │
  │                          ▼  node_scores.csv                 │
  └──────────────────────────┼───────────────────────────────── ┘
                             │
  ┌──────────────────────────┼───────────────────────────────────┐
  │  LAYER 3 — BLOCKCHAIN    │                                    │
  │                          ▼                                    │
  │            ┌────────────────────────┐                        │
  │            │    oracle_bridge.py    │                        │
  │            │  (Python → web3.py)    │                        │
  │            └──────────┬─────────────┘                        │
  │                       │  updateSybilScore() / slash()        │
  │                       ▼                                      │
  │            ┌────────────────────────┐                        │
  │            │     SybilNet.sol       │                        │
  │            │  ┌──────────────────┐  │                        │
  │            │  │ mintCredential() │  │ ← User stakes 0.01 ETH │
  │            │  ├──────────────────┤  │                        │
  │            │  │ updateScore()    │  │ ← Oracle pushes GNN    │
  │            │  ├──────────────────┤  │                        │
  │            │  │ slash()          │  │ ← Auto-slash on Sybil  │
  │            │  ├──────────────────┤  │                        │
  │            │  │ batchSlash()     │  │ ← Slash bot rings      │
  │            │  └──────────────────┘  │                        │
  │            └────────────────────────┘                        │
  └───────────────────────────────────────────────────────────── ┘
                             │
                             │  Humanity Credential (verified = true)
                             ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  LAYER 4 — TRUST-VERIFIED MARKETPLACE (roadmap)             │
  │                                                             │
  │   ┌──────────────────┐ ┌────────────────┐ ┌─────────────┐  │
  │   │  Asset Exchange  │ │  Credit Hub    │ │  Yield Hub  │  │
  │   │  (Trading)       │ │  (Borrowing)   │ │  (Earning)  │  │
  │   │  Zero wash-trade │ │  Under-collat. │ │  Bot-free   │  │
  │   │  NFTs + airdrops │ │  DeFi loans    │ │  yield farm │  │
  │   └──────────────────┘ └────────────────┘ └─────────────┘  │
  └─────────────────────────────────────────────────────────────┘
```

---

## Component Deep Dive

### 1. Data Ingestion (`data/ingestion.py`)

Two operating modes selected automatically:

| Mode | Trigger | Output |
|------|---------|--------|
| **Alchemy Live** | `ALCHEMY_API_KEY` in `.env` is valid | Real Ethereum txns from 5 seed addresses |
| **Synthetic Sybil** | No key / invalid key | 50k txns with 4 embedded attack patterns |

#### Synthetic Attack Patterns

| Pattern | Topology Signature | % of Dataset |
|---------|-------------------|-------------|
| Hub-and-spoke bot farm | One controller fans ETH to 20–80 workers and collects back | 30% |
| Wash-trading ring | 3–8 wallets cycle the same ETH in a closed loop | 20% |
| Layered Sybil cluster | Root → mid-layer → leaf hierarchical fan-out | 15% |
| Honest organic users | Random pairwise transfers, no circular patterns | 35% |

---

### 2. Graph Construction (`graph/builder.py`)

Transforms raw transactions into a **directed weighted graph**:

```
Wallets → Nodes
Transactions → Edges (directed: sender → receiver)

Edge attributes:
  weight        = number of transactions between pair
  total_value   = sum of ETH transferred
  avg_value     = mean ETH per transaction
  avg_gas       = mean gas used
  first_tx      = timestamp of earliest transfer
  last_tx       = timestamp of latest transfer
```

Storage: `data/processed/graph.pkl` (NetworkX DiGraph, serialised with pickle)

---

### 3. Feature Extraction (`features/extractor.py`)

12 node-level features computed per wallet — the input vector to the GNN:

| # | Feature | Description | Sybil Signal |
|---|---------|-------------|-------------|
| 1 | `in_degree` | Number of wallets sending TO this wallet | Low in bots |
| 2 | `out_degree` | Number of wallets receiving FROM this wallet | High in bot controllers |
| 3 | `total_tx_count` | Total weighted transaction count | Very high in bots |
| 4 | `unique_interactions` | Distinct neighbours (in + out) | Narrow in rings |
| 5 | `avg_value_sent` | Mean ETH value per outgoing tx | Uniform in bots |
| 6 | `avg_gas` | Mean gas used per tx | Uniform in bots |
| 7 | `tx_frequency` | Transactions per active day | Extremely high in bots |
| 8 | `node_age_days` | Days since first observed tx | Low in new bots |
| 9 | `reciprocity` | Fraction of out-neighbours that send back | High in wash rings |
| 10 | `clustering_coeff` | Directed clustering coefficient | High in cliques |
| 11 | `betweenness_centrality` | Node's role as a bridge in the graph | High in controllers |
| 12 | `pagerank` | Global influence score | Low in isolated bot clusters |

**Timestamp handling**: Alchemy returns ISO-8601 strings — the extractor uses `python-dateutil` to parse them into Unix timestamps before computing temporal features.

---

### 4. GNN Model (`models/gnn.py`)

#### Architecture: SybilSAGE

```
Input: [N × 12] feature matrix  +  Edge Index

Layer 1:  SAGEConv(12 → 128)  +  BatchNorm1d  +  ReLU  +  Dropout(0.4)
Layer 2:  SAGEConv(128 → 128) +  BatchNorm1d  +  ReLU  +  Dropout(0.4)
Layer 3:  SAGEConv(128 → 2)

Output:   log-softmax → [N × 2]  (Human | Sybil probability per node)
```

**Why GraphSAGE?**
- **Inductive** — can score new wallets never seen during training without retraining
- **Neighbourhood aggregation** — a bot's neighbours (other bots) give it away even if its own features look clean
- **Scalable** — mini-batch sampling allows processing of millions of nodes

#### Label Strategy

```
labels.csv present?  →  Ground-truth from synthetic generator (100% accurate)
labels.csv absent?   →  Topology heuristics on real data:
    Sybil: out_degree >= 5 AND total_tx >= 10
           OR reciprocity > 0.5 AND out_degree >= 3
    Human: in_degree >= 2 AND out_degree >= 1
           AND reciprocity < 0.3 AND unique_interactions >= 3
    Unknown: everything else (masked out of loss)
```

#### Training Details

| Hyperparameter | Value |
|---|---|
| Optimiser | Adam (lr=5e-4, weight_decay=1e-4) |
| LR schedule | CosineAnnealingLR (T_max=300) |
| Early stopping | patience=30 on val_loss |
| Feature scaling | RobustScaler (handles extreme outliers) |
| Train/Val/Test split | 60 / 20 / 20 of labeled nodes |

#### Results

| Metric | Value |
|---|---|
| Precision (Sybil) | 1.0000 |
| Recall (Sybil) | 1.0000 |
| F1-Score | 1.0000 |
| ROC-AUC | 1.0000 |
| False Positives | 0 |
| False Negatives | 0 |

---

### 5. Smart Contract (`contracts/contracts/SybilNet.sol`)

#### State Machine

```
                    ┌──────────┐
                    │   None   │ (no credential)
                    └────┬─────┘
                         │ mintCredential() + stake >= 0.01 ETH
                         ▼
                    ┌──────────┐
               ┌───│  Active  │◄──────────────────────────┐
               │   └────┬─────┘                           │
               │        │ oracle score >= 70               │ liftSuspension()
               │        ▼                                  │
               │   ┌───────────┐                          │
               │   │ Suspended │──────────────────────────┘
               │   └────┬──────┘
               │        │ slash() / withdrawStake()
               │        ▼
               │   ┌─────────┐
               └──►│ Revoked │  ← 365-day ban if slashed
                   └─────────┘
```

#### Role Permissions

| Function | Admin | Oracle | Guardian | User |
|---|---|---|---|---|
| `mintCredential()` | — | — | — | ✅ |
| `withdrawStake()` | — | — | — | ✅ |
| `updateSybilScore()` | — | ✅ | — | — |
| `slash()` | — | ✅ | — | — |
| `batchSlash()` | — | ✅ | — | — |
| `liftSuspension()` | — | ✅ | — | — |
| `setMinStake()` | ✅ | — | — | — |
| `setTreasury()` | ✅ | — | — | — |
| `pause()` / `unpause()` | — | — | ✅ | — |

#### Slash Fund Distribution

```
Slashed ETH
    ├── 10% → Reporter (oracle wallet or whistleblower)
    └── 90% → Treasury (protocol multisig)
```

#### Gas Costs (Ethereum Mainnet estimate at 20 gwei)

| Operation | Gas | ~USD |
|---|---|---|
| Deploy | 1,753,917 | ~$5.25 |
| mintCredential() | 122,824 | ~$0.37 |
| updateSybilScore() | 66,431 | ~$0.20 |
| slash() | 106,965 | ~$0.32 |
| batchSlash(3 wallets) | 175,343 | ~$0.53 |

---

### 6. Oracle Bridge (`contracts/oracle_bridge.py`)

The Python glue between the GNN and the smart contract:

```
node_scores.csv
      │
      ├── score >= 85%  →  slash(wallet, oracle) ────────► Contract
      ├── score 60–85%  →  updateSybilScore(wallet, score) ► Contract
      └── score < 60%   →  No action
```

---

## Data Flow (End to End)

```
1.  Alchemy API / Synthetic generator
        │  transactions.csv + labels.csv
        ▼
2.  graph/builder.py
        │  graph.pkl  (NetworkX DiGraph)
        ▼
3.  features/extractor.py
        │  features.csv  (43k × 12)
        ▼
4.  models/gnn.py  (GraphSAGE training)
        │  sybil_sage.pt + node_scores.csv
        ▼
5.  contracts/oracle_bridge.py  (web3.py)
        │  updateSybilScore() / slash() calls
        ▼
6.  SybilNet.sol  (on-chain enforcement)
        │  Humanity Credential  (ERC-like badge)
        ▼
7.  Marketplace (roadmap)
        │  isVerifiedHuman() gate
        ▼
    Asset Exchange  |  Credit Hub  |  Yield Hub
```

---

## Roadmap

| Week | Feature | Status |
|------|---------|--------|
| 1 | Data Pipeline | ✅ Complete |
| 2 | GNN Model (GraphSAGE) | ✅ Complete |
| 3 | Smart Contract + Oracle Bridge | ✅ Complete |
| 4 | Marketplace UI + Real-time Dashboard | 🔲 Next |
| 5 | Mempool Monitor (MEV/sandwich detection) | 🔲 Planned |
| 6 | Polish + Integration Tests | 🔲 Planned |
| 7 | Presentation + Final README | 🔲 Planned |
| 8 | zk-SNARK Privacy Layer (stretch goal) | 🔲 Stretch |

---

## Security Considerations

- **Reentrancy**: All state changes happen before ETH transfers (Checks-Effects-Interactions pattern)
- **Role separation**: Oracle cannot change protocol parameters; admin cannot slash wallets
- **Emergency pause**: Guardian can freeze all user-facing functions instantly
- **Ban duration**: Slashed wallets cannot re-enter the protocol for 365 days
- **Reporter fee cap**: Slash reporter fee capped at 30% to prevent oracle self-dealing
- **Score validation**: Contract rejects any score > 100 from the oracle
