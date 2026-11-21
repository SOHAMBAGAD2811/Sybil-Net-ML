'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

// ─── Colour palette (matches globals.css) ───────────────────────────────────
const COLOR = {
  sybil:    '#f43f5e',
  human:    '#a3e635',
  selected: '#38bdf8',
  edge:     'rgba(255,255,255,0.06)',
  edgeSybil:'rgba(244,63,94,0.35)',
  bg:       '#08090b',
};

function shortAddr(a) {
  if (!a) return '—';
  return `${a.slice(0, 10)}…${a.slice(-6)}`;
}

// ─── Main Component ──────────────────────────────────────────────────────────
export default function GraphExplorer({ selectedWallet, onSelectWallet }) {
  const canvasRef   = useRef(null);
  const stateRef    = useRef({              // mutable render state (not React state)
    nodes: [],
    links: [],
    nodeMap: new Map(),
    zoom: 1,
    panX: 0,
    panY: 0,
    dragging: false,
    dragStartX: 0,
    dragStartY: 0,
    hovered: null,
    animFrame: null,
    simRunning: false,
    velocities: new Map(),
  });

  const [meta, setMeta]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [filter, setFilter]     = useState('all');
  const [page, setPage]         = useState(0);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [error, setError]       = useState(null);
  const PAGE_SIZE = 800;

  // ── Fetch graph data ────────────────────────────────────────────────────────
  const fetchGraph = useCallback(async (filterMode, pageNum, focusWallet) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        filter:   filterMode,
        page:     pageNum,
        pageSize: PAGE_SIZE,
        limit:    PAGE_SIZE,
        ...(focusWallet ? { focus: focusWallet } : {}),
      });
      const res  = await fetch(`/api/graph?${params}`);
      const data = await res.json();

      if (data.error) { setError(data.error); return; }

      setMeta(data.meta);

      // Build node map for O(1) lookup
      const nodeMap = new Map();
      for (const n of data.nodes) nodeMap.set(n.id, n);

      // Assign initial positions in a circle / random layout
      const W = canvasRef.current?.clientWidth  || 900;
      const H = canvasRef.current?.clientHeight || 560;
      const cx = W / 2, cy = H / 2;

      // Sort: sybils in centre, humans on perimeter  
      const sybils = data.nodes.filter(n => n.predicted_label === 1);
      const humans = data.nodes.filter(n => n.predicted_label === 0);

      const layoutNode = (n, idx, total, radius, jitter) => {
        if (!n._x) {   // don't reset if already positioned
          const angle = (idx / total) * 2 * Math.PI;
          n._x = cx + radius * Math.cos(angle) + (Math.random() - 0.5) * jitter;
          n._y = cy + radius * Math.sin(angle) + (Math.random() - 0.5) * jitter;
        }
        n._vx = 0; n._vy = 0;
      };

      sybils.forEach((n, i) => layoutNode(n, i, Math.max(sybils.length,1), 80,  60));
      humans.forEach((n, i) => layoutNode(n, i, Math.max(humans.length, 1), 220, 180));

      // If focused wallet: place it at centre
      if (focusWallet) {
        const fn = nodeMap.get(focusWallet.toLowerCase());
        if (fn) { fn._x = cx; fn._y = cy; }
      }

      const st = stateRef.current;
      st.nodes   = data.nodes;
      st.links   = data.links;
      st.nodeMap = nodeMap;
      st.zoom    = 1;
      st.panX    = 0;
      st.panY    = 0;
      st.hovered = null;

    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGraph(filter, page, selectedWallet);
  }, [filter, page, selectedWallet, fetchGraph]);

  // ── Force-directed simulation (simple spring forces on Canvas) ─────────────
  const runFrame = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const st   = stateRef.current;
    const ctx  = canvas.getContext('2d');
    const W    = canvas.width;
    const H    = canvas.height;
    const nodes = st.nodes;
    const links  = st.links;

    // ── Simulation tick (lightweight) ─────────────────────────────────────────
    if (st.simRunning && nodes.length > 0 && nodes.length < 1000) {
      const alpha = 0.05;
      const cx = W / 2, cy = H / 2;

      // Repulsion between nodes
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = (a._x || cx) - (b._x || cx);
          const dy = (a._y || cy) - (b._y || cy);
          const d2 = dx*dx + dy*dy + 1;
          const f  = alpha * 800 / d2;
          a._vx = (a._vx || 0) + f * dx;
          a._vy = (a._vy || 0) + f * dy;
          b._vx = (b._vx || 0) - f * dx;
          b._vy = (b._vy || 0) - f * dy;
        }
        // Gravity toward centre
        a._vx = ((a._vx || 0) - (a._x - cx) * 0.003) * 0.9;
        a._vy = ((a._vy || 0) - (a._y - cy) * 0.003) * 0.9;
        a._x  = (a._x || cx) + (a._vx || 0);
        a._y  = (a._y || cy) + (a._vy || 0);
      }

      // Spring attraction along edges
      for (const lk of links) {
        const src = typeof lk.source === 'object' ? lk.source : st.nodeMap.get(lk.source);
        const tgt = typeof lk.target === 'object' ? lk.target : st.nodeMap.get(lk.target);
        if (!src || !tgt) continue;
        const dx = (tgt._x||0) - (src._x||0);
        const dy = (tgt._y||0) - (src._y||0);
        const d  = Math.sqrt(dx*dx + dy*dy) + 0.01;
        const f  = (d - 60) * 0.003 * alpha;
        src._x = (src._x||0) + f * dx;
        src._y = (src._y||0) + f * dy;
        tgt._x = (tgt._x||0) - f * dx;
        tgt._y = (tgt._y||0) - f * dy;
      }
    }

    // ── Draw ─────────────────────────────────────────────────────────────────
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = COLOR.bg;
    ctx.fillRect(0, 0, W, H);

    ctx.save();
    ctx.translate(st.panX, st.panY);
    ctx.scale(st.zoom, st.zoom);

    // Draw edges
    for (const lk of links) {
      const src = typeof lk.source === 'object' ? lk.source : st.nodeMap.get(lk.source);
      const tgt = typeof lk.target === 'object' ? lk.target : st.nodeMap.get(lk.target);
      if (!src || !tgt) continue;
      const isSybilEdge = src.predicted_label === 1 || tgt.predicted_label === 1;
      ctx.beginPath();
      ctx.strokeStyle = isSybilEdge ? COLOR.edgeSybil : COLOR.edge;
      ctx.lineWidth   = Math.min((lk.weight || 1) * 0.3 + 0.3, 2) / st.zoom;
      ctx.moveTo(src._x || 0, src._y || 0);
      ctx.lineTo(tgt._x || 0, tgt._y || 0);
      ctx.stroke();
    }

    // Draw nodes
    const selected = selectedWallet?.toLowerCase();
    for (const n of nodes) {
      const x = n._x || 0;
      const y = n._y || 0;
      const isSelected = n.id === selected;
      const isHovered  = n.id === st.hovered?.id;
      const isSybil    = n.predicted_label === 1;

      // Node radius scales with connectivity
      const r = isSelected ? 10 : (isSybil ? 8 : 4) / Math.sqrt(st.zoom);

      // Glow for Sybil / selected
      if (isSybil || isSelected) {
        ctx.beginPath();
        ctx.arc(x, y, r * 2.2, 0, Math.PI * 2);
        ctx.fillStyle = isSelected
          ? 'rgba(245,158,11,0.15)'
          : 'rgba(239,68,68,0.12)';
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = isSelected
        ? COLOR.selected
        : isHovered
        ? '#ffffff'
        : isSybil
        ? COLOR.sybil
        : COLOR.human;
      ctx.fill();

      // Label for selected / hovered / sybils
      if (isSelected || isHovered || (isSybil && st.zoom > 1.5)) {
        ctx.font = `${Math.max(9, 11 / st.zoom)}px JetBrains Mono, monospace`;
        ctx.fillStyle = '#ffffff';
        ctx.textAlign = 'center';
        ctx.fillText(shortAddr(n.id), x, y - r - 3);
      }
    }

    ctx.restore();

    st.animFrame = requestAnimationFrame(runFrame);
  }, [selectedWallet]);

  // ── Start / stop animation loop ────────────────────────────────────────────
  useEffect(() => {
    const st = stateRef.current;
    st.simRunning = true;

    // Slow sim down after 4s
    const timer = setTimeout(() => { if (st) st.simRunning = false; }, 4000);

    st.animFrame = requestAnimationFrame(runFrame);
    return () => {
      cancelAnimationFrame(st.animFrame);
      clearTimeout(timer);
    };
  }, [runFrame, meta]); // restart loop when new data arrives

  // ── Canvas size ────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      canvas.width  = canvas.clientWidth;
      canvas.height = canvas.clientHeight;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    return () => ro.disconnect();
  }, []);

  // ── Mouse / Touch events ───────────────────────────────────────────────────
  const toGraph = useCallback((cx, cy) => {
    const st = stateRef.current;
    return {
      x: (cx - st.panX) / st.zoom,
      y: (cy - st.panY) / st.zoom,
    };
  }, []);

  const hitTest = useCallback((gx, gy) => {
    const st = stateRef.current;
    let closest = null, closestD = 20;
    for (const n of st.nodes) {
      const dx = (n._x||0) - gx, dy = (n._y||0) - gy;
      const d  = Math.sqrt(dx*dx + dy*dy);
      if (d < closestD) { closestD = d; closest = n; }
    }
    return closest;
  }, []);

  const handleMouseMove = useCallback((e) => {
    const canvas = canvasRef.current;
    const rect   = canvas.getBoundingClientRect();
    const st     = stateRef.current;

    if (st.dragging) {
      st.panX += e.clientX - st.dragStartX;
      st.panY += e.clientY - st.dragStartY;
      st.dragStartX = e.clientX;
      st.dragStartY = e.clientY;
      return;
    }

    const { x, y } = toGraph(e.clientX - rect.left, e.clientY - rect.top);
    const node = hitTest(x, y);
    if (node !== st.hovered) {
      st.hovered = node;
      canvas.style.cursor = node ? 'pointer' : 'grab';
      setHoveredNode(node || null);
    }
  }, [toGraph, hitTest]);

  const handleMouseDown = useCallback((e) => {
    const st = stateRef.current;
    st.dragging   = true;
    st.dragStartX = e.clientX;
    st.dragStartY = e.clientY;
  }, []);

  const handleMouseUp = useCallback((e) => {
    const st = stateRef.current;
    if (!st.dragging) return;
    st.dragging = false;
    // If mouse didn't move much, treat as click
    const moved = Math.abs(e.clientX - st.dragStartX) + Math.abs(e.clientY - st.dragStartY);
    if (moved < 5) {
      const canvas = canvasRef.current;
      const rect   = canvas.getBoundingClientRect();
      const { x, y } = toGraph(e.clientX - rect.left, e.clientY - rect.top);
      const node = hitTest(x, y);
      if (node && onSelectWallet) onSelectWallet(node.id);
    }
  }, [toGraph, hitTest, onSelectWallet]);

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const st = stateRef.current;
    const canvas = canvasRef.current;
    const rect   = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 0.88;
    st.panX = mx - (mx - st.panX) * factor;
    st.panY = my - (my - st.panY) * factor;
    st.zoom = Math.max(0.15, Math.min(12, st.zoom * factor));
  }, []);

  const handleReset = () => {
    const st = stateRef.current;
    st.zoom = 1; st.panX = 0; st.panY = 0;
  };

  const handleRelayout = () => {
    const st = stateRef.current;
    const canvas = canvasRef.current;
    const W = canvas?.clientWidth  || 900;
    const H = canvas?.clientHeight || 560;
    const cx = W/2, cy = H/2;
    const sybils = st.nodes.filter(n => n.predicted_label === 1);
    const humans  = st.nodes.filter(n => n.predicted_label === 0);
    sybils.forEach((n, i) => {
      const a = (i/Math.max(sybils.length,1)) * 2 * Math.PI;
      n._x = cx + 80  * Math.cos(a) + (Math.random()-0.5)*60;
      n._y = cy + 80  * Math.sin(a) + (Math.random()-0.5)*60;
    });
    humans.forEach((n, i) => {
      const a = (i/Math.max(humans.length,1)) * 2 * Math.PI;
      n._x = cx + 240 * Math.cos(a) + (Math.random()-0.5)*180;
      n._y = cy + 240 * Math.sin(a) + (Math.random()-0.5)*180;
    });
    st.simRunning = true;
    setTimeout(() => { st.simRunning = false; }, 4000);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  const nodesShown = meta?.shownNodes   ?? 0;
  const edgesShown = meta?.shownEdges   ?? 0;
  const totalNodes = meta?.totalGraphNodes ?? 0;
  const totalEdges = meta?.totalGraphEdges ?? 0;
  const hasMore    = meta?.hasMore ?? false;

  return (
    <div className="table-section" style={{ overflow: 'hidden', marginBottom: 24 }}>

      {/* ── Header ── */}
      <div className="table-header" style={{ flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h2>🕸️ Network Topology Explorer</h2>
          {meta && (
            <span className="badge green" style={{ gap: 5, fontSize: 11 }}>
              <span style={{ width:6, height:6, borderRadius:'50%', background:'var(--green)', display:'inline-block', animation:'pulse 1.5s infinite' }} />
              {nodesShown.toLocaleString()} nodes · {edgesShown.toLocaleString()} edges
              {totalNodes > nodesShown && ` (of ${totalNodes.toLocaleString()} total)`}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Filter pills */}
          <div style={{ display:'flex', background:'var(--surface-2)', borderRadius:'var(--radius-sm)', padding:2 }}>
            {[['all','All'],['sybil','🔴 Sybils'],['human','🟢 Humans']].map(([mode, label]) => (
              <button key={mode}
                className={`action-btn ${filter === mode ? 'primary' : ''}`}
                style={{ margin:0, padding:'4px 10px', fontSize:11, border:'none',
                         color: filter===mode&&mode==='sybil' ? 'var(--red)' : filter===mode&&mode==='human' ? 'var(--green)' : '' }}
                onClick={() => { setFilter(mode); setPage(0); }}
              >{label}</button>
            ))}
          </div>

          {/* Pagination */}
          {page > 0 && (
            <button className="action-btn" style={{margin:0,padding:'4px 10px',fontSize:11}}
              onClick={() => setPage(p => p-1)}>← Prev page</button>
          )}
          {hasMore && (
            <button className="action-btn" style={{margin:0,padding:'4px 10px',fontSize:11}}
              onClick={() => setPage(p => p+1)}>Next page →</button>
          )}
          {meta && <span style={{fontSize:11,color:'var(--text-muted)'}}>p{page+1}</span>}

          {/* Controls */}
          <button className="action-btn" style={{margin:0,padding:'4px 10px',fontSize:11}} onClick={handleRelayout}>⟳ Relayout</button>
          <button className="action-btn" style={{margin:0,padding:'4px 10px',fontSize:11}} onClick={handleReset}>⌂ Reset view</button>
          {selectedWallet && (
            <button className="action-btn" style={{margin:0,padding:'4px 10px',fontSize:11}} onClick={() => onSelectWallet?.(null)}>Clear focus ✕</button>
          )}
        </div>
      </div>

      {/* ── Stats row ── */}
      {meta && (
        <div style={{ display:'flex', gap:16, padding:'8px 18px', borderBottom:'1px solid var(--border)', fontSize:11, color:'var(--text-muted)', flexWrap:'wrap' }}>
          <span>Total graph: <strong style={{color:'var(--text)'}}>{totalNodes.toLocaleString()}</strong> wallets, <strong style={{color:'var(--text)'}}>{totalEdges.toLocaleString()}</strong> edges</span>
          <span>Scored: <strong style={{color:'var(--blue)'}}>{meta.totalScoredNodes?.toLocaleString()}</strong></span>
          <span>Sybil: <strong style={{color:'var(--red)'}}>{meta.totalSybils?.toLocaleString()}</strong></span>
          <span>Human: <strong style={{color:'var(--green)'}}>{meta.totalHumans?.toLocaleString()}</strong></span>
          {selectedWallet && <span>Focus: <span className="mono" style={{color:'var(--amber)'}}>{shortAddr(selectedWallet)}</span></span>}
        </div>
      )}

      {/* ── Canvas ── */}
      <div style={{ position:'relative', width:'100%', height:580, background:COLOR.bg }}>
        {loading && (
          <div className="loading" style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', background:'rgba(10,12,15,0.85)', zIndex:10 }}>
            <div className="spinner" />
            <span>Loading graph data…</span>
          </div>
        )}
        {error && (
          <div style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', color:'var(--red)', zIndex:10, gap:12, padding:24 }}>
            <span style={{fontSize:32}}>⚠️</span>
            <strong>{error}</strong>
            <span style={{color:'var(--text-muted)',fontSize:12}}>Run: python main.py  (then reload)</span>
          </div>
        )}

        <canvas
          ref={canvasRef}
          style={{ width:'100%', height:'100%', display:'block', cursor:'grab' }}
          onMouseMove={handleMouseMove}
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseLeave={() => { stateRef.current.dragging = false; }}
          onWheel={handleWheel}
        />

        {/* Legend */}
        <div style={{ position:'absolute', bottom:14, left:14, background:'rgba(17,19,24,0.90)', backdropFilter:'blur(12px)', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', padding:'10px 14px', fontSize:11, color:'var(--text-muted)', pointerEvents:'none' }}>
          <div style={{ display:'flex', gap:14 }}>
            <span><span style={{color:COLOR.sybil}}>●</span> Sybil / Bot</span>
            <span><span style={{color:COLOR.human}}>●</span> Verified Human</span>
            <span><span style={{color:COLOR.selected}}>●</span> Selected</span>
          </div>
          {hoveredNode && (
            <div style={{ marginTop:6, paddingTop:6, borderTop:'1px solid var(--border)' }}>
              <span className="mono" style={{color:'var(--text)'}}>{hoveredNode.id}</span>
              <br/>
              <span style={{color: hoveredNode.predicted_label===1 ? 'var(--red)' : 'var(--green)'}}>
                {hoveredNode.classification} — {(hoveredNode.sybil_probability*100).toFixed(1)}% Sybil
              </span>
              {hoveredNode.out_degree != null && (
                <span style={{marginLeft:10, color:'var(--text-muted)'}}>
                  out: {hoveredNode.out_degree} / in: {hoveredNode.in_degree}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Hints */}
        <div style={{ position:'absolute', top:10, right:10, background:'rgba(17,19,24,0.75)', border:'1px solid var(--border)', borderRadius:4, padding:'4px 8px', fontSize:10, color:'var(--text-faint)', pointerEvents:'none' }}>
          Drag to pan · Scroll to zoom · Click node to inspect
        </div>
      </div>

      {/* ── Focused wallet detail ── */}
      {selectedWallet && (() => {
        const n = stateRef.current.nodeMap.get(selectedWallet.toLowerCase());
        if (!n) return null;
        return (
          <div style={{ padding:'14px 18px', borderTop:'1px solid var(--border)', display:'flex', gap:24, flexWrap:'wrap', fontSize:12, color:'var(--text-muted)' }}>
            <span><strong style={{color:'var(--text)'}}>Address:</strong> <span className="mono">{n.id}</span></span>
            <span><strong style={{color:'var(--text)'}}>Classification:</strong> <span className={`badge ${n.predicted_label===1?'red':'green'}`}>{n.classification}</span></span>
            <span><strong style={{color:'var(--text)'}}>Sybil Prob:</strong> <span style={{color:n.predicted_label===1?'var(--red)':'var(--green)'}}>{(n.sybil_probability*100).toFixed(2)}%</span></span>
            {n.out_degree != null && <span><strong style={{color:'var(--text)'}}>Out-degree:</strong> {n.out_degree}</span>}
            {n.in_degree  != null && <span><strong style={{color:'var(--text)'}}>In-degree:</strong>  {n.in_degree}</span>}
            {n.tx_frequency != null && <span><strong style={{color:'var(--text)'}}>Tx/day:</strong>   {n.tx_frequency?.toFixed(2)}</span>}
            {n.pagerank != null && <span><strong style={{color:'var(--text)'}}>PageRank:</strong> {n.pagerank?.toExponential(3)}</span>}
          </div>
        );
      })()}
    </div>
  );
}
