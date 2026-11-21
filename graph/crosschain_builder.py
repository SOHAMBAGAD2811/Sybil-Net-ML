"""
graph/crosschain_builder.py
─────────────────────────────────────────────────────────────────────────────
Week 7 — Cross-Chain Graph Builder

Builds a unified multi-chain NetworkX DiGraph where:
  • Nodes = wallet addresses (with chain activity metadata)
  • Edges = transactions (with chain_id + bridge flags)
  • Bridge edges connect the same wallet across different chains
─────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import pickle
import pandas as pd
import networkx as nx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import RAW_MULTICHAIN_PATH, PROCESSED_DATA_PATH, BRIDGE_ADDRESSES


def build_multichain_graph(data_path: str = None) -> nx.DiGraph:
    """
    Build a unified cross-chain directed graph from multi-chain transaction data.

    Node attributes:
        chains          — set of chain_ids the wallet is active on
        is_bridge_contract — True if the address is a known bridge contract

    Edge attributes:
        weight       — transaction count for this (from, to) pair
        total_value  — sum of transferred value (wei)
        avg_value    — mean transferred value
        avg_gas      — mean gas used
        first_tx     — earliest transaction timestamp
        last_tx      — latest transaction timestamp
        chain_id     — chain this edge belongs to (0 for cross-chain bridge edges)
        is_bridge_tx — True if the transaction touches a bridge contract
        edge_type    — 'same_chain' | 'bridge_hop'
    """
    if not data_path:
        data_path = RAW_MULTICHAIN_PATH

    print("[CrossChain] Loading multi-chain transaction data…")
    df = pd.read_csv(data_path)
    print(f"[CrossChain] {len(df):,} transactions across chains: "
          f"{sorted(df['chain_id'].unique())}")

    df["value"] = df["value"].astype(float)
    df["gas"] = df["gas"].astype(float)
    df["is_bridge_tx"] = df["is_bridge_tx"].astype(str).str.lower().isin(["true", "1"])

    G = nx.DiGraph()

    # ── Track which chains each wallet is active on ──────────────────────────
    wallet_chains: dict[str, set] = {}

    for _, row in df.iterrows():
        chain_id = int(row["chain_id"])
        frm = row["from"]
        to = row["to"]
        wallet_chains.setdefault(frm, set()).add(chain_id)
        wallet_chains.setdefault(to, set()).add(chain_id)

    # ── Group edges by (from, to, chain_id) ──────────────────────────────────
    grouped = df.groupby(["from", "to", "chain_id"]).agg(
        tx_count=("hash", "count"),
        total_value=("value", "sum"),
        avg_value=("value", "mean"),
        avg_gas=("gas", "mean"),
        first_tx=("timeStamp", "min"),
        last_tx=("timeStamp", "max"),
        has_bridge=("is_bridge_tx", "any"),
    ).reset_index()

    print(f"[CrossChain] Building graph from {len(grouped):,} aggregated edges…")

    for _, row in grouped.iterrows():
        frm = row["from"]
        to = row["to"]
        chain_id = int(row["chain_id"])

        # If edge already exists (same pair on different chain), combine
        if G.has_edge(frm, to):
            existing = G[frm][to]
            existing["weight"] += int(row["tx_count"])
            existing["total_value"] += row["total_value"]
            existing["avg_value"] = (existing["avg_value"] + row["avg_value"]) / 2
            existing["avg_gas"] = (existing["avg_gas"] + row["avg_gas"]) / 2
            existing["is_bridge_tx"] = existing["is_bridge_tx"] or bool(row["has_bridge"])
            # Keep cross-chain marker if multiple chains involved
            if existing.get("chain_id") != chain_id:
                existing["edge_type"] = "bridge_hop"
                existing["chain_id"] = 0  # 0 = cross-chain
        else:
            G.add_edge(
                frm, to,
                weight=int(row["tx_count"]),
                total_value=row["total_value"],
                avg_value=row["avg_value"],
                avg_gas=row["avg_gas"],
                first_tx=row["first_tx"],
                last_tx=row["last_tx"],
                chain_id=chain_id,
                is_bridge_tx=bool(row["has_bridge"]),
                edge_type="bridge_hop" if row["has_bridge"] else "same_chain",
            )

    # ── Set node attributes ──────────────────────────────────────────────────
    for node in G.nodes():
        chains = wallet_chains.get(node, set())
        G.nodes[node]["chains"] = chains
        G.nodes[node]["num_chains"] = len(chains)
        G.nodes[node]["is_bridge_contract"] = node in BRIDGE_ADDRESSES

    # ── Add virtual bridge-hop edges ─────────────────────────────────────────
    # For wallets active on multiple chains, add self-loop bridge edges
    # to capture the cross-chain identity link
    cross_chain_wallets = {
        addr for addr, chains in wallet_chains.items() if len(chains) > 1
    }
    bridge_edges_added = 0
    for wallet in cross_chain_wallets:
        if not G.has_edge(wallet, wallet):
            G.add_edge(
                wallet, wallet,
                weight=len(wallet_chains[wallet]),
                total_value=0,
                avg_value=0,
                avg_gas=0,
                first_tx="",
                last_tx="",
                chain_id=0,
                is_bridge_tx=True,
                edge_type="cross_chain_identity",
            )
            bridge_edges_added += 1

    print(f"[CrossChain] Graph built: {G.number_of_nodes():,} nodes, "
          f"{G.number_of_edges():,} edges")
    print(f"[CrossChain] Cross-chain wallets: {len(cross_chain_wallets):,}")
    print(f"[CrossChain] Virtual bridge edges added: {bridge_edges_added:,}")

    # ── Save ─────────────────────────────────────────────────────────────────
    graph_path = os.path.join(PROCESSED_DATA_PATH, "graph_multichain.pkl")
    with open(graph_path, "wb") as f:
        pickle.dump(G, f)
    print(f"[CrossChain] Graph saved → {graph_path}")

    return G


if __name__ == "__main__":
    build_multichain_graph()
