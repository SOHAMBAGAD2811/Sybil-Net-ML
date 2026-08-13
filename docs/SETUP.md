# Setup Guide

Complete setup instructions for running the full Sybil-Net stack locally.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | >= 3.11 | [python.org](https://python.org) |
| Node.js | >= 18 | [nodejs.org](https://nodejs.org) |
| npm | >= 9 | Bundled with Node.js |
| Git | any | [git-scm.com](https://git-scm.com) |

---

## 1. Clone and Set Up Python Environment

```bash
git clone https://github.com/your-username/Sybil-Net-ML.git
cd Sybil-Net-ML

python3 -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 2. Configure Environment Variables

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Get a FREE key at https://dashboard.alchemy.com/
# Select: Create App -> Ethereum Mainnet -> copy API Key
ALCHEMY_API_KEY=alch_your_key_here

# Only needed for oracle_bridge.py (smart contract integration)
# ORACLE_PRIVATE_KEY=0x...
# SYBILNET_ADDRESS=0x...
# RPC_URL=http://127.0.0.1:8545
```

> If `ALCHEMY_API_KEY` is blank or invalid, the pipeline automatically falls back
> to the realistic synthetic Sybil data generator — no key needed to get started.

---

## 3. Run the Full ML Pipeline

```bash
python main.py
```

This runs all 6 steps sequentially:

```
Step 1: Data Ingestion     — 50k transactions (Alchemy or synthetic)
Step 2: Graph Construction — NetworkX DiGraph (wallets + tx edges)
Step 3: Feature Extraction — 12 node features per wallet
Step 4: Dataset Export     — nodes.csv, edges.csv, features.csv
Step 5: Visualization      — interactive HTML graph
Step 6: GNN Training       — GraphSAGE model, outputs node_scores.csv
```

**Expected runtime:** 3–8 minutes depending on graph size and hardware.

### Run Individual Steps

```bash
# Data ingestion only
python data/ingestion.py

# Graph construction only
python graph/builder.py

# Feature extraction only
python features/extractor.py

# GNN training only
python models/gnn.py
```

---

## 4. View the Graph Visualization

Open the generated HTML file in any browser:

```bash
# Linux
xdg-open visualization/graph_visualization.html

# macOS
open visualization/graph_visualization.html

# Or just open the file directly in Chrome / Firefox
```

The interactive graph shows:
- **Violet nodes** — Hub wallets (degree > 50)
- **Red nodes** — Active wallets (degree 21–50)
- **Amber nodes** — Medium wallets (degree 6–20)
- **Cyan nodes** — Standard wallets (degree <= 5)

Hover over any node to see its address, degree, and classification.

---

## 5. Smart Contract Setup

### Install Contract Dependencies

```bash
cd contracts
npm install
```

### Compile Contracts

```bash
npx hardhat compile
```

### Run Tests

```bash
npx hardhat test
```

Expected output: **22 passing**

### Deploy Locally

```bash
# Terminal 1: Start local Hardhat node
npx hardhat node

# Terminal 2: Deploy contract
npx hardhat run scripts/deploy.js --network localhost
```

Copy the deployed contract address and add it to `../.env`:
```env
SYBILNET_ADDRESS=0x...
```

### Deploy to Sepolia Testnet

Add your deployer private key to `../.env`:
```env
DEPLOYER_PRIVATE_KEY=0x...your_key...
```

Get testnet ETH from the [Sepolia faucet](https://sepoliafaucet.com/), then:
```bash
npx hardhat run scripts/deploy.js --network sepolia
```

---

## 6. Run the Oracle Bridge

The oracle bridge reads GNN scores and submits them to the smart contract:

```bash
# From repo root
pip install web3
python contracts/oracle_bridge.py
```

Required env vars:
```env
SYBILNET_ADDRESS=0x...     # deployed contract address
ORACLE_PRIVATE_KEY=0x...   # wallet with ORACLE_ROLE
RPC_URL=http://127.0.0.1:8545  # or Sepolia/Mainnet RPC
```

---

## Output Files Reference

After running `python main.py`, these files are generated:

| File | Location | Description |
|---|---|---|
| `transactions.csv` | `data/raw/` | Raw blockchain transactions |
| `labels.csv` | `data/raw/` | Ground-truth Sybil labels (synthetic mode) |
| `graph.pkl` | `data/processed/` | Serialised NetworkX DiGraph |
| `features.csv` | `data/processed/` | 12 node features per wallet |
| `nodes.csv` | `data/processed/` | Node list (PyG compatible) |
| `edges.csv` | `data/processed/` | Edge list with attributes |
| `sybil_sage.pt` | `data/processed/` | Trained GraphSAGE model weights |
| `node_scores.csv` | `data/processed/` | Per-wallet Sybil probability |
| `training_history.csv` | `data/processed/` | Loss/accuracy per epoch |
| `graph_visualization.html` | `visualization/` | Interactive graph explorer |

---

## Troubleshooting

### Alchemy key not working
- Ensure the key is at least 20 characters long
- The key must be for an **Ethereum Mainnet** app in your Alchemy dashboard
- If the key fails validation, the pipeline silently switches to synthetic data

### PyTorch not found
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install torch_geometric
```

### Hardhat compile errors
```bash
cd contracts && npm install
npx hardhat clean && npx hardhat compile
```

### Out of memory during feature extraction
For very large graphs (>100k nodes), the betweenness centrality sampling is already limited to 500 nodes. If still OOM, reduce it in `features/extractor.py`:
```python
k_sample = min(n, 200)  # reduce from 500
```
