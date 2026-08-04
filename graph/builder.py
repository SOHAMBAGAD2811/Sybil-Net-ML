import os
import sys
import pandas as pd
import networkx as nx
import pickle

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import RAW_DATA_PATH, PROCESSED_DATA_PATH

def build_graph(data_path=RAW_DATA_PATH):
    print("Loading data...")
    df = pd.read_csv(data_path)
    
    print("Building directed graph...")
    G = nx.DiGraph()
    
    # Aggregate edge features
    # df columns: hash, blockNumber, timeStamp, from, to, value, gas, gasPrice
    df['value'] = df['value'].astype(float)
    df['gas'] = df['gas'].astype(float)
    
    # Group by sender and receiver
    grouped = df.groupby(['from', 'to']).agg(
        tx_count=('hash', 'count'),
        total_value=('value', 'sum'),
        avg_value=('value', 'mean'),
        avg_gas=('gas', 'mean'),
        first_tx=('timeStamp', 'min'),
        last_tx=('timeStamp', 'max')
    ).reset_index()
    
    # Add edges
    for _, row in grouped.iterrows():
        G.add_edge(
            row['from'], 
            row['to'], 
            weight=row['tx_count'],
            total_value=row['total_value'],
            avg_value=row['avg_value'],
            avg_gas=row['avg_gas'],
            first_tx=row['first_tx'],
            last_tx=row['last_tx']
        )
        
    print(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
    
    # Save graph
    graph_path = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")
    with open(graph_path, 'wb') as f:
        pickle.dump(G, f)
    print(f"Graph saved to {graph_path}")
    
    return G

if __name__ == "__main__":
    build_graph()
