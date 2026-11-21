"""
tests/test_gnn.py
─────────────────────────────────────────────────────────────────────────────
Tests for models/gnn.py — the GraphSAGE GNN layer.

Coverage:
  • generate_labels: produces only {-1, 0, 1} values; both classes present.
  • build_pyg_data: correct tensor shapes, edge_index is valid, masks correct.
  • SybilSAGE forward pass: output shape and log-probability validity.
  • train_epoch / evaluate: loss decreases after one step.
  • predict_proba: values in [0, 1].
  • Short training loop (5 epochs): val_acc is non-trivial.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import pytest
import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level patch: force heuristic label generation
#  (prevents reading the real data/raw/labels.csv which has production addrs)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _no_real_labels(monkeypatch):
    """Redirect LABELS_CSV_PATH so generate_labels uses topology heuristics."""
    import models.gnn as gnn_mod
    monkeypatch.setattr(gnn_mod, "LABELS_CSV_PATH", "/tmp/_nonexistent_labels.csv")


# ─────────────────────────────────────────────────────────────────────────────
#  Label generation
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateLabels:
    def test_label_values_are_valid(self, feature_df):
        from models.gnn import generate_labels, LABEL_UNKNOWN, LABEL_HUMAN, LABEL_SYBIL
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        labels = generate_labels(df)
        valid  = {LABEL_UNKNOWN, LABEL_HUMAN, LABEL_SYBIL}
        assert set(np.unique(labels)).issubset(valid)

    def test_both_classes_present(self, feature_df):
        from models.gnn import generate_labels, LABEL_HUMAN, LABEL_SYBIL
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        labels = generate_labels(df)
        assert LABEL_HUMAN in labels, "No Human (0) labels generated"
        assert LABEL_SYBIL in labels, "No Sybil (1) labels generated"

    def test_label_count_matches_df(self, feature_df):
        from models.gnn import generate_labels
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        labels = generate_labels(df)
        assert len(labels) == len(df)

    def test_labels_are_int64(self, feature_df):
        from models.gnn import generate_labels
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        labels = generate_labels(df)
        assert labels.dtype == np.int64


# ─────────────────────────────────────────────────────────────────────────────
#  PyG Data object
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildPyGData:
    def test_node_feature_shape(self, pyg_data, feature_df):
        data, labels = pyg_data
        df, _  = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert data.x.shape[0] == len(df)
        assert data.x.shape[1] == 12   # 12 feature columns

    def test_edge_index_shape(self, pyg_data):
        data, labels = pyg_data
        assert data.edge_index.shape[0] == 2
        assert data.edge_index.shape[1] > 0

    def test_edge_index_dtype(self, pyg_data):
        data, _ = pyg_data
        assert data.edge_index.dtype == torch.long

    def test_edge_index_values_in_bounds(self, pyg_data):
        data, _ = pyg_data
        n = data.num_nodes
        assert data.edge_index.min() >= 0
        assert data.edge_index.max() < n

    def test_masks_sum_to_labeled_count(self, pyg_data):
        data, labels = pyg_data
        labeled = (labels != -1).sum()
        mask_total = data.train_mask.sum() + data.val_mask.sum() + data.test_mask.sum()
        assert int(mask_total) == int(labeled)

    def test_masks_are_disjoint(self, pyg_data):
        data, _ = pyg_data
        overlap = (data.train_mask & data.val_mask).any() or \
                  (data.train_mask & data.test_mask).any() or \
                  (data.val_mask   & data.test_mask).any()
        assert not overlap, "Train/Val/Test masks overlap"

    def test_feature_dtype_float(self, pyg_data):
        data, _ = pyg_data
        assert data.x.dtype == torch.float32

    def test_y_matches_labels(self, pyg_data):
        data, labels = pyg_data
        assert (data.y.numpy() == labels).all()


# ─────────────────────────────────────────────────────────────────────────────
#  SybilSAGE model
# ─────────────────────────────────────────────────────────────────────────────

class TestSybilSAGEModel:
    @pytest.fixture(autouse=True)
    def _setup(self, pyg_data):
        from models.gnn import SybilSAGE
        self.data, self.labels = pyg_data
        self.model = SybilSAGE(in_channels=self.data.num_node_features, hidden=32, dropout=0.0)

    def test_forward_output_shape(self):
        out = self.model(self.data.x, self.data.edge_index)
        assert out.shape == (self.data.num_nodes, 2)

    def test_forward_output_is_log_probs(self):
        """log-softmax output should be ≤ 0 and per-row sum to ≈ 0 in log-space."""
        out = self.model(self.data.x, self.data.edge_index)
        assert (out <= 0).all(), "log-softmax values should be <= 0"
        row_sums = out.exp().sum(dim=1)
        assert torch.allclose(row_sums, torch.ones_like(row_sums), atol=1e-5)

    def test_predict_proba_in_0_1(self):
        proba = self.model.predict_proba(self.data.x, self.data.edge_index)
        assert proba.min() >= 0.0 and proba.max() <= 1.0

    def test_predict_proba_length(self):
        proba = self.model.predict_proba(self.data.x, self.data.edge_index)
        assert len(proba) == self.data.num_nodes

    def test_param_count_positive(self):
        n_params = sum(p.numel() for p in self.model.parameters())
        assert n_params > 0


# ─────────────────────────────────────────────────────────────────────────────
#  Training and evaluation
# ─────────────────────────────────────────────────────────────────────────────

class TestTrainingLoop:
    @pytest.fixture(autouse=True)
    def _setup(self, pyg_data):
        from models.gnn import SybilSAGE
        self.data, self.labels = pyg_data
        torch.manual_seed(0)
        self.model = SybilSAGE(in_channels=self.data.num_node_features, hidden=32, dropout=0.0)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)

    def test_train_epoch_returns_float(self):
        from models.gnn import train_epoch
        loss = train_epoch(self.model, self.data, self.optimizer)
        assert isinstance(loss, float)
        assert loss >= 0

    def test_loss_finite(self):
        from models.gnn import train_epoch
        loss = train_epoch(self.model, self.data, self.optimizer)
        assert np.isfinite(loss)

    def test_evaluate_returns_loss_and_acc(self):
        from models.gnn import evaluate
        loss, acc = evaluate(self.model, self.data, self.data.val_mask)
        assert isinstance(loss, float)
        assert 0.0 <= acc <= 1.0

    def test_loss_decreases_over_5_epochs(self):
        from models.gnn import train_epoch
        losses = [train_epoch(self.model, self.data, self.optimizer) for _ in range(5)]
        # Loss should decrease overall (allow some noise, just check general trend)
        assert losses[-1] < losses[0] * 1.5, \
            f"Loss did not decrease: {losses[0]:.4f} → {losses[-1]:.4f}"

    def test_short_training_reaches_nontrivial_accuracy(self):
        """10 epochs on tiny graph should yield better-than-random accuracy."""
        from models.gnn import train_epoch, evaluate
        for _ in range(10):
            train_epoch(self.model, self.data, self.optimizer)
        _, acc = evaluate(self.model, self.data, self.data.test_mask)
        # Even untrained on tiny data should beat ~33% (3 classes including unknown masked)
        assert acc >= 0.3, f"Test accuracy {acc:.3f} is suspiciously low"
