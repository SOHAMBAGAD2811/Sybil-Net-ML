import os
import sys
import pickle
import re
import networkx as nx
from pyvis.network import Network

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import PROCESSED_DATA_PATH

# ── Node colour / classification ─────────────────────────────────────────────

def _classify(deg):
    if deg > 50:  return {"color": "#a855f7", "label": "Hub"}       # violet
    if deg > 20:  return {"color": "#ef4444", "label": "Active"}    # red
    if deg > 5:   return {"color": "#f59e0b", "label": "Medium"}    # amber
    return              {"color": "#00d4ff", "label": "Standard"}   # cyan


# ── CSS / JS we'll inject into the pyvis HTML ────────────────────────────────

_INJECT_HEAD = """
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        /* ── Theme overrides ─────────────────────────────────────── */
        body {
            background: #05070f !important;
            font-family: 'Space Grotesk', sans-serif !important;
            color: #e2e8f0 !important;
            margin: 0 !important;
            overflow: hidden !important;
        }

        /* Hide the pyvis toolbar / heading pyvis sometimes adds */
        h1, .vis-network-tooltip { display: none !important; }

        /* Make the canvas container fill the window */
        #mynetwork {
            width: 100vw !important;
            height: 100vh !important;
            border: none !important;
            background: #05070f !important;
        }

        /* ── Glassmorphism panel ─────────────────────────────────── */
        .sn-panel {
            position: fixed;
            top: 20px;
            left: 20px;
            width: 288px;
            z-index: 999;
            background: rgba(13, 17, 32, 0.78);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(100, 180, 255, 0.13);
            border-radius: 16px;
            padding: 22px 22px 18px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            box-shadow: 0 8px 40px rgba(0,0,0,0.5);
            animation: snSlide .55s cubic-bezier(.16,1,.3,1) both;
        }
        @keyframes snSlide {
            from { transform: translateX(-40px); opacity: 0; }
            to   { transform: translateX(0);     opacity: 1; }
        }

        /* Eyebrow */
        .sn-eyebrow {
            font-size: .62rem;
            font-weight: 600;
            letter-spacing: .18em;
            text-transform: uppercase;
            color: #00d4ff;
            display: flex;
            align-items: center;
            gap: 7px;
        }
        .sn-eyebrow::before {
            content: '';
            display: inline-block;
            width: 16px; height: 2px;
            background: #00d4ff;
            border-radius: 2px;
        }

        /* Title */
        .sn-title {
            font-size: 1.5rem;
            font-weight: 700;
            letter-spacing: -.02em;
            line-height: 1.1;
            background: linear-gradient(135deg, #00d4ff 0%, #a855f7 55%, #ec4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-top: -4px;
        }
        .sn-sub {
            font-size: .77rem;
            color: #64748b;
            margin-top: -8px;
        }

        /* Stats grid */
        .sn-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }
        .sn-stat {
            background: rgba(0,0,0,.32);
            border: 1px solid rgba(100,180,255,.1);
            border-radius: 10px;
            padding: 11px 13px;
            transition: border-color .25s;
        }
        .sn-stat:hover { border-color: rgba(0,212,255,.35); }
        .sn-stat-label {
            font-size: .6rem;
            font-weight: 600;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 5px;
        }
        .sn-stat-value {
            font-size: 1.45rem;
            font-weight: 300;
            color: #fff;
            letter-spacing: -.02em;
        }
        .sn-stat-value.cyan   { color: #00d4ff; }
        .sn-stat-value.violet { color: #a855f7; }
        .sn-stat-value.red    { color: #ef4444; }

        /* Divider */
        .sn-divider {
            height: 1px;
            background: rgba(100,180,255,.09);
        }

        /* Legend */
        .sn-legend-title {
            font-size: .6rem;
            font-weight: 600;
            letter-spacing: .1em;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 8px;
        }
        .sn-legend {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .sn-legend-item {
            display: flex;
            align-items: center;
            gap: 9px;
            font-size: .78rem;
            color: #e2e8f0;
        }
        .sn-dot {
            width: 9px; height: 9px;
            border-radius: 50%;
            flex-shrink: 0;
            box-shadow: 0 0 5px currentColor;
        }

        /* ── Status pill ─────────────────────────────────────────── */
        .sn-status {
            position: fixed;
            bottom: 18px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 999;
            background: rgba(13,17,32,.82);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(100,180,255,.12);
            border-radius: 100px;
            padding: 7px 18px;
            font-size: .7rem;
            color: #64748b;
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
            animation: snFadeUp .8s ease-out .4s both;
        }
        @keyframes snFadeUp {
            from { opacity: 0; transform: translateX(-50%) translateY(8px); }
            to   { opacity: 1; transform: translateX(-50%) translateY(0); }
        }
        .sn-pulse {
            width: 6px; height: 6px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 6px #10b981;
            animation: snPulse 2s infinite;
        }
        @keyframes snPulse {
            0%,100% { opacity:1; } 50% { opacity:.25; }
        }

        /* ── Tooltip override ────────────────────────────────────── */
        div.vis-tooltip {
            background: rgba(13,17,32,.95) !important;
            border: 1px solid rgba(100,180,255,.25) !important;
            border-radius: 8px !important;
            color: #e2e8f0 !important;
            font-family: 'Space Grotesk', sans-serif !important;
            font-size: .78rem !important;
            padding: 9px 13px !important;
            box-shadow: 0 4px 24px rgba(0,0,0,.5) !important;
            backdrop-filter: blur(8px) !important;
        }
    </style>
"""

_INJECT_BODY_OPEN = """
    <!-- ── Sybil-Net UI Panel ──────────────────────────────────── -->
    <div class="sn-panel">
        <div class="sn-eyebrow">Sybil Network</div>
        <div class="sn-title">Graph Explorer</div>
        <div class="sn-sub">Blockchain topology · anomaly detection</div>

        <div class="sn-stats">
            <div class="sn-stat">
                <div class="sn-stat-label">Nodes</div>
                <div class="sn-stat-value cyan" id="sn-nodes">—</div>
            </div>
            <div class="sn-stat">
                <div class="sn-stat-label">Edges</div>
                <div class="sn-stat-value" id="sn-edges">—</div>
            </div>
            <div class="sn-stat">
                <div class="sn-stat-label">Hubs</div>
                <div class="sn-stat-value violet" id="sn-hubs">—</div>
            </div>
            <div class="sn-stat">
                <div class="sn-stat-label">Active</div>
                <div class="sn-stat-value red" id="sn-active">—</div>
            </div>
        </div>

        <div class="sn-divider"></div>

        <div>
            <div class="sn-legend-title">GNN Trust Score</div>
            <div class="sn-legend">
                <div class="sn-legend-item">
                    <div class="sn-dot" style="background:#ef4444;color:#ef4444"></div>
                    <span><b>Sybil</b> &mdash; probability &ge; 70%</span>
                </div>
                <div class="sn-legend-item">
                    <div class="sn-dot" style="background:#f59e0b;color:#f59e0b"></div>
                    <span><b>Suspicious</b> &mdash; probability 30&ndash;69%</span>
                </div>
                <div class="sn-legend-item">
                    <div class="sn-dot" style="background:#10b981;color:#10b981"></div>
                    <span><b>Human</b> &mdash; probability &lt; 30%</span>
                </div>
                <div class="sn-legend-item">
                    <div class="sn-dot" style="background:#a855f7;color:#a855f7"></div>
                    <span><b>Unknown</b> &mdash; Hub / not scored</span>
                </div>
            </div>
        </div>
    </div>

    <!-- ── Status bar ──────────────────────────────────────────── -->
    <div class="sn-status" id="sn-status">
        <div class="sn-pulse"></div>
        <span>Loading graph…</span>
    </div>
"""

_INJECT_BODY_SCRIPT = """
    <script>
        // Populate stats injected by Python
        const _snNodes  = __SN_NODES__;
        const _snEdges  = __SN_EDGES__;
        const _snHubs   = __SN_HUBS__;
        const _snActive = __SN_ACTIVE__;
        document.getElementById('sn-nodes').textContent  = _snNodes.toLocaleString();
        document.getElementById('sn-edges').textContent  = _snEdges.toLocaleString();
        document.getElementById('sn-hubs').textContent   = _snHubs.toLocaleString();
        document.getElementById('sn-active').textContent = _snActive.toLocaleString();

        // Update status once vis.js fires stabilised
        const _net = window.network || null;
        document.addEventListener('DOMContentLoaded', () => {
            // vis.js attaches to window.network inside the pyvis template
            setTimeout(() => {
                const sn = document.getElementById('sn-status');
                sn.innerHTML = '<div class="sn-pulse"></div><span>' +
                    _snNodes.toLocaleString() + ' nodes &middot; ' +
                    _snEdges.toLocaleString() + ' edges &middot; live</span>';
            }, 2000);
        });
    </script>
"""

# ── Pyvis options (Barnes-Hut physics, original feel) ────────────────────────

_VIS_OPTIONS = """
{
  "nodes": {
    "borderWidth": 2,
    "borderWidthSelected": 4,
    "font": { "size": 0 }
  },
  "edges": {
    "color": { "color": "rgba(100,180,255,0.18)", "highlight": "rgba(0,212,255,0.7)" },
    "smooth": { "type": "continuous" },
    "width": 0.8,
    "selectionWidth": 2
  },
  "interaction": {
    "hover": true,
    "navigationButtons": false,
    "keyboard": true,
    "tooltipDelay": 150
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
"""


def _inject_theme(html: str, nodes: int, edges: int, hubs: int, active: int) -> str:
    """Post-process pyvis HTML to inject our UI theme."""

    # 1. Inject fonts + CSS before </head>
    html = html.replace("</head>", _INJECT_HEAD + "\n</head>", 1)

    # 2. Inject panel + status bar right after <body>
    html = re.sub(r"(<body[^>]*>)", r"\1\n" + _INJECT_BODY_OPEN, html, count=1)

    # 3. Inject stats script before </body>
    stats_script = (
        _INJECT_BODY_SCRIPT
        .replace("__SN_NODES__",  str(nodes))
        .replace("__SN_EDGES__",  str(edges))
        .replace("__SN_HUBS__",   str(hubs))
        .replace("__SN_ACTIVE__", str(active))
    )
    html = html.replace("</body>", stats_script + "\n</body>", 1)

    return html


# ── Main function ─────────────────────────────────────────────────────────────

def visualize_graph(graph_path=None, sample_size=500):
    if not graph_path:
        graph_path = os.path.join(PROCESSED_DATA_PATH, "graph.pkl")

    # Load Sybil Scores from GNN
    sybil_scores = {}
    scores_path = os.path.join(PROCESSED_DATA_PATH, "node_scores.csv")
    if os.path.exists(scores_path):
        import csv
        with open(scores_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sybil_scores[row['node_id'].lower()] = float(row['sybil_probability'])

    print("Loading graph for visualization...")
    with open(graph_path, "rb") as f:
        G = pickle.load(f)

    print(f"Original graph has {G.number_of_nodes()} nodes.")

    if G.number_of_nodes() > sample_size:
        print(f"Sampling {sample_size} nodes for a performant UI...")
        # Prefer sampling Sybils if we have scores, otherwise degree
        if sybil_scores:
            nodes_by_score = sorted(G.nodes(), key=lambda n: sybil_scores.get(n.lower(), 0), reverse=True)
            top_nodes = nodes_by_score[:sample_size]
        else:
            degrees = sorted(G.degree(), key=lambda x: x[1], reverse=True)
            top_nodes = [n for n, d in degrees[:sample_size]]
        G_vis = G.subgraph(top_nodes)
    else:
        G_vis = G

    # ── Build pyvis network ───────────────────────────────────────────────────
    net = Network(
        height="100vh",
        width="100%",
        bgcolor="#05070f",
        font_color="white",
        directed=True,
        notebook=False,
    )

    hubs = active = 0

    for node in G_vis.nodes():
        deg = G_vis.degree(node)
        
        # New Classification based on Sybil Score
        score = sybil_scores.get(node.lower(), -1)
        if score >= 0.7:
            c = {"color": "#ef4444", "label": "🚨 Sybil"}       # red
        elif score >= 0.3:
            c = {"color": "#f59e0b", "label": "⚠️ Suspicious"} # amber
        elif score >= 0.0:
            c = {"color": "#10b981", "label": "✅ Human"}       # green
        else:
            c = _classify(deg) # fallback to old logic

        size = max(8, min(deg * 1.8, 55))   # cap max size so hubs don't overwhelm

        if deg > 50:    hubs   += 1
        if deg > 20: active += 1

        net.add_node(
            node,
            label="",                              # no clutter — tooltip on hover
            title=f"<b style='color:{c['color']}'>{c['label']}</b><br>"
                  f"<span style='font-family:monospace;font-size:.8em'>{node[:16]}…</span><br>"
                  f"Degree: <b>{deg}</b>" + 
                  (f"<br>Sybil Prob: <b>{score*100:.1f}%</b>" if score >= 0 else ""),
            size=size,
            color={
                "background": c["color"],
                "border": "#05070f",
                "highlight": {"background": "#ffffff", "border": c["color"]},
                "hover":     {"background": c["color"], "border": "#ffffff"},
            },
        )

    for u, v, data in G_vis.edges(data=True):
        weight = data.get("weight", 1)
        net.add_edge(
            u, v,
            value=weight,
            title=f"Transactions: <b>{weight}</b>",
        )

    net.set_options(_VIS_OPTIONS)

    # Save raw pyvis HTML to a temp buffer then inject theme
    output_path = os.path.join(os.path.dirname(__file__), "graph_visualization.html")
    net.save_graph(output_path)

    with open(output_path, "r", encoding="utf-8") as f:
        raw_html = f.read()

    themed_html = _inject_theme(
        raw_html,
        nodes=G_vis.number_of_nodes(),
        edges=G_vis.number_of_edges(),
        hubs=hubs,
        active=active,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(themed_html)

    print(f"Graph visualization saved to {output_path}")


if __name__ == "__main__":
    visualize_graph()
