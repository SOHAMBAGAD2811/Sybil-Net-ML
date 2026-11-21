import os
import argparse
from data.ingestion import fetch_data
from graph.builder import build_graph
from features.extractor import extract_features
from utils.export import export_datasets
from visualization.viewer import visualize_graph
from models.gnn import run_gnn_pipeline

def run_pipeline():
    print("=== Sybil-Net Week 1 Pipeline ===")
    
    print("\n--- Step 1: Data Ingestion ---")
    fetch_data()
    
    print("\n--- Step 2: Graph Construction ---")
    build_graph()
    
    print("\n--- Step 3: Feature Extraction ---")
    extract_features()
    
    print("\n--- Step 4: Dataset Export ---")
    export_datasets()
    
    print("\n--- Step 5: Visualization ---")
    visualize_graph()

    print("\n--- Step 6: GNN Model Training ---")
    run_gnn_pipeline()

    print("\n=== Pipeline Complete ===")


def run_multichain_pipeline():
    """Week 7 — Cross-Chain Pipeline: ingestion + graph + features + GNN across 4 chains."""
    from data.crosschain import fetch_multichain_data
    from graph.crosschain_builder import build_multichain_graph
    from features.crosschain_extractor import extract_multichain_features
    from models.crosschain_gnn import run_multichain_gnn_pipeline

    print("=== Sybil-Net Cross-Chain Pipeline (Week 7) ===")

    print("\n--- Step 1: Multi-Chain Data Ingestion ---")
    fetch_multichain_data()

    print("\n--- Step 2: Cross-Chain Graph Construction ---")
    build_multichain_graph()

    print("\n--- Step 3: Cross-Chain Feature Extraction (17 features) ---")
    extract_multichain_features()

    print("\n--- Step 4: Cross-Chain GNN Training ---")
    run_multichain_gnn_pipeline()

    print("\n=== Cross-Chain Pipeline Complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sybil-Net ML Pipeline")
    parser.add_argument(
        "--multichain", action="store_true",
        help="Run the Week 7 cross-chain pipeline instead of the default single-chain pipeline"
    )
    args = parser.parse_args()

    if args.multichain:
        run_multichain_pipeline()
    else:
        run_pipeline()
