"""
tests/test_crosschain.py
─────────────────────────────────────────────────────────────────────────────
Week 7 — Cross-Chain Pipeline Test Suite

Tests cover:
  • Multi-chain synthetic data generation
  • Multi-chain graph construction
  • 17-feature cross-chain extraction
  • Cross-chain GNN PyG data building
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import csv
import time
import pickle
import random
import pytest
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.conftest import make_addr, make_tx


# ─────────────────────────────────────────────────────────────────────────────
#  Fixtures — session-scoped multi-chain test data
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mc_tmp_dir(tmp_path_factory):
    """Create temp directories for multichain test data."""
    base = tmp_path_factory.mktemp("sybilnet_mc")
    raw_dir       = base / "raw"
    processed_dir = base / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()
    return {
        "root":      str(base),
        "raw":       str(raw_dir),
        "processed": str(processed_dir),
    }


@pytest.fixture(scope="session")
def mc_synthetic_csv(mc_tmp_dir):
    """Generate a small multi-chain synthetic CSV with known patterns."""
    random.seed(42)
    now = int(time.time())

    # Define wallets
    controller = make_addr("b0")
    eth_workers = [make_addr("b1") for _ in range(5)]
    poly_workers = [make_addr("b2") for _ in range(5)]
    bridge_addr = make_addr("bb")
    ring = [make_addr("cc") for _ in range(4)]
    honest = [make_addr("aa") for _ in range(30)]

    txs = []

    def _mc_tx(frm, to, chain_id, is_bridge=False, value=None):
        return {
            "hash": f"0x{random.getrandbits(256):064x}",
            "blockNumber": str(random.randint(18_000_000, 22_000_000)),
            "timeStamp": str(now - random.randint(0, 86_400 * 30)),
            "from": frm,
            "to": to,
            "value": str(value or random.randint(10**15, 5 * 10**18)),
            "gas": str(random.randint(21_000, 100_000)),
            "gasPrice": str(random.randint(10**9, 5 * 10**10)),
            "chain_id": str(chain_id),
            "is_bridge_tx": str(is_bridge),
        }

    # Bot farm on Ethereum (chain_id=1)
    for _ in range(100):
        w = random.choice(eth_workers)
        txs.append(_mc_tx(controller, w, 1))
        txs.append(_mc_tx(w, controller, 1))

    # Bot farm bridged to Polygon (chain_id=137)
    for _ in range(50):
        w_eth = random.choice(eth_workers)
        w_poly = random.choice(poly_workers)
        txs.append(_mc_tx(w_eth, bridge_addr, 1, is_bridge=True))
        txs.append(_mc_tx(bridge_addr, w_poly, 137, is_bridge=True))
        txs.append(_mc_tx(w_poly, controller, 137))

    # Wash ring across chains
    for _ in range(30):
        for i in range(len(ring)):
            chain_id = 1 if i % 2 == 0 else 137
            is_bridge = (i % 2 == 1)  # bridge on alternating hops
            txs.append(_mc_tx(ring[i], ring[(i + 1) % len(ring)], chain_id, is_bridge))

    # Honest users
    for _ in range(200):
        frm = random.choice(honest)
        to = random.choice(honest)
        while to == frm:
            to = random.choice(honest)
        chain_id = random.choice([1, 137, 42161])
        txs.append(_mc_tx(frm, to, chain_id))

    random.shuffle(txs)

    csv_path = os.path.join(mc_tmp_dir["raw"], "transactions_multichain.csv")
    fieldnames = [
        "hash", "blockNumber", "timeStamp", "from", "to",
        "value", "gas", "gasPrice", "chain_id", "is_bridge_tx",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(txs)

    # Write labels
    all_sybil = (
        {controller} | set(eth_workers) | set(poly_workers) |
        {bridge_addr} | set(ring)
    )
    all_addrs = set()
    for tx in txs:
        all_addrs.add(tx["from"])
        all_addrs.add(tx["to"])

    labels_path = os.path.join(mc_tmp_dir["raw"], "labels_multichain.csv")
    with open(labels_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["address", "is_sybil"])
        writer.writeheader()
        for addr in all_addrs:
            writer.writerow({"address": addr, "is_sybil": 1 if addr in all_sybil else 0})

    return {
        "csv_path":     csv_path,
        "labels_path":  labels_path,
        "controller":   controller,
        "eth_workers":  eth_workers,
        "poly_workers": poly_workers,
        "bridge_addr":  bridge_addr,
        "ring":         ring,
        "honest":       honest,
        "all_sybil":    all_sybil,
        "n_txs":        len(txs),
    }


@pytest.fixture(scope="session")
def mc_graph(mc_synthetic_csv, mc_tmp_dir):
    """Build multichain graph from test data."""
    mp = pytest.MonkeyPatch()
    import config.settings as settings
    mp.setattr(settings, "PROCESSED_DATA_PATH", mc_tmp_dir["processed"])
    mp.setattr(settings, "BRIDGE_ADDRESSES", {mc_synthetic_csv["bridge_addr"]})

    import graph.crosschain_builder as builder_mod
    mp.setattr(builder_mod, "PROCESSED_DATA_PATH", mc_tmp_dir["processed"])
    mp.setattr(builder_mod, "BRIDGE_ADDRESSES", {mc_synthetic_csv["bridge_addr"]})

    from graph.crosschain_builder import build_multichain_graph
    G = build_multichain_graph(data_path=mc_synthetic_csv["csv_path"])

    graph_pkl = os.path.join(mc_tmp_dir["processed"], "graph_multichain.pkl")
    if not os.path.exists(graph_pkl):
        with open(graph_pkl, "wb") as f:
            pickle.dump(G, f)

    mp.undo()
    return G, graph_pkl


@pytest.fixture(scope="session")
def mc_features(mc_graph, mc_synthetic_csv, mc_tmp_dir):
    """Extract 17-feature vectors from multichain graph."""
    mp = pytest.MonkeyPatch()
    import config.settings as settings
    mp.setattr(settings, "PROCESSED_DATA_PATH", mc_tmp_dir["processed"])
    mp.setattr(settings, "BRIDGE_ADDRESSES", {mc_synthetic_csv["bridge_addr"]})

    import features.crosschain_extractor as ext_mod
    mp.setattr(ext_mod, "PROCESSED_DATA_PATH", mc_tmp_dir["processed"])
    mp.setattr(ext_mod, "BRIDGE_ADDRESSES", {mc_synthetic_csv["bridge_addr"]})

    G, graph_pkl = mc_graph
    from features.crosschain_extractor import extract_multichain_features
    df = extract_multichain_features(
        graph_path=graph_pkl,
        raw_data_path=mc_synthetic_csv["csv_path"],
    )
    mp.undo()
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST: Multi-Chain Synthetic Data
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultichainSyntheticData:
    def test_csv_exists(self, mc_synthetic_csv):
        assert os.path.exists(mc_synthetic_csv["csv_path"])

    def test_has_chain_id_column(self, mc_synthetic_csv):
        df = pd.read_csv(mc_synthetic_csv["csv_path"])
        assert "chain_id" in df.columns

    def test_has_bridge_tx_column(self, mc_synthetic_csv):
        df = pd.read_csv(mc_synthetic_csv["csv_path"])
        assert "is_bridge_tx" in df.columns

    def test_multiple_chains_present(self, mc_synthetic_csv):
        df = pd.read_csv(mc_synthetic_csv["csv_path"])
        chain_ids = df["chain_id"].unique()
        assert len(chain_ids) >= 2, f"Expected multiple chains, got {chain_ids}"

    def test_bridge_transactions_exist(self, mc_synthetic_csv):
        df = pd.read_csv(mc_synthetic_csv["csv_path"])
        bridge_txs = df[df["is_bridge_tx"].astype(str).str.lower().isin(["true", "1"])]
        assert len(bridge_txs) > 0, "Expected bridge transactions"

    def test_labels_file_exists(self, mc_synthetic_csv):
        assert os.path.exists(mc_synthetic_csv["labels_path"])

    def test_labels_have_sybil_entries(self, mc_synthetic_csv):
        df_labels = pd.read_csv(mc_synthetic_csv["labels_path"])
        assert (df_labels["is_sybil"] == 1).sum() > 0
        assert (df_labels["is_sybil"] == 0).sum() > 0


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST: Multi-Chain Graph Construction
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultichainGraph:
    def test_graph_has_nodes(self, mc_graph):
        G, _ = mc_graph
        assert G.number_of_nodes() > 0

    def test_graph_has_edges(self, mc_graph):
        G, _ = mc_graph
        assert G.number_of_edges() > 0

    def test_nodes_have_chain_attribute(self, mc_graph):
        G, _ = mc_graph
        for node in list(G.nodes())[:10]:
            assert "chains" in G.nodes[node]
            assert "num_chains" in G.nodes[node]

    def test_multi_chain_wallets_exist(self, mc_graph):
        G, _ = mc_graph
        multi = [n for n in G.nodes() if G.nodes[n].get("num_chains", 1) > 1]
        assert len(multi) > 0, "Expected wallets active on multiple chains"

    def test_edges_have_chain_id(self, mc_graph):
        G, _ = mc_graph
        for u, v, data in list(G.edges(data=True))[:10]:
            assert "chain_id" in data
            assert "edge_type" in data

    def test_bridge_edges_exist(self, mc_graph):
        G, _ = mc_graph
        bridge_edges = [
            (u, v) for u, v, d in G.edges(data=True)
            if d.get("is_bridge_tx", False) or d.get("edge_type") in ("bridge_hop", "cross_chain_identity")
        ]
        assert len(bridge_edges) > 0

    def test_graph_pickle_saved(self, mc_graph, mc_tmp_dir):
        _, graph_pkl = mc_graph
        assert os.path.exists(graph_pkl)


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST: 17-Feature Cross-Chain Extraction
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultichainFeatures:
    def test_feature_count_is_17(self, mc_features):
        from features.crosschain_extractor import MULTICHAIN_FEATURE_COLS
        for col in MULTICHAIN_FEATURE_COLS:
            assert col in mc_features.columns, f"Missing feature: {col}"

    def test_has_node_id(self, mc_features):
        assert "node_id" in mc_features.columns

    def test_num_chains_active_populated(self, mc_features):
        assert (mc_features["num_chains_active"] >= 1).all()

    def test_multi_chain_wallets_have_num_chains_gt_1(self, mc_features):
        multi = mc_features[mc_features["num_chains_active"] > 1]
        assert len(multi) > 0

    def test_bridge_tx_count_positive_for_some(self, mc_features):
        assert (mc_features["bridge_tx_count"] > 0).sum() > 0

    def test_bridge_tx_ratio_bounded(self, mc_features):
        assert (mc_features["bridge_tx_ratio"] >= 0).all()
        assert (mc_features["bridge_tx_ratio"] <= 1.0 + 1e-6).all()

    def test_cross_chain_degree_nonnegative(self, mc_features):
        assert (mc_features["cross_chain_degree"] >= 0).all()

    def test_original_12_features_present(self, mc_features):
        original = [
            "in_degree", "out_degree", "total_tx_count", "unique_interactions",
            "avg_value_sent", "avg_gas", "tx_frequency", "node_age_days",
            "reciprocity", "clustering_coeff", "betweenness_centrality", "pagerank",
        ]
        for col in original:
            assert col in mc_features.columns

    def test_features_csv_saved(self, mc_features, mc_tmp_dir):
        path = os.path.join(mc_tmp_dir["processed"], "features_multichain.csv")
        assert os.path.exists(path)


# ═══════════════════════════════════════════════════════════════════════════════
#  TEST: Cross-Chain GNN Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestMultichainGNN:
    def test_pyg_data_has_17_features(self, mc_features, mc_graph, mc_tmp_dir, mc_synthetic_csv):
        mp = pytest.MonkeyPatch()
        import models.crosschain_gnn as mc_gnn
        mp.setattr(mc_gnn, "RAW_MULTICHAIN_LABELS_PATH",
                   mc_synthetic_csv["labels_path"])

        from models.crosschain_gnn import (
            build_multichain_pyg_data, generate_multichain_labels
        )
        G, _ = mc_graph
        labels = generate_multichain_labels(mc_features)
        data = build_multichain_pyg_data(mc_features, G, labels)

        assert data.num_node_features == 17
        mp.undo()

    def test_labels_loaded_from_csv(self, mc_features, mc_synthetic_csv):
        mp = pytest.MonkeyPatch()
        import models.crosschain_gnn as mc_gnn
        mp.setattr(mc_gnn, "RAW_MULTICHAIN_LABELS_PATH",
                   mc_synthetic_csv["labels_path"])

        from models.crosschain_gnn import generate_multichain_labels
        labels = generate_multichain_labels(mc_features)

        assert (labels == 1).sum() > 0  # has Sybils
        assert (labels == 0).sum() > 0  # has Humans
        mp.undo()

    def test_pyg_data_has_edges(self, mc_features, mc_graph, mc_tmp_dir, mc_synthetic_csv):
        mp = pytest.MonkeyPatch()
        import models.crosschain_gnn as mc_gnn
        mp.setattr(mc_gnn, "RAW_MULTICHAIN_LABELS_PATH",
                   mc_synthetic_csv["labels_path"])

        from models.crosschain_gnn import (
            build_multichain_pyg_data, generate_multichain_labels
        )
        G, _ = mc_graph
        labels = generate_multichain_labels(mc_features)
        data = build_multichain_pyg_data(mc_features, G, labels)

        assert data.num_edges > 0
        mp.undo()

    def test_pyg_data_has_train_val_test_masks(self, mc_features, mc_graph, mc_synthetic_csv):
        mp = pytest.MonkeyPatch()
        import models.crosschain_gnn as mc_gnn
        mp.setattr(mc_gnn, "RAW_MULTICHAIN_LABELS_PATH",
                   mc_synthetic_csv["labels_path"])

        from models.crosschain_gnn import (
            build_multichain_pyg_data, generate_multichain_labels
        )
        G, _ = mc_graph
        labels = generate_multichain_labels(mc_features)
        data = build_multichain_pyg_data(mc_features, G, labels)

        assert data.train_mask.sum() > 0
        assert data.val_mask.sum() > 0
        assert data.test_mask.sum() > 0
        mp.undo()
