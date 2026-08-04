import os
import sys
import pickle
import networkx as nx
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH

def extract_features(graph_path=None):
    if not graph_path:
        graph_path = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")
        
    print("Loading graph...")
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)
        
    print("Extracting features...")
    
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    
    # Calculate weighted degrees
    in_degrees_weight = dict(G.in_degree(weight='weight'))
    out_degrees_weight = dict(G.out_degree(weight='weight'))
    
    # Centrality (using a sample or approximation if graph is too large, but for 5000 nodes it's fine)
    try:
        pagerank = nx.pagerank(G, weight='weight')
    except:
        pagerank = {n: 0 for n in G.nodes()}
        
    # Clustering coefficient
    # DiGraph clustering is supported but can be slow
    clustering = nx.clustering(G)
    
    features = []
    for node in G.nodes():
        node_feats = {
            'node_id': node,
            'in_degree': in_degrees.get(node, 0),
            'out_degree': out_degrees.get(node, 0),
            'total_tx_count': in_degrees_weight.get(node, 0) + out_degrees_weight.get(node, 0),
            'pagerank': pagerank.get(node, 0),
            'clustering_coeff': clustering.get(node, 0),
        }
        features.append(node_feats)
        
    df_features = pd.DataFrame(features)
    
    features_path = os.path.join(PROCESSED_DATA_PATH, "features.csv")
    df_features.to_csv(features_path, index=False)
    print(f"Features saved to {features_path}")
    
    return df_features

if __name__ == "__main__":
    extract_features()
