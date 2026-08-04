import os
import sys
import pickle
import pandas as pd
import networkx as nx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH

def export_datasets(graph_path=None):
    if not graph_path:
        graph_path = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")
        
    print("Loading graph for export...")
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)
        
    # Export nodes
    nodes = list(G.nodes())
    df_nodes = pd.DataFrame({'node_id': nodes})
    nodes_path = os.path.join(PROCESSED_DATA_PATH, "nodes.csv")
    df_nodes.to_csv(nodes_path, index=False)
    print(f"Nodes exported to {nodes_path}")
    
    # Export edges
    edges = []
    for u, v, data in G.edges(data=True):
        edge_data = {'source': u, 'target': v}
        edge_data.update(data)
        edges.append(edge_data)
        
    df_edges = pd.DataFrame(edges)
    edges_path = os.path.join(PROCESSED_DATA_PATH, "edges.csv")
    df_edges.to_csv(edges_path, index=False)
    print(f"Edges exported to {edges_path}")

if __name__ == "__main__":
    export_datasets()
