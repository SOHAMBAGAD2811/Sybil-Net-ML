import os
from data.ingestion import fetch_data
from graph.builder import build_graph
from features.extractor import extract_features
from utils.export import export_datasets
from visualization.viewer import visualize_graph

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
    
    print("\n=== Pipeline Complete ===")

if __name__ == "__main__":
    run_pipeline()
