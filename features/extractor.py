import os
import sys
import pickle
import time
import networkx as nx
import pandas as pd
import numpy as np
from dateutil import parser as dateutil_parser

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH, RAW_DATA_PATH

# ─────────────────────────────────────────────────────────────────────────────
#  Feature Extractor
#  Produces all node-level features specified in the Week-1 PRD (FR-4):
#    ✓ in_degree              ✓ out_degree          ✓ total_tx_count
#    ✓ unique_interactions    ✓ avg_value_sent       ✓ avg_gas
#    ✓ tx_frequency           ✓ node_age_days        ✓ reciprocity
#    ✓ clustering_coeff       ✓ betweenness_centrality ✓ pagerank
# ─────────────────────────────────────────────────────────────────────────────

def _to_unix(ts) -> int:
    """
    Convert a timestamp to a Unix integer.
    Handles:
      - Already-numeric unix timestamps (int / float)
      - ISO-8601 strings like '2024-01-15T12:34:56.000Z' (Alchemy format)
      - Empty / None / NaN → returns 0
    """
    if ts is None or (isinstance(ts, float) and np.isnan(ts)):
        return 0
    if isinstance(ts, (int, float)):
        v = int(ts)
        return v if v > 1_000_000 else 0   # reject obviously wrong values
    ts_str = str(ts).strip()
    if not ts_str or ts_str in ("nan", "0", ""):
        return 0
    try:
        return int(float(ts_str))           # numeric string
    except ValueError:
        pass
    try:
        return int(dateutil_parser.parse(ts_str).timestamp())   # ISO string
    except Exception:
        return 0


def _load_raw_tx_stats(df_raw: pd.DataFrame) -> dict:
    """
    Pre-compute per-address stats directly from the raw CSV that NetworkX
    does not easily expose (avg value sent, avg gas, timestamps for age/freq).
    """
    stats: dict = {}

    df_raw = df_raw.copy()
    df_raw["value"]     = pd.to_numeric(df_raw["value"],     errors="coerce").fillna(0)
    df_raw["gas"]       = pd.to_numeric(df_raw["gas"],       errors="coerce").fillna(21_000)
    df_raw["_unix_ts"]  = df_raw["timeStamp"].apply(_to_unix)

    # Per-sender
    for addr, grp in df_raw.groupby("from"):
        s = stats.setdefault(addr, {})
        s["sent_count"]     = len(grp)
        s["avg_value_sent"] = float(grp["value"].mean())
        s["avg_gas"]        = float(grp["gas"].mean())
        ts_vals = grp["_unix_ts"][grp["_unix_ts"] > 0]
        s["first_ts"] = int(ts_vals.min()) if not ts_vals.empty else 0
        s["last_ts"]  = int(ts_vals.max()) if not ts_vals.empty else 0

    # Per-receiver — merge timestamps
    for addr, grp in df_raw.groupby("to"):
        s = stats.setdefault(addr, {})
        ts_vals = grp["_unix_ts"][grp["_unix_ts"] > 0]
        ts_min = int(ts_vals.min()) if not ts_vals.empty else 0
        ts_max = int(ts_vals.max()) if not ts_vals.empty else 0
        s["first_ts"] = min(s.get("first_ts", ts_min), ts_min) if ts_min else s.get("first_ts", 0)
        s["last_ts"]  = max(s.get("last_ts",  ts_max), ts_max)

    return stats


def extract_features(graph_path: str = None, raw_data_path: str = None):
    """
    Load the pickled NetworkX graph and the raw CSV, then compute a rich
    feature vector for every node. Saves features.csv to PROCESSED_DATA_PATH.
    """
    if not graph_path:
        graph_path = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")
    if not raw_data_path:
        raw_data_path = RAW_DATA_PATH

    # ── Load graph ───────────────────────────────────────────────────────────
    print("[Features] Loading graph…")
    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    n = G.number_of_nodes()
    print(f"[Features] Graph has {n:,} nodes and {G.number_of_edges():,} edges.")

    # ── Load raw transactions ────────────────────────────────────────────────
    raw_stats: dict = {}
    if os.path.exists(raw_data_path):
        print("[Features] Loading raw transaction data for per-address stats…")
        df_raw = pd.read_csv(raw_data_path)
        raw_stats = _load_raw_tx_stats(df_raw)
        ts_nonzero = sum(1 for s in raw_stats.values() if s.get("first_ts", 0) > 0)
        print(f"[Features] Parsed timestamps for {ts_nonzero:,} / {len(raw_stats):,} addresses.")
    else:
        print("[Features] Raw CSV not found — value/gas/age features will be 0.")

    # ── Graph-level metrics ──────────────────────────────────────────────────
    print("[Features] Computing degree metrics…")
    in_deg   = dict(G.in_degree())
    out_deg  = dict(G.out_degree())
    in_deg_w = dict(G.in_degree(weight="weight"))
    out_deg_w = dict(G.out_degree(weight="weight"))

    print("[Features] Computing PageRank…")
    try:
        pagerank = nx.pagerank(G, weight="weight", max_iter=300)
    except nx.PowerIterationFailedConvergence:
        print("[Features]   PageRank did not converge — using uniform fallback.")
        pagerank = {nd: 1.0 / n for nd in G.nodes()}

    print("[Features] Computing clustering coefficient…")
    clustering = nx.clustering(G)

    print("[Features] Computing betweenness centrality (sampled)…")
    k_sample = min(n, 500)
    betweenness = nx.betweenness_centrality(G, k=k_sample, weight="weight", normalized=True)

    print("[Features] Computing per-node reciprocity…")
    node_reciprocity: dict = {}
    for node in G.nodes():
        out_nbrs = set(G.successors(node))
        if not out_nbrs:
            node_reciprocity[node] = 0.0
        else:
            reciprocal = sum(1 for nb in out_nbrs if G.has_edge(nb, node))
            node_reciprocity[node] = reciprocal / len(out_nbrs)

    # ── Assemble feature rows ────────────────────────────────────────────────
    print("[Features] Assembling feature matrix…")
    now_ts = int(time.time())
    features = []

    for node in G.nodes():
        rs = raw_stats.get(node, {})
        first_ts = rs.get("first_ts", 0)
        last_ts  = rs.get("last_ts",  0)

        total_tx = in_deg_w.get(node, 0) + out_deg_w.get(node, 0)

        # tx_frequency: txns per day over active window
        if last_ts > first_ts:
            active_days  = max((last_ts - first_ts) / 86_400, 1)
            tx_frequency = total_tx / active_days
        else:
            tx_frequency = 0.0

        # node_age_days: days since first observed transaction
        node_age_days = (now_ts - first_ts) / 86_400 if first_ts > 0 else 0.0

        # unique interactions: distinct neighbours
        neighbours = set(G.predecessors(node)) | set(G.successors(node))
        unique_interactions = len(neighbours)

        features.append({
            "node_id":                node,
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
        })

    df_features = pd.DataFrame(features)
    features_path = os.path.join(PROCESSED_DATA_PATH, "features.csv")
    df_features.to_csv(features_path, index=False)
    print(f"[Features] Saved {len(df_features):,} feature vectors → {features_path}")
    print(f"[Features] Feature columns: {list(df_features.columns)}")

    # Quick sanity check on timestamp-derived features
    nonzero_age  = (df_features["node_age_days"]  > 0).sum()
    nonzero_freq = (df_features["tx_frequency"]   > 0).sum()
    print(f"[Features] node_age_days  > 0 : {nonzero_age:,} nodes")
    print(f"[Features] tx_frequency   > 0 : {nonzero_freq:,} nodes")

    return df_features


if __name__ == "__main__":
    extract_features()
