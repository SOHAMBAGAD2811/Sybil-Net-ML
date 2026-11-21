"""
mempool/monitor.py
─────────────────────────────────────────────────────────────────────────────
Week 5 — Real-Time Mempool Monitor
─────────────────────────────────────────────────────────────────────────────

Connects to Alchemy WebSocket and subscribes to pending transactions.
For each batch of pending txs it:
  1. Fetches full tx details (from, to, value, gas)
  2. Builds a micro NetworkX graph of the new senders/receivers
  3. Computes the same 12 node features used to train the GNN
  4. Loads the saved GraphSAGE weights and runs inference
  5. Appends flagged wallets to data/processed/mempool_alerts.json
     (the Next.js frontend tails this file via SSE)

Usage:
    python mempool/monitor.py

Requirements:
    ALCHEMY_API_KEY in .env (same key used by data/ingestion.py)
    Trained model at data/processed/sybil_sage.pt
"""

import os
import sys
import json
import time
import asyncio
import pickle
import logging
import numpy as np
import pandas as pd
import networkx as nx
import torch
import torch.nn.functional as F
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))
load_dotenv(ROOT / ".env")

from torch_geometric.nn import SAGEConv
from torch_geometric.data import Data
from sklearn.preprocessing import RobustScaler

# ── Config ────────────────────────────────────────────────────────────────────
ALCHEMY_API_KEY   = os.getenv("ALCHEMY_API_KEY", "")
WS_URL            = f"wss://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

MODEL_PATH        = ROOT / "data" / "processed" / "sybil_sage.pt"
FEATURES_CSV      = ROOT / "data" / "processed" / "features.csv"
GRAPH_PKL         = ROOT / "data" / "processed" / "graph.pkl"
ALERTS_PATH       = ROOT / "data" / "processed" / "mempool_alerts.json"

# How many pending tx hashes to batch before fetching details + running GNN
BATCH_SIZE        = 10
# Max alerts to keep in the JSON file (ring-buffer)
MAX_ALERTS        = 200
# Sybil probability threshold to emit an alert
ALERT_THRESHOLD   = 0.60
# How long to simulate in demo mode between synthetic batches (seconds)
DEMO_INTERVAL     = 2.0

FEATURE_COLS = [
    "in_degree", "out_degree", "total_tx_count", "unique_interactions",
    "avg_value_sent", "avg_gas", "tx_frequency", "node_age_days",
    "reciprocity", "clustering_coeff", "betweenness_centrality", "pagerank",
]

HIDDEN_DIM = 128
DROPOUT    = 0.4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mempool")


# ─────────────────────────────────────────────────────────────────────────────
#  GNN model definition (must match models/gnn.py exactly)
# ─────────────────────────────────────────────────────────────────────────────

class SybilSAGE(torch.nn.Module):
    def __init__(self, in_channels: int, hidden: int = HIDDEN_DIM, dropout: float = DROPOUT):
        super().__init__()
        self.conv1   = SAGEConv(in_channels, hidden, aggr="mean")
        self.bn1     = torch.nn.BatchNorm1d(hidden)
        self.conv2   = SAGEConv(hidden, hidden, aggr="mean")
        self.bn2     = torch.nn.BatchNorm1d(hidden)
        self.conv3   = SAGEConv(hidden, 2, aggr="mean")
        self.dropout = dropout

    def forward(self, x, edge_index):
        x = F.relu(self.bn1(self.conv1(x, edge_index)))
        x = F.dropout(x, p=self.dropout, training=self.training)
        x = F.relu(self.bn2(self.conv2(x, edge_index)))
        x = F.dropout(x, p=self.dropout, training=self.training)
        return F.log_softmax(self.conv3(x, edge_index), dim=1)

    @torch.no_grad()
    def predict_proba(self, x, edge_index):
        self.eval()
        return self.forward(x, edge_index).exp()[:, 1].numpy()


# ─────────────────────────────────────────────────────────────────────────────
#  Load trained model + baseline graph context
# ─────────────────────────────────────────────────────────────────────────────

def load_model_and_context():
    """
    Load the trained GraphSAGE weights and the baseline feature scaler
    (fitted on the full training set so inference is on the same scale).
    """
    log.info("Loading trained GNN from %s", MODEL_PATH)
    if not MODEL_PATH.exists():
        log.error("Model not found. Run: python models/gnn.py first.")
        sys.exit(1)

    # Load baseline features to fit the scaler
    df_base = pd.read_csv(FEATURES_CSV)
    X_base  = df_base[FEATURE_COLS].values.astype(np.float32)
    scaler  = RobustScaler()
    scaler.fit(X_base)

    # Load baseline graph for neighbourhood context
    with open(GRAPH_PKL, "rb") as f:
        G_base = pickle.load(f)

    # Instantiate model and load weights
    model = SybilSAGE(in_channels=len(FEATURE_COLS))
    state = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model.eval()
    log.info("Model loaded. Baseline graph: %d nodes, %d edges",
             G_base.number_of_nodes(), G_base.number_of_edges())

    return model, scaler, G_base, df_base


# ─────────────────────────────────────────────────────────────────────────────
#  Feature computation for a micro-graph of pending txs
# ─────────────────────────────────────────────────────────────────────────────

def compute_features_for_wallets(
    pending_txs: list[dict],
    G_base: nx.DiGraph,
    df_base: pd.DataFrame,
) -> tuple[pd.DataFrame, nx.DiGraph]:
    """
    Build a temporary graph merging the pending txs with the baseline graph,
    then compute the same 12 features for the new wallets.
    Returns a DataFrame of features (one row per new wallet).
    """
    # Collect unique new wallets
    new_wallets = set()
    for tx in pending_txs:
        if tx.get("from"): new_wallets.add(tx["from"].lower())
        if tx.get("to"):   new_wallets.add(tx["to"].lower())

    # Build micro-graph (new edges only)
    G_micro = G_base.copy()
    now_ts  = int(time.time())

    for tx in pending_txs:
        src = tx.get("from", "").lower()
        dst = tx.get("to",   "").lower()
        if not src or not dst:
            continue
        val = int(tx.get("value", 0) or 0, 16) if isinstance(tx.get("value"), str) else int(tx.get("value", 0) or 0)
        gas = int(tx.get("gas",   21000) or 21000, 16) if isinstance(tx.get("gas"), str) else int(tx.get("gas", 21000) or 21000)

        if G_micro.has_edge(src, dst):
            G_micro[src][dst]["tx_count"]   += 1
            G_micro[src][dst]["total_value"] += val
        else:
            G_micro.add_edge(src, dst, tx_count=1, total_value=val,
                             avg_gas=gas, first_ts=now_ts, last_ts=now_ts)

    # Stats dict from existing features CSV (for known wallets)
    known_stats = {row["node_id"]: row for _, row in df_base.iterrows()}

    rows = []
    for wallet in new_wallets:
        if wallet in known_stats:
            # Known wallet — use existing features
            rows.append(known_stats[wallet].to_dict())
            continue

        # New wallet — compute fresh features from micro-graph
        in_deg  = G_micro.in_degree(wallet)  if G_micro.has_node(wallet) else 0
        out_deg = G_micro.out_degree(wallet) if G_micro.has_node(wallet) else 0

        out_edges = list(G_micro.out_edges(wallet, data=True))
        total_tx  = sum(d.get("tx_count", 1) for _, _, d in out_edges)
        unique_nb = len(set(v for _, v, _ in out_edges))
        avg_val   = (sum(d.get("total_value", 0) for _, _, d in out_edges) / max(total_tx, 1))
        avg_gas   = (sum(d.get("avg_gas", 21000) for _, _, d in out_edges) / max(len(out_edges), 1))

        # Basic graph metrics (fast approximations for live inference)
        try:
            recip = nx.reciprocity(G_micro, wallet) if G_micro.has_node(wallet) else 0.0
        except Exception:
            recip = 0.0
        try:
            clust = nx.clustering(G_micro.to_undirected(), wallet) if G_micro.has_node(wallet) else 0.0
        except Exception:
            clust = 0.0

        rows.append({
            "node_id":               wallet,
            "in_degree":             in_deg,
            "out_degree":            out_deg,
            "total_tx_count":        max(total_tx, 1),
            "unique_interactions":   unique_nb,
            "avg_value_sent":        avg_val,
            "avg_gas":               avg_gas,
            "tx_frequency":          total_tx / max(1, 1),  # 1-day window
            "node_age_days":         0,                      # new wallet
            "reciprocity":           recip,
            "clustering_coeff":      clust,
            "betweenness_centrality": 0.0,                  # too slow for live
            "pagerank":              0.0,
        })

    return pd.DataFrame(rows), G_micro


# ─────────────────────────────────────────────────────────────────────────────
#  Run GNN inference on a batch of pending transactions
# ─────────────────────────────────────────────────────────────────────────────

def run_inference(
    pending_txs: list[dict],
    model: SybilSAGE,
    scaler: RobustScaler,
    G_base: nx.DiGraph,
    df_base: pd.DataFrame,
) -> list[dict]:
    """
    Run the trained GNN on the current batch of pending txs.
    Returns a list of alert dicts for wallets above ALERT_THRESHOLD.
    """
    if not pending_txs:
        return []

    df_feat, G_micro = compute_features_for_wallets(pending_txs, G_base, df_base)
    if df_feat.empty:
        return []

    wallets = df_feat["node_id"].tolist()
    X_raw   = df_feat[FEATURE_COLS].fillna(0).values.astype(np.float32)
    X_scaled = scaler.transform(X_raw).astype(np.float32)
    x        = torch.tensor(X_scaled, dtype=torch.float)

    # Build edge_index for the micro-graph (wallet subset only)
    node_idx = {w: i for i, w in enumerate(wallets)}
    src_list, dst_list = [], []
    for u, v in G_micro.edges():
        if u in node_idx and v in node_idx:
            src_list.append(node_idx[u])
            dst_list.append(node_idx[v])

    if src_list:
        edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)

    probs = model.predict_proba(x, edge_index)

    alerts = []
    ts_now = datetime.now(timezone.utc).isoformat()

    for wallet, prob in zip(wallets, probs):
        prob_f = float(prob)
        # Find a pending tx involving this wallet
        tx_hash = next(
            (tx.get("hash", "0x???") for tx in pending_txs
             if tx.get("from", "").lower() == wallet or tx.get("to", "").lower() == wallet),
            "0x???"
        )
        val_wei = next(
            (int(tx.get("value", 0) or 0, 16) if isinstance(tx.get("value"), str)
             else int(tx.get("value", 0) or 0)
             for tx in pending_txs
             if tx.get("from", "").lower() == wallet),
            0,
        )
        classification = "Sybil" if prob_f >= 0.5 else "Human"
        alert_level    = (
            "critical" if prob_f >= 0.85 else
            "warning"  if prob_f >= ALERT_THRESHOLD else
            "clean"
        )

        entry = {
            "timestamp":        ts_now,
            "wallet":           wallet,
            "tx_hash":          tx_hash,
            "sybil_probability": round(prob_f, 6),
            "classification":   classification,
            "alert_level":      alert_level,
            "value_eth":        round(val_wei / 1e18, 6),
            "status":           "pending",
        }

        if prob_f >= ALERT_THRESHOLD:
            log.warning("🚨 ALERT  %s  prob=%.3f  tx=%s", wallet[:16], prob_f, tx_hash[:14])
        else:
            log.info  ("✅ Clean  %s  prob=%.3f", wallet[:16], prob_f)

        alerts.append(entry)

    return alerts


# ─────────────────────────────────────────────────────────────────────────────
#  Alerts file writer
# ─────────────────────────────────────────────────────────────────────────────

def append_alerts(new_alerts: list[dict]):
    """Append new alerts to the ring-buffer JSON file."""
    ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if ALERTS_PATH.exists():
        try:
            existing = json.loads(ALERTS_PATH.read_text())
        except Exception:
            existing = []

    combined = new_alerts + existing        # newest first
    combined = combined[:MAX_ALERTS]        # ring-buffer cap

    ALERTS_PATH.write_text(json.dumps(combined, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
#  Demo mode — synthetic pending tx stream
# ─────────────────────────────────────────────────────────────────────────────

def make_demo_batch(df_base: pd.DataFrame, batch_num: int) -> list[dict]:
    """
    Generate a realistic synthetic batch of pending transactions by sampling
    from known wallets (mix of Sybil + Human) with random values/gas.
    """
    rng = np.random.default_rng(seed=batch_num)

    n       = BATCH_SIZE
    senders = df_base.sample(n, replace=True, random_state=batch_num)["node_id"].tolist()
    recvrs  = df_base.sample(n, replace=True, random_state=batch_num + 1000)["node_id"].tolist()

    txs = []
    for i in range(n):
        val = int(rng.uniform(0, 5e18))   # 0–5 ETH in wei
        gas = int(rng.choice([21000, 50000, 100000, 200000]))
        txs.append({
            "hash":  f"0x{''.join(rng.integers(0,16,64).astype(str))}",
            "from":  senders[i],
            "to":    recvrs[i],
            "value": val,
            "gas":   gas,
        })
    return txs


# ─────────────────────────────────────────────────────────────────────────────
#  Live WebSocket mode
# ─────────────────────────────────────────────────────────────────────────────

async def run_live(model, scaler, G_base, df_base):
    """Connect to Alchemy WebSocket and stream pending transactions."""
    import websockets

    log.info("Connecting to Alchemy WebSocket: %s", WS_URL[:60] + "…")

    pending_hashes = []
    pending_txs    = []

    async with websockets.connect(WS_URL, ping_interval=20) as ws:
        # Subscribe to pending transactions
        await ws.send(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "eth_subscribe",
            "params": ["alchemy_pendingTransactions", {"toAddress": [], "hashesOnly": False}]
        }))
        resp = json.loads(await ws.recv())
        sub_id = resp.get("result")
        log.info("Subscribed to pending txs. Subscription ID: %s", sub_id)

        async for raw_msg in ws:
            msg = json.loads(raw_msg)
            tx  = msg.get("params", {}).get("result", {})
            if not tx:
                continue

            pending_txs.append(tx)

            if len(pending_txs) >= BATCH_SIZE:
                batch, pending_txs = pending_txs[:BATCH_SIZE], pending_txs[BATCH_SIZE:]
                alerts = run_inference(batch, model, scaler, G_base, df_base)
                if alerts:
                    append_alerts(alerts)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    model, scaler, G_base, df_base = load_model_and_context()

    if not ALCHEMY_API_KEY:
        log.warning("ALCHEMY_API_KEY not set — running in DEMO mode (synthetic stream)")
        run_demo(model, scaler, G_base, df_base)
    else:
        log.info("ALCHEMY_API_KEY found — connecting to live mempool")
        try:
            asyncio.run(run_live(model, scaler, G_base, df_base))
        except KeyboardInterrupt:
            log.info("Monitor stopped.")
        except Exception as e:
            log.error("WebSocket error: %s — falling back to demo mode", e)
            run_demo(model, scaler, G_base, df_base)


def run_demo(model, scaler, G_base, df_base):
    """Simulate a live mempool stream using synthetic tx batches."""
    log.info("=== DEMO MODE: Generating synthetic mempool stream ===")
    log.info("Alerts will be written to: %s", ALERTS_PATH)
    log.info("Press Ctrl+C to stop.\n")

    batch_num = 0
    try:
        while True:
            batch   = make_demo_batch(df_base, batch_num)
            alerts  = run_inference(batch, model, scaler, G_base, df_base)
            if alerts:
                append_alerts(alerts)
                log.info("Wrote %d alerts  (total in file: up to %d)", len(alerts), MAX_ALERTS)
            batch_num += 1
            time.sleep(DEMO_INTERVAL)
    except KeyboardInterrupt:
        log.info("Demo stopped.")


if __name__ == "__main__":
    main()
