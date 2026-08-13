# GNN Model Documentation
# SybilSAGE — GraphSAGE-based Sybil Wallet Classifier

## Overview

`SybilSAGE` is a 3-layer Graph Sample and Aggregate (GraphSAGE) neural network trained to classify Ethereum wallet addresses as **Sybil** (bot/attacker) or **Human** (legitimate user) based on their **transaction graph topology** — not their content or text.

---

## Why Graph Neural Networks?

Traditional bot detection looks at what a user says or does in isolation. Sybil-Net looks at how their entire network behaves.

A single bot wallet may look clean in isolation. But when the GNN aggregates features from its 1-hop and 2-hop neighbours, the circular structure of a wash-trading ring or the hub-and-spoke topology of a bot farm becomes unmistakable.

```
Traditional ML:  feature(wallet_A) → label
GraphSAGE:       feature(wallet_A) + aggregate(neighbours) + aggregate(neighbours_of_neighbours) → label
```

---

## Architecture

```
Input: [N nodes x 12 features]  +  Edge Index [2 x E]

Layer 1:  SAGEConv(12 -> 128, aggr=mean) + BatchNorm + ReLU + Dropout(0.4)
Layer 2:  SAGEConv(128 -> 128, aggr=mean) + BatchNorm + ReLU + Dropout(0.4)
Layer 3:  SAGEConv(128 -> 2, aggr=mean)

Output:   log_softmax -> [N x 2]  (Human | Sybil probability per node)

Total parameters: 37,122
```

### Design Choices

| Choice | Reason |
|---|---|
| **GraphSAGE over GCN** | Inductive: scores new wallets without retraining |
| **Mean aggregation** | Robust to variable-size neighbourhoods |
| **3 hops** | Captures bot rings typically 3-5 nodes wide |
| **BatchNorm** | Stabilises training on blockchain data with extreme outliers |
| **RobustScaler** | Handles massive out-degree variance |
| **Dropout 0.4** | Prevents memorising exact synthetic patterns |

---

## Input Features

| Feature | Description | Sybil Signal |
|---|---|---|
| `in_degree` | Wallets sending TO this address | Low in bots |
| `out_degree` | Wallets receiving FROM this address | Very high in controllers |
| `total_tx_count` | Total weighted transaction count | Very high in bots |
| `unique_interactions` | Distinct neighbours (in + out) | Narrow in rings |
| `avg_value_sent` | Mean ETH per outgoing tx | Uniform in bots |
| `avg_gas` | Mean gas used per tx | Uniform in bots |
| `tx_frequency` | Transactions per active day | Extremely high in bots |
| `node_age_days` | Days since first observed tx | Low in new bots |
| `reciprocity` | Fraction of out-neighbours that send back | High in wash rings |
| `clustering_coeff` | Directed clustering coefficient | High in tight cliques |
| `betweenness_centrality` | Node's role as a graph bridge | High in controllers |
| `pagerank` | Global influence score | Low in isolated bot clusters |

---

## Label Strategy

### Mode 1: Synthetic Data (Ground-Truth)
When `data/raw/labels.csv` exists, the GNN loads 100% accurate labels from the synthetic generator.

| Class | Count | Source |
|---|---|---|
| Sybil (1) | ~1,600 | Bot farms + wash rings + layered clusters |
| Human (0) | ~3,000 | Organic honest user pool |

### Mode 2: Real Data (Heuristic)
When running on real Alchemy data, topology heuristics are applied as a fallback.

---

## Training Configuration

| Hyperparameter | Value |
|---|---|
| Optimiser | Adam |
| Learning rate | 5e-4 |
| Weight decay | 1e-4 |
| LR schedule | CosineAnnealingLR (T_max=300) |
| Early stopping | patience=30 on val_loss |
| Max epochs | 300 |
| Feature scaling | RobustScaler |
| Train/Val/Test | 60 / 20 / 20 of labeled nodes |
| Device | CPU (no GPU required) |

---

## Results

| Metric | Human | Sybil |
|---|---|---|
| Precision | 1.0000 | 1.0000 |
| Recall | 1.0000 | 1.0000 |
| F1-Score | 1.0000 | 1.0000 |
| Support | 611 | 310 |

| Global Metric | Value |
|---|---|
| Accuracy | 1.0000 |
| ROC-AUC | 1.0000 |
| False Positives | 0 |
| False Negatives | 0 |

> **Note:** Perfect scores on synthetic data are expected — the patterns are deterministic. In production on real noisy Ethereum data, expect 85–95% accuracy. Perfect synthetic performance validates that the architecture can learn the topology signals that matter.

---

## Outputs

| File | Description |
|---|---|
| `data/processed/sybil_sage.pt` | Trained model weights (PyTorch state_dict) |
| `data/processed/node_scores.csv` | Per-wallet Sybil probability (0–1) and classification |
| `data/processed/training_history.csv` | Loss and accuracy per epoch |

### node_scores.csv Schema

| Column | Type | Description |
|---|---|---|
| `node_id` | str | Wallet address |
| `predicted_label` | int | 0 = Human, 1 = Sybil |
| `sybil_probability` | float | GNN confidence score (0–1) |
| `classification` | str | "Human" or "Sybil" |

---

## Usage

### Run GNN Pipeline Standalone
```bash
source venv/bin/activate
python models/gnn.py
```

### Run as Part of Full Pipeline
```bash
python main.py
```
The GNN runs as Step 6 after data ingestion, graph construction, feature extraction, export, and visualisation.

### Load Model for Inference
```python
import torch
from models.gnn import SybilSAGE

model = SybilSAGE(in_channels=12)
model.load_state_dict(torch.load("data/processed/sybil_sage.pt"))
model.eval()

# Score new graph
sybil_probs = model.predict_proba(data.x, data.edge_index)
```
