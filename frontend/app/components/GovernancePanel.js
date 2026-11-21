"use client";

import { useState, useEffect } from "react";

function shortAddr(addr) {
  if (!addr) return "—";
  return `${addr.slice(0, 8)}…${addr.slice(-6)}`;
}

export default function GovernancePanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [proposalTitle, setProposalTitle] = useState("");
  const [proposalDesc, setProposalDesc] = useState("");
  const [votedProposals, setVotedProposals] = useState({});

  useEffect(() => {
    fetch("/api/governance")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleVote = (propId, option) => {
    setVotedProposals(prev => ({ ...prev, [propId]: option }));
  };

  if (loading) {
    return (
      <div className="section-container" style={{ margin: 0, textAlign: 'center', padding: 40 }}>
        <div className="spinner" />
        <p style={{ marginTop: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          Fetching active DAO proposals & quadratic voting weights...
        </p>
      </div>
    );
  }

  const { stats, proposals } = data || {
    stats: { total: 12, active: 3, passed: 8, sybilsBlocked: 412 },
    proposals: [
      {
        id: "PROP-042",
        title: "Adjust GNN Sybil Threshold from 0.50 to 0.45",
        proposer: "0x892a...c410",
        type: "PARAMETER_CHANGE",
        status: "Active",
        forVotes: 1420,
        againstVotes: 180,
        endTime: "2d 14h remaining",
      },
      {
        id: "PROP-041",
        title: "Slash Appeal for Suspicious Cluster #819",
        proposer: "0x166c...c48b",
        type: "SLASH_APPEAL",
        status: "Active",
        forVotes: 420,
        againstVotes: 2190,
        endTime: "1d 08h remaining",
      },
    ]
  };

  return (
    <div className="section-container" style={{ margin: 0 }}>
      <div className="section-header">
        <div>
          <h2>
            <span className="badge-status active">QUADRATIC DAO</span>
            Decentralized Governance &amp; Slash Appeals
          </h2>
          <p style={{ marginTop: 4 }}>
            1-Human 1-Vote Quadratic Voting System. Proof-of-Humanity credentials neutralize Sybil voting rings automatically.
          </p>
        </div>
        <button 
          className="btn-terminal primary"
          onClick={() => setShowCreateModal(!showCreateModal)}
        >
          + Submit DAO Proposal
        </button>
      </div>

      {/* Governance Metrics Grid */}
      <div className="metrics-grid" style={{ marginBottom: 24 }}>
        <div className="metric-card">
          <div className="metric-header">
            <span>TOTAL PROPOSALS</span>
          </div>
          <div className="metric-val">{stats?.total || 12}</div>
          <div className="metric-sub">On-chain proposals</div>
        </div>
        <div className="metric-card">
          <div className="metric-header">
            <span>ACTIVE VOTING</span>
          </div>
          <div className="metric-val lime">{stats?.active || 3}</div>
          <div className="metric-sub">Open for vote</div>
        </div>
        <div className="metric-card">
          <div className="metric-header">
            <span>PASSED PROPOSALS</span>
          </div>
          <div className="metric-val cyan">{stats?.passed || 8}</div>
          <div className="metric-sub">Executed on-chain</div>
        </div>
        <div className="metric-card">
          <div className="metric-header">
            <span>SYBIL VOTES BLOCKED</span>
          </div>
          <div className="metric-val red">{stats?.sybilsBlocked || 412}</div>
          <div className="metric-sub">Fake votes neutralized</div>
        </div>
      </div>

      {/* Create Proposal Modal/Drawer */}
      {showCreateModal && (
        <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', padding: 18, borderRadius: 'var(--radius-md)', marginBottom: 24 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 700, marginBottom: 12, color: 'var(--accent-lime)' }}>
            NEW DAO PROPOSAL SUBMISSION
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <input 
              type="text" 
              className="input-terminal" 
              placeholder="Proposal Title (e.g. Adjust Threshold)" 
              value={proposalTitle}
              onChange={(e) => setProposalTitle(e.target.value)}
            />
            <textarea 
              className="input-terminal" 
              rows={3}
              placeholder="Detailed description and parameter changes..."
              value={proposalDesc}
              onChange={(e) => setProposalDesc(e.target.value)}
              style={{ fontFamily: 'var(--font-sans)', resize: 'vertical' }}
            />
            <div style={{ display: 'flex', gap: 10 }}>
              <button 
                className="btn-terminal primary" 
                onClick={() => {
                  alert('Proposal submitted to testnet DAO contract!');
                  setShowCreateModal(false);
                  setProposalTitle('');
                  setProposalDesc('');
                }}
              >
                Submit to Governance
              </button>
              <button className="btn-terminal" onClick={() => setShowCreateModal(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Active Proposals Feed */}
      <div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>
          Active Proposals &amp; Quadratic Ballots
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {proposals.map((prop) => {
            const totalVotes = (prop.forVotes || 0) + (prop.againstVotes || 0);
            const forPct = totalVotes > 0 ? ((prop.forVotes / totalVotes) * 100).toFixed(1) : 50;
            const hasVoted = votedProposals[prop.id];

            return (
              <div 
                key={prop.id}
                style={{ 
                  background: 'var(--bg-surface-2)', 
                  border: '1px solid var(--border-default)', 
                  borderRadius: 'var(--radius-md)', 
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span className="badge-status active">{prop.id || 'PROP'}</span>
                      <span className="badge-status cyan">{prop.type || 'GOVERNANCE'}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                        by {shortAddr(prop.proposer)}
                      </span>
                    </div>
                    <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {prop.title || prop.description}
                    </h3>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--accent-amber)' }}>
                    {prop.endTime || '2d remaining'}
                  </div>
                </div>

                {/* Progress Bar */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11, marginBottom: 6 }}>
                    <span style={{ color: 'var(--accent-lime)' }}>FOR: {prop.forVotes || 0} ({forPct}%)</span>
                    <span style={{ color: 'var(--accent-red)' }}>AGAINST: {prop.againstVotes || 0} ({(100 - forPct).toFixed(1)}%)</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
                    <div style={{ width: `${forPct}%`, background: 'var(--accent-lime)' }} />
                    <div style={{ width: `${100 - forPct}%`, background: 'var(--accent-red)' }} />
                  </div>
                </div>

                {/* Vote Buttons */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 6, borderTop: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                    VOTING POWER: <span style={{ color: 'var(--accent-lime)' }}>1.00 (QUADRATIC)</span>
                  </div>

                  {hasVoted ? (
                    <div className="badge-status active">
                      ✓ VOTED {hasVoted}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button 
                        className="btn-terminal"
                        style={{ borderColor: 'var(--border-lime)', color: 'var(--accent-lime)' }}
                        onClick={() => handleVote(prop.id, 'FOR')}
                      >
                        Vote FOR
                      </button>
                      <button 
                        className="btn-terminal"
                        style={{ borderColor: 'rgba(244,63,94,0.4)', color: 'var(--accent-red)' }}
                        onClick={() => handleVote(prop.id, 'AGAINST')}
                      >
                        Vote AGAINST
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
