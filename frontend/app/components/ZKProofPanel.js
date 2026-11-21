'use client';

import { useState } from 'react';

export default function ZKProofPanel({ walletAddress, isHuman, walletScore }) {
  const [proofStatus, setProofStatus] = useState('idle'); // idle | generating | ready | verified
  const [proofHash, setProofHash] = useState('');
  const [circuitStats, setCircuitStats] = useState(null);

  const handleGenerateProof = () => {
    if (!walletAddress || !isHuman) return;

    setProofStatus('generating');

    // Simulate proof generation with circuit timing metrics
    setTimeout(() => {
      const mockHash = "0x" + Array.from({length: 16}, () => Math.floor(Math.random()*16).toString(16)).join('');
      setProofHash(mockHash);
      setCircuitStats({
        constraints: 14280,
        provingTime: '1,420 ms',
        circuit: 'BN254 Groth16 SybilScoreV3',
      });
      setProofStatus('ready');
    }, 2200);
  };

  const handleSubmitOnChain = () => {
    if (proofStatus !== 'ready') return;
    
    setProofStatus('verifying');
    
    // Simulate transaction submission
    setTimeout(() => {
      setProofStatus('verified');
    }, 1800);
  };

  return (
    <div className="section-container" style={{ margin: 0 }}>
      <div className="section-header">
        <div>
          <h2>
            <span className="badge-status cyan">ZK-SNARK</span>
            Zero-Knowledge Anonymous Proof Console
          </h2>
          <p style={{ marginTop: 4 }}>
            Generate a Groth16 cryptographic proof locally to verify your humanity across dApps without exposing transaction history or wallet address.
          </p>
        </div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
          CIRCUIT: <span style={{ color: 'var(--accent-lime)' }}>BN254 GROTH16</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20 }}>
        {/* Left Column: Generator & Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', padding: 16, borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              Proof Execution State
            </div>
            
            {proofStatus === 'idle' && (
              <div>
                <p style={{ color: 'var(--text-secondary)', marginBottom: 14, fontSize: 12 }}>
                  {walletAddress 
                    ? (isHuman ? 'Wallet eligible. Click below to compile ZK witness in-browser.' : 'Credential status unverified or flagged.')
                    : 'Connect wallet to generate anonymous proof witness.'}
                </p>
                <button 
                  className="btn-terminal primary"
                  onClick={handleGenerateProof}
                  disabled={!isHuman || !walletAddress}
                >
                  ⚡ Generate ZK Proof Witness Locally
                </button>
              </div>
            )}

            {proofStatus === 'generating' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0' }}>
                <div className="spinner" />
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-cyan)' }}>
                  Computing Groth16 Witness (14.2k constraints)...
                </div>
              </div>
            )}

            {proofStatus === 'ready' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-lime)' }}>
                  ✓ WITNESS COMPUTED SUCCESSFULLY
                </div>
                <div style={{ background: 'var(--bg-primary)', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-lime)', wordBreak: 'break-all' }}>
                  PROVING HASH: {proofHash}
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <button 
                    className="btn-terminal primary"
                    onClick={handleSubmitOnChain}
                  >
                    Submit Verifier TX On-Chain
                  </button>
                  <button 
                    className="btn-terminal"
                    onClick={() => {
                      navigator.clipboard.writeText(proofHash);
                      alert('Proof hash copied to clipboard');
                    }}
                  >
                    Copy Proof Hash
                  </button>
                </div>
              </div>
            )}

            {proofStatus === 'verifying' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0' }}>
                <div className="spinner" />
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--accent-amber)' }}>
                  Verifying proof parameters on SybilNetVerifier.sol...
                </div>
              </div>
            )}

            {proofStatus === 'verified' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div className="badge-status active" style={{ width: 'fit-content' }}>
                  ✓ ON-CHAIN CREDENTIAL VERIFIED
                </div>
                <p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                  Your anonymous proof is now recorded on-chain. You may claim gated access on any supported partner protocol without revealing your address.
                </p>
                <button className="btn-terminal" onClick={() => setProofStatus('idle')}>
                  Reset Proof Console
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Circuit Details & Metrics */}
        <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', padding: 16, borderRadius: 'var(--radius-md)', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', borderBottom: '1px solid var(--border-subtle)', paddingBottom: 6 }}>
            Circuit Specs & Verifier
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            <span style={{ color: 'var(--text-muted)' }}>Curves:</span>
            <span style={{ color: 'var(--text-primary)' }}>alt_bn128 (BN254)</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            <span style={{ color: 'var(--text-muted)' }}>Proving Scheme:</span>
            <span style={{ color: 'var(--text-primary)' }}>Groth16</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            <span style={{ color: 'var(--text-muted)' }}>Constraints:</span>
            <span style={{ color: 'var(--accent-cyan)' }}>14,280</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            <span style={{ color: 'var(--text-muted)' }}>Public Inputs:</span>
            <span style={{ color: 'var(--text-primary)' }}>Root, Nullifier, MinScore</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11 }}>
            <span style={{ color: 'var(--text-muted)' }}>Verification Gas:</span>
            <span style={{ color: 'var(--accent-lime)' }}>~194,500 gas</span>
          </div>

          {circuitStats && (
            <div style={{ marginTop: 'auto', paddingTop: 10, borderTop: '1px solid var(--border-subtle)', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-lime)' }}>
              ⚡ Proving Time: {circuitStats.provingTime}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
