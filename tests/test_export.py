"""
tests/test_export.py
─────────────────────────────────────────────────────────────────────────────
Tests for utils/export.py — dataset export layer.

Coverage:
  • nodes.csv is written and contains all graph nodes.
  • edges.csv is written and contains all graph edges.
  • Edge attributes (weight, total_value, etc.) are present in edges.csv.
  • No duplicate rows in either CSV.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import pickle
import pytest
import pandas as pd
import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────────────────────────
#  Module-scoped fixture: build graph, export, share across all tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    """
    Build a simple graph, export it once, and share the results across all
    tests in this module.  Uses module scope so exports happen once.
    """
    base = tmp_path_factory.mktemp("export")

    G = nx.DiGraph()
    G.add_edge("0xA", "0xB", weight=3, total_value=1000.0, avg_value=333.3,
               avg_gas=21000, first_tx=1700000000, last_tx=1700086400)
    G.add_edge("0xB", "0xC", weight=1, total_value=500.0, avg_value=500.0,
               avg_gas=21000, first_tx=1700000000, last_tx=1700000000)
    G.add_edge("0xA", "0xC", weight=2, total_value=800.0, avg_value=400.0,
               avg_gas=21000, first_tx=1700000000, last_tx=1700000001)

    pkl_path = str(base / "graph.pkl")
    with open(pkl_path, "wb") as f:
        pickle.dump(G, f)

    # Patch PROCESSED_DATA_PATH before calling export
    mp = pytest.MonkeyPatch()
    import config.settings as settings
    import utils.export as export_mod
    mp.setattr(settings,   "PROCESSED_DATA_PATH", str(base))
    mp.setattr(export_mod, "PROCESSED_DATA_PATH", str(base), raising=False)

    from utils.export import export_datasets
    export_datasets(graph_path=pkl_path)
    mp.undo()

    nodes_csv = str(base / "nodes.csv")
    edges_csv = str(base / "edges.csv")

    return {
        "graph":     G,
        "base":      str(base),
        "nodes_csv": nodes_csv,
        "edges_csv": edges_csv,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExportDatasets:
    def test_nodes_csv_created(self, exported):
        assert os.path.exists(exported["nodes_csv"]), "nodes.csv was not created"

    def test_edges_csv_created(self, exported):
        assert os.path.exists(exported["edges_csv"]), "edges.csv was not created"

    def test_nodes_csv_contains_all_nodes(self, exported):
        df = pd.read_csv(exported["nodes_csv"])
        assert set(df["node_id"]) == set(exported["graph"].nodes())

    def test_edges_csv_row_count(self, exported):
        df = pd.read_csv(exported["edges_csv"])
        assert len(df) == exported["graph"].number_of_edges()

    def test_edges_csv_has_source_target(self, exported):
        df = pd.read_csv(exported["edges_csv"])
        assert "source" in df.columns and "target" in df.columns

    def test_edges_csv_weight_preserved(self, exported):
        df = pd.read_csv(exported["edges_csv"])
        assert "weight" in df.columns
        ab_row = df[(df["source"] == "0xA") & (df["target"] == "0xB")]
        assert not ab_row.empty
        assert ab_row["weight"].values[0] == 3

    def test_no_duplicate_edges(self, exported):
        df = pd.read_csv(exported["edges_csv"])
        dups = df.duplicated(subset=["source", "target"])
        assert not dups.any(), f"{dups.sum()} duplicate edges found"

    def test_no_duplicate_nodes(self, exported):
        df = pd.read_csv(exported["nodes_csv"])
        assert df["node_id"].nunique() == len(df)

    def test_all_edges_in_csv(self, exported):
        df = pd.read_csv(exported["edges_csv"])
        G  = exported["graph"]
        for u, v in G.edges():
            row = df[(df["source"] == u) & (df["target"] == v)]
            assert not row.empty, f"Edge {u}→{v} missing from edges.csv"

    def test_total_value_preserved(self, exported):
        df = pd.read_csv(exported["edges_csv"])
        ab = df[(df["source"] == "0xA") & (df["target"] == "0xB")]
        assert ab["total_value"].values[0] == pytest.approx(1000.0)
