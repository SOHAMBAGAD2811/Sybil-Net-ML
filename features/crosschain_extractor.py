"""
features/crosschain_extractor.py
─────────────────────────────────────────────────────────────────────────────
Week 7 — Cross-Chain Feature Extractor

Extends the original 12 node features with 5 cross-chain features:
  13. num_chains_active    — distinct chains the wallet is active on
  14. bridge_tx_count      — number of bridge transactions
  15. bridge_tx_ratio      — bridge_tx_count / total_tx_count
  16. cross_chain_degree   — unique wallets interacted with on OTHER chains
  17. bridge_hop_count     — times wallet moved funds through bridge contracts
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import pickle
import time
import networkx as nx
import pandas as pd
import numpy as np
from dateutil import parser as dateutil_parser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH, RAW_MULTICHAIN_PATH, BRIDGE_ADDRESSES


# All 17 feature columns (original 12 + 5 cross-chain)
MULTICHAIN_FEATURE_COLS = [
    "in_degree", "out_degree", "total_tx_count", "unique_interactions",
    "avg_value_sent", "avg_gas", "tx_frequency", "node_age_days",
    "reciprocity", "clustering_coeff", "betweenness_centrality", "pagerank",
    # Cross-chain features (Week 7)
    "num_chains_active", "bridge_tx_count", "bridge_tx_ratio",
    "cross_chain_degree", "bridge_hop_count",
]


def _to_unix(ts) -> int:
    """Convert a timestamp to Unix integer (handles int/float/ISO strings)."""
    if ts is None or (isinstance(ts, float) and np.isnan(ts)):
        return 0
    if isinstance(ts, (int, float)):
        v = int(ts)
        return v if v > 1_000_000 else 0
    ts_str = str(ts).strip()
    if not ts_str or ts_str in ("nan", "0", ""):
        return 0
    try:
        return int(float(ts_str))
    except ValueError:
        pass
    try:
        return int(dateutil_parser.parse(ts_str).timestamp())
    except Exception:
        return 0


def _load_raw_tx_stats(df_raw: pd.DataFrame) -> dict:
    """Pre-compute per-address stats from the raw multichain CSV."""
    stats: dict = {}

    df_raw = df_raw.copy()
    df_raw["value"]    = pd.to_numeric(df_raw["value"],    errors="coerce").fillna(0)
    df_raw["gas"]      = pd.to_numeric(df_raw["gas"],      errors="coerce").fillna(21_000)
    df_raw["_unix_ts"] = df_raw["timeStamp"].apply(_to_unix)
    df_raw["is_bridge_tx"] = df_raw["is_bridge_tx"].astype(str).str.lower().isin(["true", "1"])

    for addr, grp in df_raw.groupby("from"):
        s = stats.setdefault(addr, {})
        s["sent_count"]     = len(grp)
        s["avg_value_sent"] = float(grp["value"].mean())
        s["avg_gas"]        = float(grp["gas"].mean())
        ts_vals = grp["_unix_ts"][grp["_unix_ts"] > 0]
        s["first_ts"] = int(ts_vals.min()) if not ts_vals.empty else 0
        s["last_ts"]  = int(ts_vals.max()) if not ts_vals.empty else 0

        # Cross-chain stats from sender perspective
        s["bridge_tx_sent"] = int(grp["is_bridge_tx"].sum())
        s["chains_sent_on"] = set(grp["chain_id"].unique())

    for addr, grp in df_raw.groupby("to"):
        s = stats.setdefault(addr, {})
        ts_vals = grp["_unix_ts"][grp["_unix_ts"] > 0]
        ts_min = int(ts_vals.min()) if not ts_vals.empty else 0
        ts_max = int(ts_vals.max()) if not ts_vals.empty else 0
        s["first_ts"] = min(s.get("first_ts", ts_min), ts_min) if ts_min else s.get("first_ts", 0)
        s["last_ts"]  = max(s.get("last_ts",  ts_max), ts_max)

        # Cross-chain stats from receiver perspective
        s["bridge_tx_recv"] = s.get("bridge_tx_recv", 0) + int(grp["is_bridge_tx"].sum())
        existing_chains = s.get("chains_recv_on", set())
        s["chains_recv_on"] = existing_chains | set(grp["chain_id"].unique())

    return stats


def extract_multichain_features(
    graph_path: str = None,
    raw_data_path: str = None,
) -> pd.DataFrame:
    """
    Load the pickled multichain graph and raw CSV, then compute 17 features
    per node (12 original + 5 cross-chain). Saves features_multichain.csv.
    """
    if not graph_path:
        graph_path = os.path.join(PROCESSED_DATA_PATH, "graph_multichain.pkl")
    if not raw_data_path:
        raw_data_path = RAW_MULTICHAIN_PATH

    # ── Load graph ───────────────────────────────────────────────────────────
    print("[MC-Features] Loading multichain graph…")
    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    n = G.number_of_nodes()
    print(f"[MC-Features] Graph has {n:,} nodes and {G.number_of_edges():,} edges.")

    # ── Load raw transactions ────────────────────────────────────────────────
    raw_stats: dict = {}
    if os.path.exists(raw_data_path):
        print("[MC-Features] Loading raw multichain data for per-address stats…")
        df_raw = pd.read_csv(raw_data_path)
        raw_stats = _load_raw_tx_stats(df_raw)
    else:
        print("[MC-Features] Raw CSV not found — cross-chain features will be 0.")

    # ── Graph-level metrics ──────────────────────────────────────────────────
    print("[MC-Features] Computing degree metrics…")
    in_deg   = dict(G.in_degree())
    out_deg  = dict(G.out_degree())
    in_deg_w = dict(G.in_degree(weight="weight"))
    out_deg_w = dict(G.out_degree(weight="weight"))

    print("[MC-Features] Computing PageRank…")
    try:
        pagerank = nx.pagerank(G, weight="weight", max_iter=300)
    except nx.PowerIterationFailedConvergence:
        pagerank = {nd: 1.0 / n for nd in G.nodes()}

    print("[MC-Features] Computing clustering coefficient…")
    clustering = nx.clustering(G)

    print("[MC-Features] Computing betweenness centrality (sampled)…")
    k_sample = min(n, 500)
    betweenness = nx.betweenness_centrality(G, k=k_sample, weight="weight", normalized=True)

    print("[MC-Features] Computing per-node reciprocity…")
    node_reciprocity: dict = {}
    for node in G.nodes():
        out_nbrs = set(G.successors(node))
        out_nbrs.discard(node)  # exclude self-loops
        if not out_nbrs:
            node_reciprocity[node] = 0.0
        else:
            reciprocal = sum(1 for nb in out_nbrs if G.has_edge(nb, node))
            node_reciprocity[node] = reciprocal / len(out_nbrs)

    # ── Cross-chain edge analysis ────────────────────────────────────────────
    print("[MC-Features] Computing cross-chain features…")
    bridge_tx_per_node: dict[str, int] = {}
    cross_chain_neighbours: dict[str, set] = {}

    for u, v, data in G.edges(data=True):
        is_bridge = data.get("is_bridge_tx", False)
        edge_type = data.get("edge_type", "same_chain")

        if is_bridge or edge_type in ("bridge_hop", "cross_chain_identity"):
            bridge_tx_per_node[u] = bridge_tx_per_node.get(u, 0) + data.get("weight", 1)
            bridge_tx_per_node[v] = bridge_tx_per_node.get(v, 0) + data.get("weight", 1)

        # Cross-chain degree: neighbours on OTHER chains
        node_chains = G.nodes[u].get("chains", set())
        edge_chain = data.get("chain_id", 0)
        if edge_chain != 0 and edge_chain not in node_chains:
            cross_chain_neighbours.setdefault(u, set()).add(v)
        # Also from v's perspective
        v_chains = G.nodes[v].get("chains", set())
        if edge_chain != 0 and edge_chain not in v_chains:
            cross_chain_neighbours.setdefault(v, set()).add(u)

    # ── Assemble feature rows ────────────────────────────────────────────────
    print("[MC-Features] Assembling 17-feature matrix…")
    now_ts = int(time.time())
    features = []

    for node in G.nodes():
        rs = raw_stats.get(node, {})
        first_ts = rs.get("first_ts", 0)
        last_ts  = rs.get("last_ts",  0)

        total_tx = in_deg_w.get(node, 0) + out_deg_w.get(node, 0)

        if last_ts > first_ts:
            active_days  = max((last_ts - first_ts) / 86_400, 1)
            tx_frequency = total_tx / active_days
        else:
            tx_frequency = 0.0

        node_age_days = (now_ts - first_ts) / 86_400 if first_ts > 0 else 0.0

        neighbours = set(G.predecessors(node)) | set(G.successors(node))
        neighbours.discard(node)
        unique_interactions = len(neighbours)

        # Cross-chain features
        node_chains = G.nodes[node].get("chains", set())
        num_chains_active = len(node_chains) if node_chains else 1
        bridge_count = bridge_tx_per_node.get(node, 0)
        bridge_ratio = bridge_count / max(total_tx, 1)
        cross_chain_deg = len(cross_chain_neighbours.get(node, set()))

        # Bridge hop count from raw stats
        bridge_sent = rs.get("bridge_tx_sent", 0)
        bridge_recv = rs.get("bridge_tx_recv", 0)
        bridge_hop_count = bridge_sent + bridge_recv

        features.append({
            "node_id":                node,
            # Original 12 features
            "in_degree":              in_deg.get(node, 0),
            "out_degree":             out_deg.get(node, 0),
            "total_tx_count":         int(total_tx),
            "unique_interactions":    unique_interactions,
            "avg_value_sent":         round(rs.get("avg_value_sent", 0.0), 4),
            "avg_gas":                round(rs.get("avg_gas", 0.0), 2),
            "tx_frequency":           round(tx_frequency, 6),
            "node_age_days":          round(node_age_days, 2),
            "reciprocity":            round(node_reciprocity.get(node, 0.0), 6),
            "clustering_coeff":       round(clustering.get(node, 0.0), 6),
            "betweenness_centrality": round(betweenness.get(node, 0.0), 8),
            "pagerank":               round(pagerank.get(node, 0.0), 8),
            # Cross-chain features (Week 7)
            "num_chains_active":      num_chains_active,
            "bridge_tx_count":        bridge_count,
            "bridge_tx_ratio":        round(bridge_ratio, 6),
            "cross_chain_degree":     cross_chain_deg,
            "bridge_hop_count":       bridge_hop_count,
        })

    df_features = pd.DataFrame(features)
    features_path = os.path.join(PROCESSED_DATA_PATH, "features_multichain.csv")
    df_features.to_csv(features_path, index=False)
    print(f"[MC-Features] Saved {len(df_features):,} feature vectors (17 cols) → {features_path}")

    # Sanity checks
    multi_chain = (df_features["num_chains_active"] > 1).sum()
    has_bridge  = (df_features["bridge_tx_count"] > 0).sum()
    print(f"[MC-Features] Multi-chain wallets : {multi_chain:,}")
    print(f"[MC-Features] Bridge-active nodes : {has_bridge:,}")

    return df_features


if __name__ == "__main__":
    extract_multichain_features()
