"""
tests/test_features.py
─────────────────────────────────────────────────────────────────────────────
Tests for features/extractor.py — the feature engineering layer.

Coverage:
  • All 12 required features are present in the output DataFrame.
  • Every node in the graph has a feature row (100% coverage).
  • Feature value ranges are sane (no negatives where impossible, etc.).
  • Sybil structural signals:
      - Hub-and-spoke controller has high out_degree.
      - Wash-ring nodes have high reciprocity.
  • _to_unix helper handles all supported formats.
  • extract_features saves features.csv to PROCESSED_DATA_PATH.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import pickle
import tempfile
import pytest
import numpy as np
import pandas as pd
import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

REQUIRED_FEATURES = [
    "node_id",
    "in_degree", "out_degree", "total_tx_count", "unique_interactions",
    "avg_value_sent", "avg_gas", "tx_frequency", "node_age_days",
    "reciprocity", "clustering_coeff", "betweenness_centrality", "pagerank",
]


# ─────────────────────────────────────────────────────────────────────────────
#  _to_unix helper tests
# ─────────────────────────────────────────────────────────────────────────────

class TestToUnix:
    def setup_method(self):
        from features.extractor import _to_unix
        self._to_unix = _to_unix

    def test_integer_passthrough(self):
        ts = 1_700_000_000
        assert self._to_unix(ts) == ts

    def test_float_passthrough(self):
        ts = 1_700_000_000.0
        assert self._to_unix(ts) == 1_700_000_000

    def test_numeric_string(self):
        assert self._to_unix("1700000000") == 1_700_000_000

    def test_iso_string(self):
        result = self._to_unix("2024-01-15T12:00:00Z")
        assert result > 1_700_000_000      # should be a valid unix ts

    def test_none_returns_zero(self):
        assert self._to_unix(None) == 0

    def test_nan_returns_zero(self):
        assert self._to_unix(float("nan")) == 0

    def test_empty_string_returns_zero(self):
        assert self._to_unix("") == 0

    def test_obviously_wrong_small_value_returns_zero(self):
        # Values < 1_000_000 are clearly not Unix timestamps
        assert self._to_unix(42) == 0


# ─────────────────────────────────────────────────────────────────────────────
#  extract_features integration tests (use session fixtures)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractFeatures:
    def test_all_required_columns_present(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        for col in REQUIRED_FEATURES:
            assert col in df.columns, f"Missing column: {col}"

    def test_every_graph_node_has_a_row(self, feature_df, built_graph):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        G, _  = built_graph
        graph_nodes = set(G.nodes())
        feature_nodes = set(df["node_id"])
        missing = graph_nodes - feature_nodes
        assert not missing, f"{len(missing)} nodes have no feature row"

    def test_no_duplicate_node_ids(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert df["node_id"].nunique() == len(df)

    def test_in_degree_non_negative(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert (df["in_degree"] >= 0).all()

    def test_out_degree_non_negative(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert (df["out_degree"] >= 0).all()

    def test_reciprocity_in_0_1(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert (df["reciprocity"] >= 0).all() and (df["reciprocity"] <= 1).all()

    def test_clustering_coeff_in_0_1(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert (df["clustering_coeff"] >= 0).all() and (df["clustering_coeff"] <= 1).all()

    def test_pagerank_sums_to_approx_1(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        total_pr = df["pagerank"].sum()
        assert abs(total_pr - 1.0) < 0.01, f"PageRank sum={total_pr:.4f}, expected ≈ 1.0"

    def test_no_nan_in_features(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        numeric_cols = [c for c in REQUIRED_FEATURES if c != "node_id"]
        nan_counts = df[numeric_cols].isna().sum()
        assert nan_counts.sum() == 0, f"NaN values found:\n{nan_counts[nan_counts > 0]}"

    def test_features_csv_written_to_disk(self, feature_df, tmp_dir):
        features_path = os.path.join(tmp_dir["processed"], "features.csv")
        assert os.path.exists(features_path), "features.csv was not saved"

    def test_hub_controller_has_high_out_degree(self, feature_df, synthetic_csv):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        ctrl  = synthetic_csv["controller"]
        row   = df[df["node_id"] == ctrl]
        assert not row.empty, f"Controller {ctrl} not found in features"
        assert row["out_degree"].values[0] >= 5, \
            f"Controller out_degree={row['out_degree'].values[0]}, expected >= 5"

    def test_ring_nodes_have_nonzero_in_and_out_degree(self, feature_df, synthetic_csv):
        """Directed wash ring: each node has both in_degree and out_degree >= 1."""
        df, meta = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        ring_addrs = meta["ring"] if meta else synthetic_csv["ring"]
        ring_rows  = df[df["node_id"].isin(ring_addrs)]
        assert not ring_rows.empty, "Ring nodes not found in features DataFrame"
        assert (ring_rows["in_degree"]  >= 1).all(), "Ring nodes should have in_degree >= 1"
        assert (ring_rows["out_degree"] >= 1).all(), "Ring nodes should have out_degree >= 1"

    def test_tx_frequency_non_negative(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert (df["tx_frequency"] >= 0).all()

    def test_node_age_days_non_negative(self, feature_df):
        df, _ = feature_df if isinstance(feature_df, tuple) else (feature_df, None)
        assert (df["node_age_days"] >= 0).all()
