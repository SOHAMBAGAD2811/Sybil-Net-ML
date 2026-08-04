import os
import sys
import pickle
import json
import networkx as nx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sybil-Net Graph Explorer</title>
    <script src="https://unpkg.com/force-graph"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --panel-bg: rgba(255, 255, 255, 0.05);
            --panel-border: rgba(255, 255, 255, 0.1);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.5);
        }
        body, html {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background-color: var(--bg-color);
            font-family: 'Inter', sans-serif;
            color: var(--text-main);
            overflow: hidden;
        }
        #graph-container {
            width: 100%;
            height: 100%;
            position: absolute;
            top: 0;
            left: 0;
            z-index: 1;
        }
        .dashboard {
            position: absolute;
            top: 20px;
            left: 20px;
            width: 320px;
            z-index: 10;
            background: var(--panel-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            display: flex;
            flex-direction: column;
            gap: 20px;
            animation: slideIn 0.5s ease-out forwards;
        }
        @keyframes slideIn {
            from { transform: translateX(-50px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        h1 {
            font-size: 1.5rem;
            margin: 0;
            font-weight: 600;
            background: linear-gradient(90deg, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stat-card {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px var(--accent-glow);
        }
        .stat-label {
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: 300;
        }
        .stat-value.small {
            font-size: 1.1rem;
            word-break: break-all;
            color: #93c5fd;
        }
        .node-tooltip {
            background: rgba(15, 23, 42, 0.9) !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            border-radius: 8px !important;
            padding: 12px !important;
            font-family: 'Inter', sans-serif !important;
            backdrop-filter: blur(4px) !important;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5) !important;
            color: #fff !important;
        }
        .tooltip-title { font-weight: 600; color: #60a5fa; margin-bottom: 4px; font-size: 0.9rem;}
        .tooltip-info { font-size: 0.8rem; color: #cbd5e1; }
    </style>
</head>
<body>
    <div id="graph-container"></div>
    
    <div class="dashboard">
        <h1>Sybil-Net Explorer</h1>
        <p style="font-size: 0.9rem; color: var(--text-muted); margin-top: -10px;">Network Topology Analysis</p>
        
        <div class="stat-card">
            <div class="stat-label">Total Nodes</div>
            <div class="stat-value" id="total-nodes">-</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-label">Total Edges</div>
            <div class="stat-value" id="total-edges">-</div>
        </div>
        
        <div class="stat-card">
            <div class="stat-label">Highest Degree Node</div>
            <div class="stat-value small" id="top-node">-</div>
        </div>
    </div>

    <script>
        // Graph data injected by Python
        const graphData = __GRAPH_DATA__;
        
        // Update stats
        document.getElementById('total-nodes').textContent = graphData.nodes.length.toLocaleString();
        document.getElementById('total-edges').textContent = graphData.links.length.toLocaleString();
        
        if (graphData.nodes.length > 0) {
            const topNode = graphData.nodes.reduce((prev, current) => (prev.val > current.val) ? prev : current);
            document.getElementById('top-node').textContent = topNode.id.substring(0, 12) + "...";
        }

        // Color scale based on degree
        const getColor = (val) => {
            if (val > 50) return '#c084fc'; // Purple for hubs
            if (val > 20) return '#ef4444'; // Red for highly active
            if (val > 5) return '#f59e0b';  // Yellow for medium
            return '#3b82f6';               // Blue for standard nodes
        };

        const Graph = ForceGraph()(document.getElementById('graph-container'))
            .graphData(graphData)
            .nodeId('id')
            .nodeVal('val') // Size by degree
            .nodeLabel(node => `
                <div class="node-tooltip">
                    <div class="tooltip-title">Wallet Address</div>
                    <div class="tooltip-info" style="font-family: monospace;">${node.id}</div>
                    <div class="tooltip-info" style="margin-top: 8px;">Degree: <b>${node.val}</b></div>
                </div>
            `)
            .nodeColor(node => getColor(node.val))
            .linkSource('source')
            .linkTarget('target')
            .linkColor(() => 'rgba(255, 255, 255, 0.15)')
            .linkWidth(link => Math.max(1, Math.min(link.weight || 1, 5)))
            .backgroundColor('#0b0f19')
            .d3Force('charge', d3.forceManyBody().strength(-120))
            .d3Force('link', d3.forceLink().distance(40))
            .onNodeHover(node => {
                document.body.style.cursor = node ? 'pointer' : null;
            });
            
        // Initial animation
        setTimeout(() => {
            Graph.zoomToFit(1000, 50);
        }, 1000);
    </script>
</body>
</html>
"""

def visualize_graph(graph_path=None, sample_size=1000):
    if not graph_path:
        graph_path = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")
        
    print("Loading graph for visualization...")
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)
        
    print(f"Original graph has {G.number_of_nodes()} nodes.")
    
    if G.number_of_nodes() > sample_size:
        print(f"Sampling {sample_size} nodes for a performant UI...")
        degrees = sorted(G.degree(), key=lambda x: x[1], reverse=True)
        top_nodes = [n for n, d in degrees[:sample_size]]
        G_vis = G.subgraph(top_nodes)
    else:
        G_vis = G
        
    # Prepare JSON data
    nodes_data = []
    for node in G_vis.nodes():
        deg = G_vis.degree(node)
        nodes_data.append({
            "id": node,
            "val": deg
        })
        
    links_data = []
    for u, v, data in G_vis.edges(data=True):
        links_data.append({
            "source": u,
            "target": v,
            "weight": data.get('weight', 1)
        })
        
    graph_json = {
        "nodes": nodes_data,
        "links": links_data
    }
    
    html_content = HTML_TEMPLATE.replace("__GRAPH_DATA__", json.dumps(graph_json))
    
    output_path = os.path.join(os.path.dirname(__file__), "graph_visualization.html")
    with open(output_path, "w") as f:
        f.write(html_content)
        
    print(f"Beautiful UI Visualization saved to {output_path}")

if __name__ == "__main__":
    visualize_graph()
