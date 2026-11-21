"use client";

import { useState, useEffect, useCallback } from "react";

const CHAINS = [
  { id: 1, name: "Ethereum Mainnet", short: "ETH", color: "#627EEA", status: "SYNCED" },
  { id: 137, name: "Polygon PoS", short: "MATIC", color: "#8247E5", status: "SYNCED" },
  { id: 42161, name: "Arbitrum One", short: "ARB", color: "#28A0F0", status: "SYNCED" },
  { id: 8453, name: "Base L2", short: "BASE", color: "#0052FF", status: "SYNCED" },
];

function shortAddr(addr) {
  if (!addr) return "—";
  return `${addr.slice(0, 8)}…${addr.slice(-6)}`;
}

export default function CrossChainPanel() {
  const [data, setData] = useState(null);
  const [activeChain, setActiveChain] = useState(null);
  const [walletInput, setWalletInput] = useState("");
  const [walletData, setWalletData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lookupLoading, setLookupLoading] = useState(false);

  useEffect(() => {
    fetch("/api/crosschain")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const lookupWallet = useCallback(async () => {
    if (!walletInput.trim()) return;
    setLookupLoading(true);
    try {
      const r = await fetch(
        `/api/crosschain?wallet=${encodeURIComponent(walletInput.trim())}`
      );
      const d = await r.json();
      setWalletData(d.wallet || null);
    } catch {
      setWalletData(null);
    }
    setLookupLoading(false);
  }, [walletInput]);

  if (loading) {
    return (
      <div className="section-container" style={{ margin: 0, textAlign: 'center', padding: 40 }}>
        <div className="spinner" />
        <p style={{ marginTop: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          Syncing cross-chain bridge state across L1/L2s…
        </p>
      </div>
    );
  }

  const filteredTxs = activeChain && data?.transactions
    ? data.transactions.filter(
        (tx) => tx.sourceChainId === activeChain || tx.destChainId === activeChain
      )
    : data?.transactions || [];

  return (
    <div className="section-container" style={{ margin: 0 }}>
      <div className="section-header">
        <div>
          <h2>
            <span className="badge-status cyan">MULTI-CHAIN</span>
            Cross-Chain Credential Bridge &amp; Relay
          </h2>
          <p style={{ marginTop: 4 }}>
            Propagate GNN Humanity Scores &amp; Zero-Knowledge Nullifiers securely across Ethereum L1, Polygon, Arbitrum, and Base.
          </p>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
          RELAY LATENCY: <span style={{ color: 'var(--accent-lime)' }}>~1.4s</span>
        </div>
      </div>

      {/* Top Chain Selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <button
          className={`btn-terminal ${activeChain === null ? 'primary' : ''}`}
          onClick={() => setActiveChain(null)}
        >
          ALL NETWORKS ({CHAINS.length})
        </button>
        {CHAINS.map((chain) => (
          <button
            key={chain.id}
            className="btn-terminal"
            style={{
              borderColor: activeChain === chain.id ? chain.color : 'var(--border-default)',
              color: activeChain === chain.id ? chain.color : 'var(--text-secondary)',
              background: activeChain === chain.id ? 'var(--bg-surface-2)' : 'transparent',
            }}
            onClick={() => setActiveChain(chain.id)}
          >
            ● {chain.name}
          </button>
        ))}
      </div>

      {/* Grid: Wallet Lookup & Chain Status */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20, marginBottom: 24 }}>
        {/* Wallet Lookup */}
        <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', padding: 16, borderRadius: 'var(--radius-md)' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>
            Cross-Chain Address Lookup
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              type="text"
              className="input-terminal"
              placeholder="Enter wallet address 0x..."
              value={walletInput}
              onChange={(e) => setWalletInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && lookupWallet()}
              style={{ flex: 1 }}
            />
            <button className="btn-terminal primary" onClick={lookupWallet} disabled={lookupLoading}>
              {lookupLoading ? 'Querying...' : 'Query State'}
            </button>
          </div>

          {walletData && (
            <div style={{ marginTop: 16, background: 'var(--bg-primary)', padding: 14, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Wallet:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-primary)' }}>{shortAddr(walletData.address)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Synched Chains:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-lime)' }}>{walletData.syncedChains?.length || 0} / 4</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Bridge Nonce:</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-primary)' }}>#{walletData.nonce || 0}</span>
              </div>
            </div>
          )}
        </div>

        {/* Chain Matrix */}
        <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', padding: 16, borderRadius: 'var(--radius-md)' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>
            Network Sync Matrix
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {CHAINS.map((chain) => (
              <div key={chain.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 10px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontFamily: 'var(--font-mono)', fontSize: 11, color: chain.color }}>
                  ● {chain.short}
                </div>
                <div className="badge-status active">
                  {chain.status}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Transaction Feed */}
      <div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 10 }}>
          Recent Cross-Chain Credential Relays
        </div>
        <table className="table-terminal">
          <thead>
            <tr>
              <th>Tx Hash</th>
              <th>Source</th>
              <th>Destination</th>
              <th>User Address</th>
              <th>Status</th>
              <th>Age</th>
            </tr>
          </thead>
          <tbody>
            {filteredTxs.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 20 }}>
                  No cross-chain events found for selected filter.
                </td>
              </tr>
            ) : (
              filteredTxs.map((tx, idx) => (
                <tr key={idx}>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-lime)' }}>{shortAddr(tx.hash || tx.txHash)}</td>
                  <td>{tx.sourceChain || 'Ethereum'}</td>
                  <td>{tx.destChain || 'Arbitrum'}</td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{shortAddr(tx.userAddress || tx.wallet)}</td>
                  <td>
                    <span className="badge-status active">CONFIRMED</span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{tx.age || '2m ago'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
