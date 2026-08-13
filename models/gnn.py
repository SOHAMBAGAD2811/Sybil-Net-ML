"""
models/gnn.py
─────────────────────────────────────────────────────────────────────────────
Sybil-Net GNN Model — GraphSAGE-based Sybil Wallet Classifier
─────────────────────────────────────────────────────────────────────────────

Architecture: GraphSAGE (Hamilton et al., 2017)
  • Inductive — generalises to unseen nodes
  • Uses neighbourhood aggregation (mean) across 2 hops
  • 3-layer stack: SAGEConv → BatchNorm → ReLU → Dropout

Label strategy (semi-supervised heuristics on real data):
  • SYBIL   — wallets with extreme out_degree:in_degree ratio AND
              very high reciprocity (circular sending patterns)
  • HUMAN   — wallets with balanced degree + older age + normal reciprocity
  • UNKNOWN — everything else (masked out of loss computation)

This lets the model learn from the clearest examples while ignoring
ambiguous middle-ground wallets — standard practice for semi-supervised GNN.
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import SAGEConv
from torch_geometric.transforms import NormalizeFeatures
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import (
    classification_report, roc_auc_score, confusion_matrix
)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_COLS = [
    "in_degree", "out_degree", "total_tx_count", "unique_interactions",
    "avg_value_sent", "avg_gas", "tx_frequency", "node_age_days",
    "reciprocity", "clustering_coeff", "betweenness_centrality", "pagerank",
]

LABEL_UNKNOWN = -1
LABEL_HUMAN   =  0
LABEL_SYBIL   =  1

HIDDEN_DIM    = 128
NUM_LAYERS    = 3
DROPOUT       = 0.4
LEARNING_RATE = 5e-4
WEIGHT_DECAY  = 1e-4
EPOCHS        = 300
PATIENCE      = 30          # early stopping patience


# ─────────────────────────────────────────────────────────────────────────────
#  Label generation — heuristic semi-supervised strategy
# ─────────────────────────────────────────────────────────────────────────────

LABELS_CSV_PATH = os.path.join(
    os.path.dirname(PROCESSED_DATA_PATH), "raw", "labels.csv"
)


def generate_labels(df: pd.DataFrame) -> np.ndarray:
    """
    Load ground-truth labels from labels.csv (written by the synthetic data
    generator) when available.  Falls back to topology-based heuristics when
    running on real Alchemy data that has no label file.
    """
    # ── Mode 1: Ground-truth labels from synthetic generator ─────────────────
    if os.path.exists(LABELS_CSV_PATH):
        print(f"[Labels] Loading ground-truth labels from {LABELS_CSV_PATH}")
        df_labels = pd.read_csv(LABELS_CSV_PATH)
        label_map = dict(zip(df_labels["address"], df_labels["is_sybil"]))

        labels = np.array([
            label_map.get(addr, LABEL_UNKNOWN) for addr in df["node_id"]
        ], dtype=np.int64)

        # Map: 1 → LABEL_SYBIL (1), 0 → LABEL_HUMAN (0), missing → UNKNOWN (-1)
        n_sybil   = int((labels == LABEL_SYBIL).sum())
        n_human   = int((labels == LABEL_HUMAN).sum())
        n_unknown = int((labels == LABEL_UNKNOWN).sum())
        print(f"[Labels] Ground-truth: Sybil={n_sybil:,}  Human={n_human:,}  "
              f"Unknown={n_unknown:,}  ({(n_sybil+n_human)/len(df)*100:.1f}% labeled)")
        return labels

    # ── Mode 2: Heuristic semi-supervised (real/unlabeled data) ──────────────
    print("[Labels] No labels.csv found — using topology heuristics (real data mode).")
    labels = np.full(len(df), LABEL_UNKNOWN, dtype=np.int64)

    sybil_mask = (
        ((df["out_degree"] >= 5) & (df["total_tx_count"] >= 10)) |
        ((df["reciprocity"] > 0.5) & (df["out_degree"] >= 3))
    ).values
    labels[sybil_mask] = LABEL_SYBIL

    human_mask = (
        (df["in_degree"]           >= 2) &
        (df["out_degree"]          >= 1) &
        (df["reciprocity"]         <  0.3) &
        (df["unique_interactions"] >= 3)
    ).values
    labels[human_mask & (labels == LABEL_UNKNOWN)] = LABEL_HUMAN

    n_sybil   = int((labels == LABEL_SYBIL).sum())
    n_human   = int((labels == LABEL_HUMAN).sum())
    n_unknown = int((labels == LABEL_UNKNOWN).sum())
    labeled_pct = (n_sybil + n_human) / len(df) * 100
    print(f"[Labels] Heuristic: Sybil={n_sybil:,}  Human={n_human:,}  "
          f"Unknown={n_unknown:,}  ({labeled_pct:.1f}% labeled)")

    if n_sybil == 0 or n_human == 0:
        print("[Labels] WARNING: one class empty — using out_degree percentile split.")
        p99_out = df["out_degree"].quantile(0.99)
        p50_out = df["out_degree"].quantile(0.50)
        labels = np.full(len(df), LABEL_UNKNOWN, dtype=np.int64)
        labels[df["out_degree"].values >= max(p99_out, 2)] = LABEL_SYBIL
        labels[df["out_degree"].values <= p50_out]         = LABEL_HUMAN
        n_sybil = int((labels == LABEL_SYBIL).sum())
        n_human = int((labels == LABEL_HUMAN).sum())
        print(f"[Labels] Fallback → Sybil={n_sybil:,}  Human={n_human:,}")

    return labels


# ─────────────────────────────────────────────────────────────────────────────
#  PyTorch Geometric Data object builder
# ─────────────────────────────────────────────────────────────────────────────

def build_pyg_data(
    df_features: pd.DataFrame,
    G,                           # networkx DiGraph
    labels: np.ndarray,
) -> Data:
    """
    Convert the NetworkX graph + feature DataFrame into a PyG Data object.
    Node ordering follows df_features index (same as G.nodes() after build).
    """
    # ── Map node addresses → integer indices ─────────────────────────────────
    node_list = list(df_features["node_id"])
    node_idx  = {addr: i for i, addr in enumerate(node_list)}

    # ── Feature matrix ───────────────────────────────────────────────────────
    X_raw = df_features[FEATURE_COLS].values.astype(np.float32)
    # RobustScaler handles the extreme outliers common in blockchain data
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X_raw).astype(np.float32)
    x = torch.tensor(X_scaled, dtype=torch.float)

    # ── Edge index ───────────────────────────────────────────────────────────
    edge_src, edge_dst = [], []
    for u, v in G.edges():
        if u in node_idx and v in node_idx:
            edge_src.append(node_idx[u])
            edge_dst.append(node_idx[v])
    edge_index = torch.tensor([edge_src, edge_dst], dtype=torch.long)

    # ── Labels ───────────────────────────────────────────────────────────────
    y = torch.tensor(labels, dtype=torch.long)

    # ── Train / val / test masks (only labeled nodes) ────────────────────────
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
    print(f"[PyG]  Nodes={data.num_nodes:,}  Edges={data.num_edges:,}  "
          f"Features={data.num_node_features}")
    print(f"[PyG]  Train={train_mask.sum():,}  "
          f"Val={val_mask.sum():,}  Test={test_mask.sum():,}")
    return data


# ─────────────────────────────────────────────────────────────────────────────
#  GraphSAGE Model
# ─────────────────────────────────────────────────────────────────────────────

class SybilSAGE(torch.nn.Module):
    """
    3-layer GraphSAGE network for binary Sybil / Human node classification.

    Layers:
      SAGEConv(in, hidden) → BN → ReLU → Dropout
      SAGEConv(hidden, hidden) → BN → ReLU → Dropout
      SAGEConv(hidden, 2)   → log-softmax output
    """

    def __init__(self, in_channels: int, hidden: int = HIDDEN_DIM, dropout: float = DROPOUT):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden, aggr="mean")
        self.bn1   = torch.nn.BatchNorm1d(hidden)
        self.conv2 = SAGEConv(hidden, hidden, aggr="mean")
        self.bn2   = torch.nn.BatchNorm1d(hidden)
        self.conv3 = SAGEConv(hidden, 2, aggr="mean")
        self.dropout = dropout

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = self.bn1(x)
        x = F.relu(x)
        x = F.dropout(x, p=self.dropout, training=self.training)

        x = self.conv2(x, edge_index)
        x = self.bn2(x)
        x = F.relu(x)
        x = F.dropout(x, p=self.dropout, training=self.training)

        x = self.conv3(x, edge_index)
        return F.log_softmax(x, dim=1)

    @torch.no_grad()
    def predict_proba(self, x, edge_index):
        """Return Sybil probability for every node."""
        self.eval()
        log_probs = self.forward(x, edge_index)
        return log_probs.exp()[:, LABEL_SYBIL].numpy()


# ─────────────────────────────────────────────────────────────────────────────
#  Training loop
# ─────────────────────────────────────────────────────────────────────────────

def train_epoch(model, data, optimizer):
    model.train()
    optimizer.zero_grad()
    out  = model(data.x, data.edge_index)
    loss = F.nll_loss(out[data.train_mask], data.y[data.train_mask])
    loss.backward()
    optimizer.step()
    return float(loss.detach())


@torch.no_grad()
def evaluate(model, data, mask):
    model.eval()
    out   = model(data.x, data.edge_index)
    loss  = float(F.nll_loss(out[mask], data.y[mask]))
    preds = out[mask].argmax(dim=1)
    acc   = float((preds == data.y[mask]).sum()) / int(mask.sum())
    return loss, acc


# ─────────────────────────────────────────────────────────────────────────────
#  Main training function
# ─────────────────────────────────────────────────────────────────────────────

def train_gnn(data: Data, epochs: int = EPOCHS, patience: int = PATIENCE):
    torch.manual_seed(42)
    device = torch.device("cpu")   # CPU-only (no GPU required)
    data   = data.to(device)

    model = SybilSAGE(in_channels=data.num_node_features).to(device)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    best_val_loss = float("inf")
    best_state    = None
    patience_ctr  = 0
    history       = []

    print(f"\n[Train] Starting {epochs}-epoch GraphSAGE training…")
    print(f"        Model params: {sum(p.numel() for p in model.parameters()):,}")

    for epoch in range(1, epochs + 1):
        train_loss              = train_epoch(model, data, optimizer)
        val_loss, val_acc       = evaluate(model, data, data.val_mask)
        scheduler.step()

        history.append({
            "epoch": epoch, "train_loss": train_loss,
            "val_loss": val_loss, "val_acc": val_acc,
        })

        # Early stopping
        if val_loss < best_val_loss - 1e-5:
            best_val_loss = val_loss
            best_state    = {k: v.clone() for k, v in model.state_dict().items()}
            patience_ctr  = 0
        else:
            patience_ctr += 1
            if patience_ctr >= patience:
                print(f"[Train] Early stop at epoch {epoch} (val_loss={val_loss:.4f})")
                break

        if epoch % 25 == 0 or epoch == 1:
            print(f"  Epoch {epoch:4d}  train_loss={train_loss:.4f}  "
                  f"val_loss={val_loss:.4f}  val_acc={val_acc:.3f}")

    # Restore best weights
    model.load_state_dict(best_state)
    return model, pd.DataFrame(history)


# ─────────────────────────────────────────────────────────────────────────────
#  Evaluation + scoring
# ─────────────────────────────────────────────────────────────────────────────

@torch.no_grad()
def evaluate_final(model, data):
    model.eval()
    out      = model(data.x, data.edge_index)
    preds    = out.argmax(dim=1).numpy()
    probas   = out.exp()[:, LABEL_SYBIL].numpy()
    y_true   = data.y.numpy()

    mask     = data.test_mask.numpy()
    y_true_t = y_true[mask]
    y_pred_t = preds[mask]
    y_prob_t = probas[mask]

    cm = confusion_matrix(y_true_t, y_pred_t, labels=[LABEL_HUMAN, LABEL_SYBIL])
    print(f"  Confusion matrix:\n    TN={cm[0,0]:,}  FP={cm[0,1]:,}\n"
          f"    FN={cm[1,0]:,}  TP={cm[1,1]:,}")

    classes_present = np.unique(y_true_t)
    target_names = ["Human", "Sybil"]
    labels_arg   = [LABEL_HUMAN, LABEL_SYBIL]
    # Only pass target_names for classes actually present to avoid sklearn crash
    present_names = [target_names[c] for c in classes_present]
    print(classification_report(
        y_true_t, y_pred_t,
        labels=labels_arg,
        target_names=target_names,
        digits=4,
        zero_division=0,
    ))
    try:
        auc = roc_auc_score(y_true_t, y_prob_t)
        print(f"  ROC-AUC : {auc:.4f}")
    except Exception as e:
        print(f"  ROC-AUC : n/a ({e})")


    return preds, probas


# ─────────────────────────────────────────────────────────────────────────────
#  Save outputs
# ─────────────────────────────────────────────────────────────────────────────

def save_outputs(model, df_features, preds, probas, history):
    model_path = os.path.join(PROCESSED_DATA_PATH, "sybil_sage.pt")
    torch.save(model.state_dict(), model_path)
    print(f"\n[Save] Model → {model_path}")

    history_path = os.path.join(PROCESSED_DATA_PATH, "training_history.csv")
    history.to_csv(history_path, index=False)
    print(f"[Save] Training history → {history_path}")

    df_scores = df_features[["node_id"]].copy()
    df_scores["predicted_label"] = preds
    df_scores["sybil_probability"] = np.round(probas, 6)
    df_scores["classification"] = df_scores["predicted_label"].map(
        {LABEL_HUMAN: "Human", LABEL_SYBIL: "Sybil"}
    )
    scores_path = os.path.join(PROCESSED_DATA_PATH, "node_scores.csv")
    df_scores.to_csv(scores_path, index=False)
    print(f"[Save] Node scores → {scores_path}")

    n_sybil = (df_scores["predicted_label"] == LABEL_SYBIL).sum()
    print(f"\n[Result] {n_sybil:,} wallets flagged as Sybil "
          f"({n_sybil/len(df_scores)*100:.1f}% of all nodes)")
    return df_scores


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_gnn_pipeline():
    print("=== Sybil-Net GNN Training Pipeline ===\n")

    # ── Load preprocessed data ───────────────────────────────────────────────
    features_path = os.path.join(PROCESSED_DATA_PATH, "features.csv")
    graph_path    = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")

    if not os.path.exists(features_path) or not os.path.exists(graph_path):
        print("[Error] features.csv or graph.pkl not found.")
        print("        Run the Week-1 pipeline first: python main.py")
        sys.exit(1)

    print("[Load] Reading features…")
    df_features = pd.read_csv(features_path)
    print(f"       {len(df_features):,} nodes, {len(FEATURE_COLS)} features each")

    print("[Load] Reading graph…")
    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    # ── Generate heuristic labels ────────────────────────────────────────────
    print("\n[Labels] Generating heuristic semi-supervised labels…")
    labels = generate_labels(df_features)

    # ── Build PyG Data object ────────────────────────────────────────────────
    print("\n[PyG] Building PyTorch Geometric data object…")
    data = build_pyg_data(df_features, G, labels)

    # ── Train ────────────────────────────────────────────────────────────────
    model, history = train_gnn(data)

    # ── Evaluate ─────────────────────────────────────────────────────────────
    preds, probas = evaluate_final(model, data)

    # ── Save ─────────────────────────────────────────────────────────────────
    df_scores = save_outputs(model, df_features, preds, probas, history)

    print("\n=== GNN Pipeline Complete ===")
    return model, df_scores


if __name__ == "__main__":
    run_gnn_pipeline()
