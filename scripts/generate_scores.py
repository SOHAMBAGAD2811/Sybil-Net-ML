"""
generate_scores.py
==================
Generates node_scores.csv for ALL wallets in nodes.csv using graph-topology
heuristics - no ML training required.

Usage:
    python scripts/generate_scores.py
"""

import os, sys
import pandas as pd
import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'processed')

def load_edges():
    p = os.path.join(DATA, 'edges.csv')
    if not os.path.exists(p):
        sys.exit(f"[ERROR] {p} not found. Run python main.py first.")
    df = pd.read_csv(p)
    df['source'] = df['source'].str.lower()
    df['target'] = df['target'].str.lower()
    return df

def load_nodes():
    p = os.path.join(DATA, 'nodes.csv')
    if not os.path.exists(p):
        sys.exit(f"[ERROR] {p} not found. Run python main.py first.")
    df = pd.read_csv(p)
    df['node_id'] = df['node_id'].str.lower()
    return df

def compute_scores(nodes_df, edges_df):
    print(f"[Score] Loaded {len(nodes_df):,} nodes and {len(edges_df):,} edges")

    out_deg = edges_df.groupby('source').size().rename('out_degree')
    in_deg  = edges_df.groupby('target').size().rename('in_degree')
    tx_cnt  = pd.concat([
        edges_df.groupby('source').size(),
        edges_df.groupby('target').size()
    ]).groupby(level=0).sum().rename('total_tx')

    edge_pairs = set(zip(edges_df['source'], edges_df['target']))
    recip_counts = {}
    for src, tgt in edge_pairs:
        if (tgt, src) in edge_pairs:
            recip_counts[src] = recip_counts.get(src, 0) + 1
    recip_series = pd.Series(recip_counts, name='recip_count')

    val_stats = edges_df.groupby('source')['total_value'].agg(['mean', 'std']).fillna(0)
    val_stats['cv'] = val_stats['std'] / (val_stats['mean'].abs() + 1e-12)

    unique_src = edges_df.groupby('source')['target'].nunique().rename('unique_out')

    df = nodes_df.copy()
    df = df.join(out_deg,     on='node_id')
    df = df.join(in_deg,      on='node_id')
    df = df.join(tx_cnt,      on='node_id')
    df = df.join(recip_series,on='node_id')
    df = df.join(val_stats[['cv']], on='node_id')
    df = df.join(unique_src,  on='node_id')
    df = df.fillna(0)

    total = (df['out_degree'] + df['in_degree']).clip(lower=1)
    df['reciprocity'] = df['recip_count'] / total

    def pct_rank(s):
        return s.rank(pct=True).clip(0, 1)

    sig_out_deg     = pct_rank(df['out_degree'])
    sig_reciprocity = df['reciprocity'].clip(0, 1)
    sig_tx_cnt      = pct_rank(df['total_tx'])
    sig_concentration = (1 - pct_rank(df['unique_out'].clip(lower=0)))
    sig_value_robot = (1 - df['cv'].clip(0, 10) / 10).clip(0, 1)

    score = (
        0.30 * sig_out_deg +
        0.25 * sig_reciprocity +
        0.20 * sig_tx_cnt +
        0.15 * sig_concentration +
        0.10 * sig_value_robot
    ).clip(0, 1)

    score = (score ** 1.5).clip(0, 1)

    df['sybil_probability'] = np.round(score.values, 6)
    df['predicted_label']   = (score.values >= 0.50).astype(int)
    df['classification']    = df['predicted_label'].map({0: 'Human', 1: 'Sybil'})

    n_sybil = (df['predicted_label'] == 1).sum()
    print(f"[Score] Flagged {n_sybil:,} / {len(df):,} wallets as Sybil ({n_sybil/len(df)*100:.1f}%)")

    return df[['node_id', 'predicted_label', 'sybil_probability', 'classification']]


def main():
    nodes  = load_nodes()
    edges  = load_edges()
    scores = compute_scores(nodes, edges)
    out = os.path.join(DATA, 'node_scores.csv')
    scores.to_csv(out, index=False)
    print(f"[Done] node_scores.csv -> {out}  ({len(scores):,} wallets)")

if __name__ == '__main__':
    main()
