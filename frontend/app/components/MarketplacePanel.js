'use client';

import { useState, useEffect } from 'react';
import { useAccount, useChainId, useSwitchChain } from 'wagmi';
import { hardhat } from 'wagmi/chains';

const WALLETS = {
  human: { name: '🧑 Human Wallet', address: '0x285C0312ce4d3C1cD8C1649DfFc373B744110c5c' },
  sybil: { name: '🤖 Sybil Wallet', address: '0x166Cee66374774eC3827F2429E986DA87539c48b' },
};

function shortHash(hash) {
  if (!hash) return '';
  return hash.slice(0, 8) + '…' + hash.slice(-6);
}

function shortAddr(addr) {
  if (!addr) return '';
  return addr.slice(0, 6) + '…' + addr.slice(-4);
}

export default function MarketplacePanel({ onDemoChange }) {
  const { isConnected } = useAccount();
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();

  const [demoWallet, setDemoWallet] = useState('human');
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  
  const [chainState, setChainState] = useState({
    isHuman: false,
    hasClaimed: false,
    totalClaims: 0,
  });

  const activeAddress = WALLETS[demoWallet].address;

  useEffect(() => {
    let active = true;
    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/demo?address=${activeAddress}`);
        const data = await res.json();
        if (active && data && !data.error) {
          setChainState({
            isHuman: data.isHuman,
            hasClaimed: data.hasClaimed,
            totalClaims: data.totalClaims,
          });
        }
      } catch (err) {}
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [activeAddress]);

  useEffect(() => {
    if (onDemoChange) {
      onDemoChange({ role: demoWallet, isHuman: chainState.isHuman });
    }
  }, [demoWallet, chainState.isHuman, onDemoChange]);

  const handleWalletChange = (e) => {
    setDemoWallet(e.target.value);
    setLogs([]);
  };

  const addLog = (type, message, detail = '') => {
    setLogs((prev) => [{ time: new Date().toLocaleTimeString(), type, message, detail }, ...prev].slice(0, 5));
  };

  const executeAction = async (action) => {
    setLoading(true);
    addLog('info', `Broadcasting ${action} transaction to mempool...`);

    try {
      const res = await fetch('/api/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, address: activeAddress }),
      });
      const data = await res.json();

      if (!res.ok || data.error) {
        const err = data.error;
        if (typeof err === 'object') {
          addLog('error', err.title, err.detail);
        } else {
          addLog('error', 'Transaction Failed', err);
        }
      } else {
        addLog('success', 'Transaction Confirmed!', `Tx Hash: ${shortHash(data.hash)}`);
        setChainState(data.state);
      }
    } catch (err) {
      addLog('error', 'Network Failure', err.message);
    }
    setLoading(false);
  };

  return (
    <div className="section-container" style={{ margin: 0 }}>
      <div className="section-header">
        <div>
          <h2>
            <span className="badge-status active">VERIFIED DAPP</span>
            Sybil-Gated Airdrop &amp; Contract Sandbox
          </h2>
          <p style={{ marginTop: 4 }}>
            Interact with SybilNet testnet contracts. Sybil-flagged wallets are automatically reverted by on-chain modifier.
          </p>
        </div>

        {isConnected && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>DEMO ROLE:</span>
            <select 
              value={demoWallet} 
              onChange={handleWalletChange}
              className="input-terminal"
            >
              <option value="human">🧑 Human ({shortAddr(WALLETS.human.address)})</option>
              <option value="sybil">🤖 Sybil Bot ({shortAddr(WALLETS.sybil.address)})</option>
            </select>
          </div>
        )}
      </div>

      {!isConnected ? (
        <div style={{ padding: 32, background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', textAlign: 'center' }}>
          <p style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>Connect Web3 Wallet to test smart contract interactions.</p>
        </div>
      ) : chainId !== hardhat.id ? (
        <div style={{ padding: 20, background: 'var(--accent-red-dim)', border: '1px solid var(--accent-red)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
          <h3 style={{ color: 'var(--accent-red)', margin: '0 0 8px', fontSize: 14 }}>⚠️ Localhost Hardhat Network Required</h3>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>MetaMask is active, but must target local chain (Chain ID 31337).</p>
          <button 
            className="btn-terminal primary"
            onClick={() => switchChain({ chainId: hardhat.id })}
            style={{ background: 'var(--accent-red)', borderColor: 'var(--accent-red)', color: '#fff' }}
          >
            Switch to Localhost (31337)
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {/* Step 1: Stake & Mint */}
          <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', padding: 18, borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                STEP 01 // STAKE &amp; MINT
              </div>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Mint Humanity Credential</h3>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
                Deposit 0.01 ETH to register your GNN trust score on-chain.
              </p>
            </div>

            {chainState.isHuman ? (
              <div className="badge-status active">
                ✓ CREDENTIAL ACTIVE ON-CHAIN
              </div>
            ) : (
              <button 
                className="btn-terminal primary"
                onClick={() => executeAction('MINT')}
                disabled={loading}
              >
                {loading ? 'Executing...' : 'Stake 0.01 ETH & Mint'}
              </button>
            )}
          </div>

          {/* Step 2: Claim Airdrop */}
          <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', padding: 18, borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                STEP 02 // TRUST-GATED CLAIM
              </div>
              <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>Claim Protocol Tokens</h3>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
                Reverts if wallet is flagged as Sybil or missing valid credential.
              </p>
            </div>

            {chainState.hasClaimed ? (
              <div className="badge-status active">
                🎉 100 SYBL TOKENS CLAIMED
              </div>
            ) : (
              <button 
                className="btn-terminal"
                onClick={() => executeAction('CLAIM')}
                disabled={loading || !chainState.isHuman}
                style={{
                  background: chainState.isHuman ? 'var(--accent-lime)' : 'transparent',
                  color: chainState.isHuman ? '#000' : 'var(--text-muted)',
                  borderColor: chainState.isHuman ? 'var(--accent-lime)' : 'var(--border-default)'
                }}
              >
                {loading ? 'Executing...' : 'Claim 100 SYBL Tokens'}
              </button>
            )}
          </div>

          {/* Live Transaction Log Console */}
          <div style={{ gridColumn: '1 / -1', background: 'var(--bg-primary)', border: '1px solid var(--border-default)', padding: 16, borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 10 }}>
              Mempool &amp; Event Execution Console
            </div>
            {logs.length === 0 ? (
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                Console idle. Trigger an action above to view live RPC logs.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {logs.map((l, i) => (
                  <div 
                    key={i} 
                    style={{ 
                      fontFamily: 'var(--font-mono)', 
                      fontSize: 11, 
                      padding: '8px 12px', 
                      borderRadius: 'var(--radius-sm)',
                      background: l.type === 'error' ? 'var(--accent-red-dim)' : l.type === 'success' ? 'var(--accent-lime-dim)' : 'var(--bg-surface-2)',
                      border: `1px solid ${l.type === 'error' ? 'rgba(244,63,94,0.3)' : l.type === 'success' ? 'var(--border-lime)' : 'var(--border-subtle)'}`,
                      color: l.type === 'error' ? 'var(--accent-red)' : l.type === 'success' ? 'var(--accent-lime)' : 'var(--text-primary)'
                    }}
                  >
                    <span style={{ opacity: 0.6, marginRight: 10 }}>[{l.time}]</span>
                    <strong>{l.message}</strong>
                    {l.detail && <div style={{ marginTop: 2, opacity: 0.85, fontSize: 10 }}>{l.detail}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
