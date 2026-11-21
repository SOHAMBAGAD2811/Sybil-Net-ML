"""
tests/conftest.py
─────────────────────────────────────────────────────────────────────────────
Shared fixtures for the Sybil-Net test suite.

Design:
  • session-scoped tmp dir via tmp_path_factory (compatible with session scope)
  • Module-level constants patched with pytest.MonkeyPatch() (creates its own
    context, not tied to function scope)
  • Heavy graph + feature objects built once and cached for the whole session
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import csv
import time
import uuid
import pickle
import random
import pytest
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers exposed to test modules
# ─────────────────────────────────────────────────────────────────────────────

def make_addr(prefix: str = "") -> str:
    return f"0x{prefix}{uuid.uuid4().hex[:40 - len(prefix)]}"


def make_tx(frm, to, now, value=None, gas=21_000):
    return {
        "hash":        f"0x{uuid.uuid4().hex}",
        "blockNumber": str(random.randint(18_000_000, 22_000_000)),
        "timeStamp":   str(now - random.randint(0, 86_400 * 30)),
        "from":        frm,
        "to":          to,
        "value":       str(value or random.randint(10**15, 5 * 10**18)),
        "gas":         str(gas),
        "gasPrice":    str(random.randint(10**9, 5 * 10**10)),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Session-scoped temp directory
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def tmp_dir(tmp_path_factory):
    base = tmp_path_factory.mktemp("sybilnet")
    raw_dir       = base / "raw"
    processed_dir = base / "processed"
    raw_dir.mkdir()
    processed_dir.mkdir()
    return {
        "root":      str(base),
        "raw":       str(raw_dir),
        "processed": str(processed_dir),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Synthetic CSV with known Sybil patterns
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def synthetic_csv(tmp_dir):
    random.seed(42)
    now = int(time.time())

    controller = make_addr("b0")
    workers    = [make_addr("b1") for _ in range(10)]
    ring       = [make_addr("cc") for _ in range(5)]
    honest     = [make_addr("aa") for _ in range(50)]

    txs = []

    # Hub-and-spoke
    for _ in range(200):
        w = random.choice(workers)
        txs.append(make_tx(controller, w, now))
        txs.append(make_tx(w, controller, now))

    # Wash ring
    for _ in range(60):
        for i in range(len(ring)):
            txs.append(make_tx(ring[i], ring[(i + 1) % len(ring)], now))

    # Honest
    for _ in range(300):
        frm = random.choice(honest)
        to  = random.choice(honest)
        while to == frm:
            to = random.choice(honest)
        txs.append(make_tx(frm, to, now))

    random.shuffle(txs)

    csv_path = os.path.join(tmp_dir["raw"], "transactions.csv")
    fieldnames = ["hash", "blockNumber", "timeStamp", "from", "to", "value", "gas", "gasPrice"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(txs)

    return {
        "csv_path":   csv_path,
        "controller": controller,
        "workers":    workers,
        "ring":       ring,
        "honest":     honest,
        "n_txs":      len(txs),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Graph (session-scoped, patches with its own MonkeyPatch context)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def built_graph(synthetic_csv, tmp_dir):
    """DiGraph built from synthetic_csv; graph.pkl saved to tmp processed dir."""
    # Use a session-owned MonkeyPatch to redirect PROCESSED_DATA_PATH
    mp = pytest.MonkeyPatch()
    import config.settings as settings
    import graph.builder as builder_mod
    mp.setattr(settings,     "PROCESSED_DATA_PATH", tmp_dir["processed"])
    mp.setattr(builder_mod,  "PROCESSED_DATA_PATH", tmp_dir["processed"],
               raising=False)

    from graph.builder import build_graph
    G = build_graph(data_path=synthetic_csv["csv_path"])

    graph_pkl = os.path.join(tmp_dir["processed"], "graph.pkl")
    if not os.path.exists(graph_pkl):
        with open(graph_pkl, "wb") as f:
            pickle.dump(G, f)

    mp.undo()
    return G, graph_pkl


# ─────────────────────────────────────────────────────────────────────────────
#  Feature DataFrame
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def feature_df(built_graph, synthetic_csv, tmp_dir):
    mp = pytest.MonkeyPatch()
    import config.settings as settings
    import features.extractor as extractor_mod
    mp.setattr(settings,      "PROCESSED_DATA_PATH", tmp_dir["processed"])
    mp.setattr(settings,      "RAW_DATA_PATH",       synthetic_csv["csv_path"])
    mp.setattr(extractor_mod, "PROCESSED_DATA_PATH", tmp_dir["processed"],
               raising=False)

    G, graph_pkl = built_graph
    from features.extractor import extract_features
    df = extract_features(
        graph_path=graph_pkl,
        raw_data_path=synthetic_csv["csv_path"],
    )
    mp.undo()
    return df, synthetic_csv


# ─────────────────────────────────────────────────────────────────────────────
#  PyG Data object
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pyg_data(feature_df, built_graph, tmp_dir):
    mp = pytest.MonkeyPatch()
    import models.gnn as gnn_mod
    # Point to a non-existent path so generate_labels uses topology heuristics
    mp.setattr(gnn_mod, "LABELS_CSV_PATH",
               os.path.join(tmp_dir["raw"], "labels.csv"))  # won't exist

    from models.gnn import build_pyg_data, generate_labels
    df, _  = feature_df
    G, _   = built_graph
    labels = generate_labels(df)
    data   = build_pyg_data(df, G, labels)
    mp.undo()
    return data, labels
