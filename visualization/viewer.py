import os
import sys
import pickle
import networkx as nx
from pyvis.network import Network

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH

def visualize_graph(graph_path=None, sample_size=500):
    if not graph_path:
        graph_path = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")
        
    print("Loading graph for visualization...")
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)
        
    print(f"Original graph has {G.number_of_nodes()} nodes.")
    
    # Subgraph for visualization if too large
    if G.number_of_nodes() > sample_size:
        print(f"Sampling {sample_size} nodes for visualization...")
        # Take nodes with highest degree
        degrees = sorted(G.degree(), key=lambda x: x[1], reverse=True)
        top_nodes = [n for n, d in degrees[:sample_size]]
        G_vis = G.subgraph(top_nodes)
    else:
        G_vis = G
        
    net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white", directed=True)
    
    # Add nodes with degree as size and hover info
    for node in G_vis.nodes():
        deg = G_vis.degree(node)
        net.add_node(
            node, 
            label=str(node)[:8] + "...", 
            title=f"Address: {node}\nDegree: {deg}",
            size=max(10, deg * 2)
        )
        
    # Add edges
    for u, v, data in G_vis.edges(data=True):
        weight = data.get('weight', 1)
        net.add_edge(u, v, value=weight, title=f"Txs: {weight}\nValue: {data.get('total_value', 0)}")
        
    net.set_options("""
    var options = {
      "nodes": {
        "borderWidth": 2,
        "borderWidthSelected": 4
      },
      "edges": {
        "color": {
          "inherit": true
        },
        "smooth": false
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -30000,
          "centralGravity": 0.3,
          "springLength": 95,
          "springConstant": 0.04,
          "damping": 0.09,
          "avoidOverlap": 0.1
        },
        "minVelocity": 0.75
      }
    }
    """)
    
    output_path = os.path.join(os.path.dirname(__file__), "graph_visualization.html")
    net.save_graph(output_path)
    print(f"Visualization saved to {output_path}")

if __name__ == "__main__":
    visualize_graph()
