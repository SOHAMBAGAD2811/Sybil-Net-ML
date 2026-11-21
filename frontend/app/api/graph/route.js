import path from 'path';
import fs from 'fs';
import { NextResponse } from 'next/server';

// ─── CSV helpers ─────────────────────────────────────────────────────────────
function parseCSV(filePath) {
  const raw = fs.readFileSync(filePath, 'utf-8').trim().split('\n');
  const headers = raw[0].split(',').map((h) => h.trim());
  return raw.slice(1).map((line) => {
    const values = line.split(',');
    const obj = {};
    headers.forEach((h, i) => { obj[h] = (values[i] || '').trim(); });
    return obj;
  });
}

function buildAdjacency(edges) {
  const adj = new Map();
  for (const e of edges) {
    if (!adj.has(e.source)) adj.set(e.source, new Set());
    if (!adj.has(e.target)) adj.set(e.target, new Set());
    adj.get(e.source).add(e.target);
    adj.get(e.target).add(e.source);
  }
  return adj;
}

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const limit       = Math.min(parseInt(searchParams.get('limit') || '800', 10), 3000);
    const focusWallet = searchParams.get('focus')?.toLowerCase() || null;
    const filterMode  = searchParams.get('filter') || 'all';
    const page        = parseInt(searchParams.get('page') || '0', 10);
    const pageSize    = parseInt(searchParams.get('pageSize') || '800', 10);

    const dataDir      = path.join(process.cwd(), '..', 'data', 'processed');
    const nodesPath    = path.join(dataDir, 'nodes.csv');
    const edgesPath    = path.join(dataDir, 'edges.csv');
    const scoresPath   = path.join(dataDir, 'node_scores.csv');
    const featuresPath = path.join(dataDir, 'features.csv');

    if (!fs.existsSync(nodesPath) || !fs.existsSync(edgesPath)) {
      return NextResponse.json(
        { error: 'Graph data not ready. Run: python main.py' },
        { status: 404 }
      );
    }

    // ── Score map ─────────────────────────────────────────────────────────────
    const scoreMap = new Map();
    if (fs.existsSync(scoresPath)) {
      const rows = parseCSV(scoresPath);
      for (const row of rows) {
        if (!row.node_id) continue;
        const id = row.node_id.toLowerCase();
        const sybilProb = parseFloat(row.sybil_probability || '0');
        const hasPredLabel = 'predicted_label' in row;
        scoreMap.set(id, {
          predicted_label: hasPredLabel
            ? parseInt(row.predicted_label || '0', 10)
            : sybilProb >= 0.5 ? 1 : 0,
          sybil_probability: sybilProb,
          classification: (row.classification || '').trim() || (sybilProb >= 0.5 ? 'Sybil' : 'Human'),
        });
      }
    }

    // ── Feature map ───────────────────────────────────────────────────────────
    const featureMap = new Map();
    if (fs.existsSync(featuresPath)) {
      const rows = parseCSV(featuresPath);
      for (const row of rows) {
        if (row.node_id) featureMap.set(row.node_id.toLowerCase(), row);
      }
    }

    // ── Load all edges ────────────────────────────────────────────────────────
    const edgeRows = parseCSV(edgesPath);
    const allEdges = edgeRows
      .filter((r) => r.source && r.target)
      .map((r) => ({
        source: r.source.toLowerCase(),
        target: r.target.toLowerCase(),
        weight: parseFloat(r.weight || '1'),
        value:  parseFloat(r.total_value || '0'),
      }));

    // ── All nodes ─────────────────────────────────────────────────────────────
    const nodeRows    = parseCSV(nodesPath);
    const allNodeIds  = nodeRows.map((r) => r.node_id?.toLowerCase()).filter(Boolean);

    function getScore(id) {
      return scoreMap.get(id) || { predicted_label: 0, sybil_probability: 0.05, classification: 'Human' };
    }

    // ── Subgraph selection ────────────────────────────────────────────────────
    let selectedEdges = [];
    const includedNodeIds = new Set();

    if (focusWallet) {
      // 2-hop BFS from focused wallet
      const adj = buildAdjacency(allEdges);
      const hop1 = adj.get(focusWallet) || new Set();
      const hop2 = new Set();
      for (const n of hop1) {
        for (const nn of (adj.get(n) || new Set())) {
          if (nn !== focusWallet && !hop1.has(nn)) hop2.add(nn);
        }
      }
      const neighbourhood = new Set([focusWallet, ...hop1, ...Array.from(hop2).slice(0, 200)]);
      selectedEdges = allEdges.filter(
        (e) => neighbourhood.has(e.source) && neighbourhood.has(e.target)
      );
      for (const e of selectedEdges) {
        includedNodeIds.add(e.source);
        includedNodeIds.add(e.target);
      }
      includedNodeIds.add(focusWallet);

    } else {
      // Apply filter
      let candidateEdges = allEdges;
      if (filterMode === 'sybil') {
        candidateEdges = allEdges.filter((e) => {
          const s = getScore(e.source);
          const t = getScore(e.target);
          return s.predicted_label === 1 || t.predicted_label === 1;
        });
      } else if (filterMode === 'human') {
        candidateEdges = allEdges.filter((e) => {
          const s = getScore(e.source);
          const t = getScore(e.target);
          return s.predicted_label === 0 && t.predicted_label === 0;
        });
      }

      // Sort: sybil-heavy edges first for visible cluster grouping
      candidateEdges.sort((a, b) => {
        const aS = getScore(a.source).sybil_probability + getScore(a.target).sybil_probability;
        const bS = getScore(b.source).sybil_probability + getScore(b.target).sybil_probability;
        return bS - aS;
      });

      const offset = page * pageSize;
      selectedEdges = candidateEdges.slice(offset, offset + Math.min(limit, pageSize));
      for (const e of selectedEdges) {
        includedNodeIds.add(e.source);
        includedNodeIds.add(e.target);
      }

      // Add isolated sybil nodes (no edges on this page)
      if (filterMode !== 'human') {
        for (const id of allNodeIds) {
          if (includedNodeIds.size >= limit * 1.5) break;
          if (getScore(id).predicted_label === 1 && !includedNodeIds.has(id)) {
            includedNodeIds.add(id);
          }
        }
      }
    }

    // ── Build node objects ────────────────────────────────────────────────────
    const nodes = Array.from(includedNodeIds).map((id) => {
      const score = getScore(id);
      const feat  = featureMap.get(id) || {};
      return {
        id,
        ...score,
        in_degree:     feat.in_degree     ? parseFloat(feat.in_degree)     : undefined,
        out_degree:    feat.out_degree    ? parseFloat(feat.out_degree)    : undefined,
        tx_frequency:  feat.tx_frequency  ? parseFloat(feat.tx_frequency)  : undefined,
        pagerank:      feat.pagerank      ? parseFloat(feat.pagerank)      : undefined,
        node_age_days: feat.node_age_days ? parseFloat(feat.node_age_days) : undefined,
        clustering_coeff: feat.clustering_coeff ? parseFloat(feat.clustering_coeff) : undefined,
      };
    });

    // ── Totals for UI stats ───────────────────────────────────────────────────
    const totalSybils = Array.from(scoreMap.values()).filter((s) => s.predicted_label === 1).length;
    const filteredEdgeCount = (() => {
      if (filterMode === 'all') return allEdges.length;
      if (filterMode === 'sybil')
        return allEdges.filter((e) =>
          getScore(e.source).predicted_label === 1 || getScore(e.target).predicted_label === 1
        ).length;
      return allEdges.filter((e) =>
        getScore(e.source).predicted_label === 0 && getScore(e.target).predicted_label === 0
      ).length;
    })();

    return NextResponse.json({
      nodes,
      links: selectedEdges,
      meta: {
        totalGraphNodes:    allNodeIds.length,
        totalGraphEdges:    allEdges.length,
        totalScoredNodes:   scoreMap.size,
        totalSybils,
        totalHumans:        scoreMap.size - totalSybils,
        totalFilteredEdges: filteredEdgeCount,
        shownNodes:  nodes.length,
        shownEdges:  selectedEdges.length,
        page,
        pageSize,
        hasMore: (page + 1) * pageSize < filteredEdgeCount,
      },
    });

  } catch (err) {
    console.error('[/api/graph]', err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
