"""
tests/test_graph.py
─────────────────────────────────────────────────────────────────────────────
Tests for graph/builder.py — the graph construction layer.

Coverage:
  • Output is a NetworkX DiGraph.
  • All wallets in CSV appear as nodes.
  • Every unique (from, to) pair becomes a directed edge.
  • Edge attributes: weight (tx_count), total_value, avg_value, avg_gas,
    first_tx, last_tx are present and correctly typed.
  • Duplicate transactions are aggregated (not duplicated as edges).
  • graph.pkl round-trips without data loss.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import csv
import time
import uuid
import pickle
import tempfile
import pytest
import pandas as pd
import networkx as nx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_csv(tmp_path, rows):
    """Write rows to a CSV and return the path."""
    csv_path = tmp_path / "transactions.csv"
    fieldnames = ["hash", "blockNumber", "timeStamp", "from", "to", "value", "gas", "gasPrice"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return str(csv_path)


def _row(frm, to, value="1000000000000000", gas="21000"):
    return {
        "hash":        f"0x{uuid.uuid4().hex}",
        "blockNumber": "19000000",
        "timeStamp":   str(int(time.time())),
        "from":        frm,
        "to":          to,
        "value":       value,
        "gas":         gas,
        "gasPrice":    "1000000000",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildGraph:
    def test_returns_digraph(self, tmp_path):
        from graph.builder import build_graph
        csv_path = _build_csv(tmp_path, [_row("0xA", "0xB"), _row("0xB", "0xC")])
        G = build_graph(data_path=csv_path)
        assert isinstance(G, nx.DiGraph)

    def test_nodes_include_all_wallets(self, tmp_path):
        from graph.builder import build_graph
        csv_path = _build_csv(tmp_path, [_row("0xA", "0xB"), _row("0xC", "0xD")])
        G = build_graph(data_path=csv_path)
        assert {"0xA", "0xB", "0xC", "0xD"}.issubset(set(G.nodes()))

    def test_directed_edges_present(self, tmp_path):
        from graph.builder import build_graph
        csv_path = _build_csv(tmp_path, [_row("0xA", "0xB")])
        G = build_graph(data_path=csv_path)
        assert G.has_edge("0xA", "0xB")
        assert not G.has_edge("0xB", "0xA")

    def test_edge_weight_is_tx_count(self, tmp_path):
        """Two transactions from A→B must produce weight=2."""
        from graph.builder import build_graph
        csv_path = _build_csv(tmp_path, [_row("0xA", "0xB"), _row("0xA", "0xB")])
        G = build_graph(data_path=csv_path)
        assert G["0xA"]["0xB"]["weight"] == 2

    def test_edge_has_required_attributes(self, tmp_path):
        from graph.builder import build_graph
        csv_path = _build_csv(tmp_path, [_row("0xA", "0xB")])
        G = build_graph(data_path=csv_path)
        edge = G["0xA"]["0xB"]
        for attr in ("weight", "total_value", "avg_value", "avg_gas", "first_tx", "last_tx"):
            assert attr in edge, f"Edge missing attribute: {attr}"

    def test_total_value_sums_correctly(self, tmp_path):
        from graph.builder import build_graph
        rows = [
            _row("0xA", "0xB", value="1000"),
            _row("0xA", "0xB", value="2000"),
        ]
        csv_path = _build_csv(tmp_path, rows)
        G = build_graph(data_path=csv_path)
        assert G["0xA"]["0xB"]["total_value"] == pytest.approx(3000.0)

    def test_avg_value_is_mean(self, tmp_path):
        from graph.builder import build_graph
        rows = [
            _row("0xA", "0xB", value="1000"),
            _row("0xA", "0xB", value="3000"),
        ]
        csv_path = _build_csv(tmp_path, rows)
        G = build_graph(data_path=csv_path)
        assert G["0xA"]["0xB"]["avg_value"] == pytest.approx(2000.0)

    def test_no_duplicate_edges(self, tmp_path):
        """Multiple raw txns between same pair → single edge in graph."""
        from graph.builder import build_graph
        rows = [_row("0xA", "0xB") for _ in range(5)]
        csv_path = _build_csv(tmp_path, rows)
        G = build_graph(data_path=csv_path)
        # DiGraph allows only one edge per (u, v)
        assert G.number_of_edges() == 1

    def test_bidirectional_creates_two_edges(self, tmp_path):
        from graph.builder import build_graph
        csv_path = _build_csv(tmp_path, [_row("0xA", "0xB"), _row("0xB", "0xA")])
        G = build_graph(data_path=csv_path)
        assert G.has_edge("0xA", "0xB")
        assert G.has_edge("0xB", "0xA")

    def test_graph_pkl_round_trips(self, tmp_path):
        from graph.builder import build_graph
        csv_path = _build_csv(tmp_path, [_row("0xA", "0xB"), _row("0xB", "0xC")])
        G = build_graph(data_path=csv_path)

        pkl_path = str(tmp_path / "graph.pkl")
        with open(pkl_path, "wb") as f:
            pickle.dump(G, f)
        with open(pkl_path, "rb") as f:
            G2 = pickle.load(f)

        assert set(G.nodes()) == set(G2.nodes())
        assert set(G.edges()) == set(G2.edges())

    def test_synthetic_hub_has_high_out_degree(self, tmp_path):
        """Build a hub-and-spoke graph inline; controller must have out_degree >= workers."""
        import csv as _csv
        import time as _time
        import uuid as _uuid

        controller = "0xCONTROLLER"
        workers    = [f"0xWORKER{i:02d}" for i in range(10)]
        now        = int(_time.time())

        rows = []
        for w in workers:
            rows.append({
                "hash": f"0x{_uuid.uuid4().hex}", "blockNumber": "19000000",
                "timeStamp": str(now), "from": controller, "to": w,
                "value": "1000000000000000", "gas": "21000", "gasPrice": "1000000000",
            })

        csv_path = _build_csv(tmp_path, rows)
        from graph.builder import build_graph
        G = build_graph(data_path=csv_path)
        assert G.out_degree(controller) == 10

    def test_synthetic_ring_has_reciprocal_edges(self, tmp_path):
        """Wash ring A→B→C→D→E→A should produce circular directed edges."""
        import csv as _csv
        import time as _time
        import uuid as _uuid

        ring = [f"0xRING{i:02d}" for i in range(5)]
        now  = int(_time.time())

        rows = []
        for i in range(len(ring)):
            rows.append({
                "hash": f"0x{_uuid.uuid4().hex}", "blockNumber": "19000000",
                "timeStamp": str(now),
                "from": ring[i], "to": ring[(i + 1) % len(ring)],
                "value": "1000000000000000", "gas": "21000", "gasPrice": "1000000000",
            })

        csv_path = _build_csv(tmp_path, rows)
        from graph.builder import build_graph
        G = build_graph(data_path=csv_path)

        # Every consecutive pair in the ring should have a directed edge
        for i in range(len(ring)):
            assert G.has_edge(ring[i], ring[(i + 1) % len(ring)]), \
                f"Missing edge: {ring[i]} → {ring[(i+1) % len(ring)]}"
