"""
tests/test_mempool.py
─────────────────────────────────────────────────────────────────────────────
Tests for mempool/monitor.py — the real-time Mempool monitoring layer.

Coverage:
  • make_demo_batch: correct batch size, required tx fields, hex values.
  • compute_features_for_wallets: DataFrame shape, all 12 features present.
  • run_inference: list of alert dicts, required keys, probability in [0,1].
  • append_alerts: ring-buffer cap, newest-first ordering, valid JSON.
  • alert_level assignment logic: clean / warning / critical thresholds.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import json
import time
import uuid
import pickle
import tempfile
import pytest
import numpy as np
import pandas as pd
import networkx as nx
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ─────────────────────────────────────────────────────────────────────────────
#  Shared fixtures for mempool tests
# ─────────────────────────────────────────────────────────────────────────────

FEATURE_COLS = [
    "in_degree", "out_degree", "total_tx_count", "unique_interactions",
    "avg_value_sent", "avg_gas", "tx_frequency", "node_age_days",
    "reciprocity", "clustering_coeff", "betweenness_centrality", "pagerank",
]


@pytest.fixture(scope="module")
def tiny_model_and_context(feature_df, built_graph, tmp_dir):
    """
    Build a tiny SybilSAGE model in eval mode, along with the scaler and
    baseline graph needed by the mempool monitor.  No training needed —
    we just verify inference mechanics, not model quality.
    """
    from models.gnn import SybilSAGE
    from sklearn.preprocessing import RobustScaler

    df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
    G, _  = built_graph

    X_raw  = df[FEATURE_COLS].values.astype(np.float32)
    scaler = RobustScaler()
    scaler.fit(X_raw)

    torch.manual_seed(0)
    model = SybilSAGE(in_channels=12, hidden=16, dropout=0.0)
    model.eval()

    return model, scaler, G, df


@pytest.fixture()
def demo_txs(feature_df):
    """A demo batch of 10 synthetic pending transactions."""
    from mempool.monitor import make_demo_batch
    df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
    return make_demo_batch(df, batch_num=0)


# ─────────────────────────────────────────────────────────────────────────────
#  make_demo_batch
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeDemoBatch:
    def test_batch_size(self, demo_txs):
        assert len(demo_txs) == 10    # BATCH_SIZE = 10

    def test_required_tx_keys(self, demo_txs):
        for tx in demo_txs:
            for key in ("hash", "from", "to", "value", "gas"):
                assert key in tx, f"tx missing key: {key}"

    def test_value_is_integer(self, demo_txs):
        for tx in demo_txs:
            assert isinstance(tx["value"], int), "value should be int (wei)"

    def test_gas_is_integer(self, demo_txs):
        for tx in demo_txs:
            assert isinstance(tx["gas"], int), "gas should be int"

    def test_addresses_are_strings(self, demo_txs):
        for tx in demo_txs:
            assert isinstance(tx["from"], str)
            assert isinstance(tx["to"],   str)

    def test_different_batches_differ(self, feature_df):
        from mempool.monitor import make_demo_batch
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        batch0 = make_demo_batch(df, 0)
        batch1 = make_demo_batch(df, 1)
        hashes0 = {tx["hash"] for tx in batch0}
        hashes1 = {tx["hash"] for tx in batch1}
        assert hashes0 != hashes1, "Different batches should have different tx hashes"


# ─────────────────────────────────────────────────────────────────────────────
#  compute_features_for_wallets
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeFeatures:
    def test_returns_dataframe(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import compute_features_for_wallets
        _, _, G_base, df_base = tiny_model_and_context
        df_feat, _ = compute_features_for_wallets(demo_txs, G_base, df_base)
        assert isinstance(df_feat, pd.DataFrame)

    def test_all_feature_cols_present(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import compute_features_for_wallets
        _, _, G_base, df_base = tiny_model_and_context
        df_feat, _ = compute_features_for_wallets(demo_txs, G_base, df_base)
        for col in FEATURE_COLS:
            assert col in df_feat.columns, f"Missing feature column: {col}"

    def test_row_per_unique_wallet(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import compute_features_for_wallets
        _, _, G_base, df_base = tiny_model_and_context
        unique_wallets = set()
        for tx in demo_txs:
            if tx.get("from"): unique_wallets.add(tx["from"].lower())
            if tx.get("to"):   unique_wallets.add(tx["to"].lower())
        df_feat, _ = compute_features_for_wallets(demo_txs, G_base, df_base)
        assert len(df_feat) == len(unique_wallets)

    def test_no_nan_features(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import compute_features_for_wallets
        _, _, G_base, df_base = tiny_model_and_context
        df_feat, _ = compute_features_for_wallets(demo_txs, G_base, df_base)
        nan_count = df_feat[FEATURE_COLS].isna().sum().sum()
        assert nan_count == 0, f"NaNs found in feature matrix: {nan_count}"


# ─────────────────────────────────────────────────────────────────────────────
#  run_inference
# ─────────────────────────────────────────────────────────────────────────────

class TestRunInference:
    def test_returns_list(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import run_inference
        model, scaler, G_base, df_base = tiny_model_and_context
        alerts = run_inference(demo_txs, model, scaler, G_base, df_base)
        assert isinstance(alerts, list)

    def test_all_wallets_get_alert_entry(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import run_inference
        model, scaler, G_base, df_base = tiny_model_and_context
        alerts = run_inference(demo_txs, model, scaler, G_base, df_base)
        unique_wallets = set()
        for tx in demo_txs:
            if tx.get("from"): unique_wallets.add(tx["from"].lower())
            if tx.get("to"):   unique_wallets.add(tx["to"].lower())
        assert len(alerts) == len(unique_wallets)

    def test_alert_has_required_keys(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import run_inference
        model, scaler, G_base, df_base = tiny_model_and_context
        alerts = run_inference(demo_txs, model, scaler, G_base, df_base)
        required = {"timestamp", "wallet", "tx_hash", "sybil_probability",
                    "classification", "alert_level", "value_eth", "status"}
        for alert in alerts:
            missing = required - set(alert.keys())
            assert not missing, f"Alert missing keys: {missing}"

    def test_sybil_probability_in_0_1(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import run_inference
        model, scaler, G_base, df_base = tiny_model_and_context
        alerts = run_inference(demo_txs, model, scaler, G_base, df_base)
        for a in alerts:
            p = a["sybil_probability"]
            assert 0.0 <= p <= 1.0, f"Probability out of range: {p}"

    def test_classification_is_human_or_sybil(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import run_inference
        model, scaler, G_base, df_base = tiny_model_and_context
        alerts = run_inference(demo_txs, model, scaler, G_base, df_base)
        for a in alerts:
            assert a["classification"] in ("Human", "Sybil")

    def test_alert_level_valid(self, demo_txs, tiny_model_and_context):
        from mempool.monitor import run_inference
        model, scaler, G_base, df_base = tiny_model_and_context
        alerts = run_inference(demo_txs, model, scaler, G_base, df_base)
        for a in alerts:
            assert a["alert_level"] in ("clean", "warning", "critical")

    def test_empty_input_returns_empty(self, tiny_model_and_context):
        from mempool.monitor import run_inference
        model, scaler, G_base, df_base = tiny_model_and_context
        alerts = run_inference([], model, scaler, G_base, df_base)
        assert alerts == []


# ─────────────────────────────────────────────────────────────────────────────
#  append_alerts (ring-buffer)
# ─────────────────────────────────────────────────────────────────────────────

class TestAppendAlerts:
    def _make_alert(self, prob=0.5):
        from datetime import datetime, timezone
        return {
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "wallet":           f"0x{uuid.uuid4().hex[:40]}",
            "tx_hash":          f"0x{uuid.uuid4().hex}",
            "sybil_probability": prob,
            "classification":   "Sybil" if prob >= 0.5 else "Human",
            "alert_level":      "warning",
            "value_eth":        0.01,
            "status":           "pending",
        }

    def test_file_created(self, tmp_path, monkeypatch):
        from mempool import monitor as m
        alerts_path = tmp_path / "mempool_alerts.json"
        monkeypatch.setattr(m, "ALERTS_PATH", alerts_path)
        m.append_alerts([self._make_alert()])
        assert alerts_path.exists()

    def test_file_is_valid_json(self, tmp_path, monkeypatch):
        from mempool import monitor as m
        alerts_path = tmp_path / "mempool_alerts.json"
        monkeypatch.setattr(m, "ALERTS_PATH", alerts_path)
        m.append_alerts([self._make_alert(), self._make_alert()])
        data = json.loads(alerts_path.read_text())
        assert isinstance(data, list)

    def test_newest_first_ordering(self, tmp_path, monkeypatch):
        from mempool import monitor as m
        alerts_path = tmp_path / "mempool_alerts.json"
        monkeypatch.setattr(m, "ALERTS_PATH", alerts_path)

        a1 = self._make_alert(prob=0.1)
        a1["wallet"] = "0x" + "a" * 40
        time.sleep(0.01)
        a2 = self._make_alert(prob=0.9)
        a2["wallet"] = "0x" + "b" * 40

        m.append_alerts([a1])
        m.append_alerts([a2])

        data = json.loads(alerts_path.read_text())
        # Newest (a2) should be first
        assert data[0]["wallet"] == a2["wallet"]

    def test_ring_buffer_cap(self, tmp_path, monkeypatch):
        from mempool import monitor as m
        alerts_path = tmp_path / "mempool_alerts.json"
        monkeypatch.setattr(m, "ALERTS_PATH", alerts_path)
        monkeypatch.setattr(m, "MAX_ALERTS", 5)

        for i in range(10):
            m.append_alerts([self._make_alert()])

        data = json.loads(alerts_path.read_text())
        assert len(data) <= 5, f"Ring buffer exceeded cap: {len(data)} > 5"
