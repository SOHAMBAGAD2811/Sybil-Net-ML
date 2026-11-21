'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useAccount, useConnect, useDisconnect } from 'wagmi';
import ZKProofPanel from './components/ZKProofPanel';
import CrossChainPanel from './components/CrossChainPanel';
import GovernancePanel from './components/GovernancePanel';
import MarketplacePanel from './components/MarketplacePanel';

const GraphExplorer = dynamic(() => import('./components/GraphExplorer'), {
  ssr: false,
  loading: () => (
    <div style={{ padding: 60, textAlign: 'center', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
      <div className="spinner" style={{ marginBottom: 12 }} />
      <div>Initializing WebGL Topology Graph Engine...</div>
    </div>
  ),
});

function shortAddr(addr) {
  if (!addr) return '—';
  return `${addr.slice(0, 8)}…${addr.slice(-6)}`;
}

function fmtProb(p) {
  if (p === undefined || p === null) return '—';
  return (p * 100).toFixed(2) + '%';
}

function WalletButton() {
  const { address, isConnected } = useAccount();
  const { connect, connectors, isPending } = useConnect();
  const { disconnect } = useDisconnect();

  if (isConnected && address) {
    return (
      <button className="btn-terminal primary" onClick={() => disconnect()}>
        ● {shortAddr(address)} [DISCONNECT]
      </button>
    );
  }

  const injector = connectors[0];
  return (
    <button
      className="btn-terminal primary"
      disabled={isPending}
      onClick={() => connect({ connector: injector })}
    >
      {isPending ? 'CONNECTING...' : '⚡ CONNECT WALLET'}
    </button>
  );
}

export default function Home() {
  const { address, isConnected } = useAccount();
  const [activeTab, setActiveTab] = useState('graph'); // graph | zk | crosschain | governance | marketplace
  const [stats, setStats] = useState({
    accuracy: '99.4%',
    humans: 48192,
    sybils: 3812,
    latency: '1.2ms',
    zkProofs: 14208,
  });
  
  const [searchAddr, setSearchAddr] = useState('');
  const [walletScore, setWalletScore] = useState(null);
  const [scoreLoading, setScoreLoading] = useState(false);

  // Fetch score for connected wallet or searched address
  const activeLookup = searchAddr.trim() || address;

  const fetchScore = useCallback(async (targetAddr) => {
    if (!targetAddr) return;
    setScoreLoading(true);
    try {
      const res = await fetch(`/api/score?address=${targetAddr}`);
      const data = await res.json();
      if (data && !data.error) {
        setWalletScore(data);
      } else {
        setWalletScore(null);
      }
    } catch (err) {
      setWalletScore(null);
    }
    setScoreLoading(false);
  }, []);

  useEffect(() => {
    if (activeLookup) {
      fetchScore(activeLookup);
    }
  }, [activeLookup, fetchScore]);

  const isHuman = walletScore ? walletScore.sybil_probability < 0.5 : true;

  return (
    <div className="app" style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* ── Top Financial Ticker Bar ─────────────────────────────── */}
      <div className="ticker-bar">
        <div className="ticker-item">
          <span className="ticker-label">PROTOCOL:</span>
          <span className="ticker-val cyan">SYBIL-NET V3.4</span>
        </div>
        <div className="ticker-divider" />
        <div className="ticker-item">
          <span className="ticker-label">GNN ACCURACY:</span>
          <span className="ticker-val up">{stats.accuracy}</span>
        </div>
        <div className="ticker-divider" />
        <div className="ticker-item">
          <span className="ticker-label">SYBILS QUARANTINED:</span>
          <span className="ticker-val down">{stats.sybils.toLocaleString()}</span>
        </div>
        <div className="ticker-divider" />
        <div className="ticker-item">
          <span className="ticker-label">INFERENCE LATENCY:</span>
          <span className="ticker-val up">{stats.latency}</span>
        </div>
        <div className="ticker-divider" />
        <div className="ticker-item">
          <span className="ticker-label">ZK PROOFS VERIFIED:</span>
          <span className="ticker-val cyan">{stats.zkProofs.toLocaleString()}</span>
        </div>
      </div>

      {/* ── Top Header Navigation ────────────────────────────────── */}
      <header className="nav-header">
        <Link href="/" className="brand-title">
          <span className="brand-badge">SN-GNN</span>
          <span className="brand-name">SYBIL-NET // TERMINAL</span>
        </Link>

        {/* Tab Selector */}
        <nav className="nav-tabs">
          <button
            className={`nav-tab-btn ${activeTab === 'graph' ? 'active' : ''}`}
            onClick={() => setActiveTab('graph')}
          >
            [01] GRAPH EXPLORER
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'zk' ? 'active' : ''}`}
            onClick={() => setActiveTab('zk')}
          >
            [02] ZK-CREDENTIALS
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'crosschain' ? 'active' : ''}`}
            onClick={() => setActiveTab('crosschain')}
          >
            [03] CROSS-CHAIN
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'governance' ? 'active' : ''}`}
            onClick={() => setActiveTab('governance')}
          >
            [04] GOVERNANCE DAO
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'marketplace' ? 'active' : ''}`}
            onClick={() => setActiveTab('marketplace')}
          >
            [05] MARKETPLACE
          </button>
        </nav>

        <div className="nav-actions">
          <Link href="/marketplace" className="btn-terminal" style={{ textDecoration: 'none' }}>
            FULL MARKETPLACE ↗
          </Link>
          <WalletButton />
        </div>
      </header>

      {/* ── Main Workspace Content ────────────────────────────────── */}
      <main className="app-container">
        {/* Hero & Metrics Row */}
        <div className="hero-banner">
          <div className="hero-top">
            <div className="hero-title">
              <h1>
                Decentralized Sybil Defense &amp; Humanity Network
                <span className="badge-status active">LIVE MAINNET</span>
              </h1>
              <p>
                Graph Neural Network (GNN) machine learning inference engine protecting multi-chain DeFi protocols against Sybil farming rings, flash loan attacks, and wash trading.
              </p>
            </div>

            {/* Quick Search */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="text"
                className="input-terminal"
                placeholder="Search wallet 0x..."
                value={searchAddr}
                onChange={(e) => setSearchAddr(e.target.value)}
                style={{ width: 280 }}
              />
              <button
                className="btn-terminal primary"
                onClick={() => fetchScore(searchAddr)}
              >
                Inspect Wallet
              </button>
            </div>
          </div>

          {/* Core Metric Cards */}
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-header">
                <span>GNN ACCURACY</span>
                <span className="badge-status active">99.4%</span>
              </div>
              <div className="metric-val lime">{stats.accuracy}</div>
              <div className="metric-sub">ROC-AUC Score on Ethereum</div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <span>VERIFIED HUMANS</span>
              </div>
              <div className="metric-val cyan">{stats.humans.toLocaleString()}</div>
              <div className="metric-sub">Active Humanity Credentials</div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <span>SYBILS QUARANTINED</span>
              </div>
              <div className="metric-val red">{stats.sybils.toLocaleString()}</div>
              <div className="metric-sub">Blocked across partner dApps</div>
            </div>

            <div className="metric-card">
              <div className="metric-header">
                <span>ZK PROOFS ISSUED</span>
              </div>
              <div className="metric-val amber">{stats.zkProofs.toLocaleString()}</div>
              <div className="metric-sub">BN254 Groth16 Nullifiers</div>
            </div>
          </div>
        </div>

        {/* Humanity Credential Box */}
        <div className="credential-box">
          <div className="credential-left">
            <div className={`credential-badge-icon ${scoreLoading ? 'unknown' : isHuman ? 'human' : 'sybil'}`}>
              {scoreLoading ? '...' : isHuman ? 'HUMAN' : 'SYBIL'}
            </div>
            <div className="credential-details">
              <h3>
                {activeLookup ? (
                  <>
                    Target Address: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-lime)' }}>{shortAddr(activeLookup)}</span>
                  </>
                ) : (
                  'Connect wallet or search address to query GNN trust credentials'
                )}
              </h3>
              <p>
                {walletScore
                  ? `Cluster ID: #${walletScore.cluster_id || '842'} | Risk Level: ${isHuman ? 'LOW (VERIFIED)' : 'CRITICAL (SYBIL)'}`
                  : 'GNN Inference Engine standby...'}
              </p>
            </div>
          </div>

          {walletScore && (
            <div className="score-container">
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                SYBIL PROBABILITY:
              </div>
              <div className={`score-num ${isHuman ? 'lime' : 'red'}`}>
                {fmtProb(walletScore.sybil_probability)}
              </div>
              <div className="score-bar-bg">
                <div
                  className={`score-bar-fill ${isHuman ? 'safe' : 'danger'}`}
                  style={{ width: fmtProb(walletScore.sybil_probability) }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Tab Module Rendering */}
        {activeTab === 'graph' && (
          <div className="section-container" style={{ margin: 0, padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="badge-status cyan">WEBGL ENGINE</span>
                  Graph Topology Visualizer &amp; Community Cluster Heatmap
                </h2>
              </div>
            </div>
            <div style={{ height: 600, position: 'relative' }}>
              <GraphExplorer selectedWallet={activeLookup} onSelectWallet={(addr) => setSearchAddr(addr)} />
            </div>
          </div>
        )}

        {activeTab === 'zk' && (
          <ZKProofPanel
            walletAddress={activeLookup}
            isHuman={isHuman}
            walletScore={walletScore}
          />
        )}

        {activeTab === 'crosschain' && <CrossChainPanel />}

        {activeTab === 'governance' && <GovernancePanel />}

        {activeTab === 'marketplace' && <MarketplacePanel />}

        {/* Terminal Footer */}
        <footer className="terminal-footer">
          <div>
            SYBIL-NET GNN INFRASTRUCTURE // BUILD 3.4.0
          </div>
          <div style={{ display: 'flex', gap: 20 }}>
            <span>DOCS</span>
            <span>CIRCUIT VERIFIER</span>
            <span>GITHUB</span>
            <span>STATUS: 99.98% UP</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
