"""
models/crosschain_gnn.py
─────────────────────────────────────────────────────────────────────────────
Week 7 — Cross-Chain GraphSAGE GNN

Extends the Week-2 GNN to work with the 17-feature multichain dataset.
Adds chain-aware label generation and a dedicated multichain pipeline.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH, RAW_MULTICHAIN_LABELS_PATH
from models.gnn import (
    SybilSAGE, train_gnn, evaluate_final, save_outputs,
    LABEL_UNKNOWN, LABEL_HUMAN, LABEL_SYBIL,
    HIDDEN_DIM, DROPOUT,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration — 17 features (12 original + 5 cross-chain)
# ─────────────────────────────────────────────────────────────────────────────

MULTICHAIN_FEATURE_COLS = [
    "in_degree", "out_degree", "total_tx_count", "unique_interactions",
    "avg_value_sent", "avg_gas", "tx_frequency", "node_age_days",
    "reciprocity", "clustering_coeff", "betweenness_centrality", "pagerank",
    # Cross-chain features
    "num_chains_active", "bridge_tx_count", "bridge_tx_ratio",
    "cross_chain_degree", "bridge_hop_count",
]


# ─────────────────────────────────────────────────────────────────────────────
#  Label generation for multichain data
# ─────────────────────────────────────────────────────────────────────────────

def generate_multichain_labels(df: pd.DataFrame) -> np.ndarray:
    """
    Load ground-truth labels from labels_multichain.csv when available.
    Falls back to topology + cross-chain heuristics.
    """
    labels_path = RAW_MULTICHAIN_LABELS_PATH

    if os.path.exists(labels_path):
        print(f"[MC-Labels] Loading ground-truth labels from {labels_path}")
        df_labels = pd.read_csv(labels_path)
        label_map = dict(zip(df_labels["address"], df_labels["is_sybil"]))

        labels = np.array([
            label_map.get(addr, LABEL_UNKNOWN) for addr in df["node_id"]
        ], dtype=np.int64)

        n_sybil   = int((labels == LABEL_SYBIL).sum())
        n_human   = int((labels == LABEL_HUMAN).sum())
        n_unknown = int((labels == LABEL_UNKNOWN).sum())
        print(f"[MC-Labels] Ground-truth: Sybil={n_sybil:,}  Human={n_human:,}  "
              f"Unknown={n_unknown:,}  ({(n_sybil+n_human)/len(df)*100:.1f}% labeled)")
        return labels

    # Heuristic fallback with cross-chain signals
    print("[MC-Labels] No labels_multichain.csv — using cross-chain heuristics.")
    labels = np.full(len(df), LABEL_UNKNOWN, dtype=np.int64)

    # Sybil signals: high bridge activity + high out-degree + high reciprocity
    sybil_mask = (
        ((df["out_degree"] >= 5) & (df["total_tx_count"] >= 10)) |
        ((df["reciprocity"] > 0.5) & (df["out_degree"] >= 3)) |
        ((df["bridge_tx_ratio"] > 0.5) & (df["bridge_tx_count"] >= 5)) |
        ((df["num_chains_active"] >= 3) & (df["bridge_tx_count"] >= 10))
    ).values
    labels[sybil_mask] = LABEL_SYBIL

    # Human signals: balanced activity, low bridge ratio
    human_mask = (
        (df["in_degree"]           >= 2) &
        (df["out_degree"]          >= 1) &
        (df["reciprocity"]         <  0.3) &
        (df["unique_interactions"] >= 3) &
        (df["bridge_tx_ratio"]     <  0.3)
    ).values
    labels[human_mask & (labels == LABEL_UNKNOWN)] = LABEL_HUMAN

    n_sybil   = int((labels == LABEL_SYBIL).sum())
    n_human   = int((labels == LABEL_HUMAN).sum())
    print(f"[MC-Labels] Heuristic: Sybil={n_sybil:,}  Human={n_human:,}")

    return labels


# ─────────────────────────────────────────────────────────────────────────────
#  PyG Data builder for 17-feature multichain graph
# ─────────────────────────────────────────────────────────────────────────────

def build_multichain_pyg_data(
    df_features: pd.DataFrame,
    G,
    labels: np.ndarray,
) -> Data:
    """
    Convert the multichain NetworkX graph + 17-feature DataFrame into a
    PyG Data object.
    """
    node_list = list(df_features["node_id"])
    node_idx  = {addr: i for i, addr in enumerate(node_list)}

    # Feature matrix (17 features)
    X_raw = df_features[MULTICHAIN_FEATURE_COLS].values.astype(np.float32)
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X_raw).astype(np.float32)
    x = torch.tensor(X_scaled, dtype=torch.float)

    # Edge index
    edge_src, edge_dst = [], []
    for u, v in G.edges():
        if u in node_idx and v in node_idx:
            edge_src.append(node_idx[u])
            edge_dst.append(node_idx[v])
    edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long)

    # Labels
    y = torch.tensor(labels, dtype=torch.long)

    # Train/val/test masks (only labeled nodes)
    labeled_idx = np.where(labels != LABEL_UNKNOWN)[0]
    np.random.seed(42)
    np.random.shuffle(labeled_idx)

    n_labeled = len(labeled_idx)
    n_train   = int(n_labeled * 0.60)
    n_val     = int(n_labeled * 0.20)

    train_idx = labeled_idx[:n_train]
    val_idx   = labeled_idx[n_train:n_train + n_val]
    test_idx  = labeled_idx[n_train + n_val:]

    n_nodes = len(node_list)
    train_mask = torch.zeros(n_nodes, dtype=torch.bool)
    val_mask   = torch.zeros(n_nodes, dtype=torch.bool)
    test_mask  = torch.zeros(n_nodes, dtype=torch.bool)
    train_mask[train_idx] = True
    val_mask[val_idx]     = True
    test_mask[test_idx]   = True

    data = Data(
        x=x,
        edge_index=edge_index,
        y=y,
        train_mask=train_mask,
        val_mask=val_mask,
        test_mask=test_mask,
        num_nodes=n_nodes,
    )
    print(f"[MC-PyG]  Nodes={data.num_nodes:,}  Edges={data.num_edges:,}  "
          f"Features={data.num_node_features}")
    print(f"[MC-PyG]  Train={train_mask.sum():,}  "
          f"Val={val_mask.sum():,}  Test={test_mask.sum():,}")
    return data


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point — multichain GNN pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_multichain_gnn_pipeline():
    """Run the full GNN pipeline on multi-chain data (17 features)."""
    print("=== Sybil-Net Cross-Chain GNN Training Pipeline ===\n")

    features_path = os.path.join(PROCESSED_DATA_PATH, "features_multichain.csv")
    graph_path    = os.path.join(PROCESSED_DATA_PATH, "graph_multichain.pkl")

    if not os.path.exists(features_path) or not os.path.exists(graph_path):
        print("[Error] features_multichain.csv or graph_multichain.pkl not found.")
        print("        Run the multichain pipeline first: python main.py --multichain")
        sys.exit(1)

    print("[Load] Reading multichain features…")
    df_features = pd.read_csv(features_path)
    print(f"       {len(df_features):,} nodes, {len(MULTICHAIN_FEATURE_COLS)} features each")

    print("[Load] Reading multichain graph…")
    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    print("\n[Labels] Generating labels…")
    labels = generate_multichain_labels(df_features)

    print("\n[PyG] Building PyTorch Geometric data object…")
    data = build_multichain_pyg_data(df_features, G, labels)

    # Train (reuse the same SybilSAGE model — it auto-adapts to input dim)
    model, history = train_gnn(data)

    # Evaluate
    preds, probas = evaluate_final(model, data)

    # Save with multichain-specific filenames
    model_path = os.path.join(PROCESSED_DATA_PATH, "sybil_sage_multichain.pt")
    torch.save(model.state_dict(), model_path)
    print(f"\n[Save] Multichain model → {model_path}")

    history_path = os.path.join(PROCESSED_DATA_PATH, "training_history_multichain.csv")
    history.to_csv(history_path, index=False)

    df_scores = df_features[["node_id"]].copy()
    df_scores["predicted_label"]   = preds
    df_scores["sybil_probability"] = np.round(probas, 6)
    df_scores["classification"]    = df_scores["predicted_label"].map(
        {LABEL_HUMAN: "Human", LABEL_SYBIL: "Sybil"}
    )
    scores_path = os.path.join(PROCESSED_DATA_PATH, "node_scores_multichain.csv")
    df_scores.to_csv(scores_path, index=False)
    print(f"[Save] Multichain scores → {scores_path}")

    n_sybil = (df_scores["predicted_label"] == LABEL_SYBIL).sum()
    print(f"\n[Result] {n_sybil:,} wallets flagged as Sybil "
          f"({n_sybil/len(df_scores)*100:.1f}% of all nodes)")

    print("\n=== Cross-Chain GNN Pipeline Complete ===")
    return model, df_scores


if __name__ == "__main__":
    run_multichain_gnn_pipeline()
