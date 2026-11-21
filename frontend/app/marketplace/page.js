'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { useAccount, useConnect, useDisconnect } from 'wagmi';
import './marketplace.css';

// ── helpers ───────────────────────────────────────────────────────────────────
const shortAddr = (a) => a ? `${a.slice(0,6)}…${a.slice(-4)}` : '';

const TICKER_DATA = [
  { sym: 'ETH/USD',  val: '1,842.40', chg: '+2.94%', up: true  },
  { sym: 'SYBL/USD', val: '0.0054',   chg: '+3.12%', up: true  },
  { sym: 'BTC/USD',  val: '61,220',   chg: '-0.44%', up: false },
  { sym: 'GAS',      val: '24 gwei',  chg: '',        up: true  },
  { sym: 'BOTS BLOCKED', val: '1,847', chg: '24h',   up: false },
  { sym: 'VERIFIED LPs', val: '3,219', chg: 'active', up: true  },
];

// ── Toast ─────────────────────────────────────────────────────────────────────
function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(onClose, 3000);
    return () => clearTimeout(t);
  }, [toast, onClose]);
  if (!toast) return null;
  return (
    <div className={`m-toast ${toast.type}`}>
      <span className="m-toast-icon">
        {toast.type === 'success' ? '↑' : '×'}
      </span>
      <div>
        <div className="m-toast-title">{toast.title}</div>
        <div className="m-toast-msg">{toast.msg}</div>
      </div>
    </div>
  );
}

// ── Wallet ────────────────────────────────────────────────────────────────────
function WalletBtn() {
  const { address, isConnected } = useAccount();
  const { connect, connectors, isPending } = useConnect();
  const { disconnect } = useDisconnect();
  if (isConnected && address) {
    return (
      <button className="m-wallet-connected" onClick={() => disconnect()}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0 }} />
        {shortAddr(address)}
      </button>
    );
  }
  return (
    <button className="m-wallet-btn" disabled={isPending} onClick={() => connect({ connector: connectors[0] })}>
      {isPending ? 'connecting…' : 'Connect Wallet'}
    </button>
  );
}

// ── NFT table row ─────────────────────────────────────────────────────────────
function NftRow({ nft, onBuy }) {
  const rar = (nft.rarity || 'common').toLowerCase();
  const trustColor = nft.trustScore > 80 ? 'var(--accent)' : nft.trustScore > 50 ? 'var(--warn)' : 'var(--danger)';
  return (
    <div className="m-nft-row">
      <div className={`m-nft-thumb ${rar}`}>{nft.emoji}</div>
      <div>
        <div className="m-nft-name">{nft.name}</div>
        <div className="m-nft-col">{nft.collection}</div>
      </div>
      <span className={`m-rarity ${rar}`}>{nft.rarity}</span>
      <div className="m-trust-cell">
        <span className="m-trust-num">{nft.trustScore}</span>
        <div className="m-trust-bar">
          <div className="m-trust-fill" style={{ width: `${nft.trustScore}%`, background: trustColor }} />
        </div>
      </div>
      <div>
        <div className="m-price-eth">Ξ {nft.price}</div>
        <div className="m-price-usd">${(nft.price * 1842).toFixed(0)}</div>
      </div>
      <div>
        <div className="m-bids">{nft.bids} bids</div>
        <div className="m-timer">{nft.timeLeft}</div>
      </div>
      <span style={{ color: nft.verified ? 'var(--accent)' : 'var(--danger)', fontSize: 10, fontFamily: 'var(--mono)', fontWeight: 600 }}>
        {nft.verified ? 'VERIFIED' : 'FLAGGED'}
      </span>
      <button
        className={`m-btn-buy ${!nft.verified ? 'blocked' : ''}`}
        onClick={() => nft.verified && onBuy(nft)}
      >
        {nft.verified ? 'Place Bid' : 'Blocked'}
      </button>
    </div>
  );
}

// ── Swap ──────────────────────────────────────────────────────────────────────
function SwapSection({ pairs, showToast }) {
  const [from, setFrom] = useState('');
  const [sel, setSel] = useState(0);
  const pair = pairs[sel] || {};
  const to = from ? (parseFloat(from) * pair.rate).toFixed(6) : '';

  return (
    <div className="m-swap-grid">
      {/* left: swap form */}
      <div className="m-swap-left">
        <div style={{ marginBottom: 24 }}>
          <div className="m-swap-label">You pay</div>
          <div className="m-swap-field">
            <input
              className="m-swap-input"
              type="number"
              placeholder="0.0"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
            <div className="m-token-pill">
              <div className="m-token-dot">{pair.from?.[0]}</div>
              {pair.from}
            </div>
          </div>

          <div className="m-swap-sep">
            <button className="m-swap-flip" onClick={() => {}}>⇅</button>
          </div>

          <div className="m-swap-label">You receive</div>
          <div className="m-swap-field">
            <input className="m-swap-input" placeholder="0.0" value={to} readOnly />
            <div className="m-token-pill">
              <div className="m-token-dot">{pair.to?.[0]}</div>
              {pair.to}
            </div>
          </div>
        </div>

        <div className="m-swap-meta">
          {[
            ['Rate',       `1 ${pair.from} = ${pair.rate?.toLocaleString()} ${pair.to}`],
            ['Fee',        `${pair.fee}%`],
            ['Liquidity',  `$${pair.liquidity}`],
            ['Vol 24h',    `$${pair.volume24h}`],
            ['Access',     pair.trustGated ? 'Verified wallets only' : 'Open'],
          ].map(([k, v]) => (
            <div key={k} className="m-swap-meta-row">
              <span>{k}</span>
              <span style={{ color: k === 'Access' && pair.trustGated ? 'var(--warn)' : undefined }}>{v}</span>
            </div>
          ))}
        </div>

        <button
          className="m-swap-submit"
          onClick={() => {
            if (!from) return showToast('error', 'Enter an amount', '');
            showToast('success', `${from} ${pair.from} → ${to} ${pair.to}`, 'Order submitted to mempool');
            setFrom('');
          }}
        >
          Swap {pair.from} → {pair.to}
        </button>

        <div style={{ marginTop: 10, fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--tx-3)', textAlign: 'center' }}>
          Protected by Sybil-Net oracle · Wash-trade detection live
        </div>
      </div>

      {/* right: pairs */}
      <div className="m-swap-right">
        <div className="m-pairs-table">
          <div className="m-pairs-head">
            <span>Pair</span>
            <span>Rate</span>
            <span>24h</span>
            <span>Vol</span>
          </div>
          {pairs.map((p, i) => (
            <div
              key={i}
              className={`m-pairs-row ${i === sel ? 'sel' : ''}`}
              onClick={() => setSel(i)}
            >
              <div className="m-pairs-name">
                {p.from}/{p.to}
                {p.trustGated && <span className="m-gate-tag">gated</span>}
              </div>
              <span className="m-pairs-rate">{p.rate?.toLocaleString()}</span>
              <span className={p.change24h >= 0 ? 'm-up' : 'm-down'}>
                {p.change24h >= 0 ? '+' : ''}{p.change24h}%
              </span>
              <span className="m-dim">${p.volume24h}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Pools ─────────────────────────────────────────────────────────────────────
function PoolsSection({ pools, showToast }) {
  return (
    <>
      {/* mini stat bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, background: 'var(--line)', border: '1px solid var(--line)', borderRadius: 'var(--r)', overflow: 'hidden', marginBottom: 24 }}>
        {[
          { label: 'Bots blocked 24h', val: '1,847', style: { color: 'var(--danger)' } },
          { label: 'Rewards distributed', val: '24,190 SYBL', style: { color: 'var(--accent)' } },
          { label: 'Verified LPs active', val: '3,219', style: { color: 'var(--tx)' } },
        ].map((s) => (
          <div key={s.label} style={{ background: 'var(--surface)', padding: '16px 20px' }}>
            <div style={{ fontSize: 10, color: 'var(--tx-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--mono)', letterSpacing: '-0.02em', ...s.style }}>{s.val}</div>
          </div>
        ))}
      </div>

      <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--r)', overflow: 'hidden', background: 'var(--surface)' }}>
        <div className="m-pools-table">
          <div className="m-pools-head">
            <span>Pool</span>
            <span>APY</span>
            <span>TVL</span>
            <span>Vol 24h</span>
            <span>Risk</span>
            <span></span>
          </div>
          {pools.map((p, i) => (
            <div key={i} className="m-pool-row">
              <div className="m-pool-name-cell">
                <div className="m-pool-pair">{p.name}</div>
                <div className="m-pool-tags">
                  {p.humanOnly && <span className="m-pool-tag gated">Verified-only</span>}
                  <span className="m-pool-tag">AMM v3</span>
                </div>
              </div>
              <div className="m-apy">{p.apy}%</div>
              <div className="m-tvl">{p.tvl}</div>
              <div className="m-vol">{p.volume24h}</div>
              <span className={`m-risk-pill ${p.risk.toLowerCase()}`}>{p.risk}</span>
              <div className="m-pool-actions">
                <button className="m-btn-pool add" onClick={() => showToast('success', `Adding to ${p.name}`, 'Position opened')}>Add</button>
                <button className="m-btn-pool rem" onClick={() => showToast('success', `Exiting ${p.name}`, 'Position closed')}>Exit</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ── Borrow ────────────────────────────────────────────────────────────────────
function BorrowSection({ markets, showToast }) {
  const TIERS = [
    { range: '≥ 80', mult: '3.5×', name: 'Platinum', col: 'var(--accent)' },
    { range: '60–79', mult: '2.5×', name: 'Gold',    col: 'var(--info)'   },
    { range: '40–59', mult: '1.5×', name: 'Silver',  col: 'var(--warn)'   },
    { range: '< 40',  mult: '0×',   name: 'None',    col: 'var(--danger)' },
  ];

  return (
    <>
      <div className="m-tiers">
        {TIERS.map((t) => (
          <div key={t.name} className="m-tier">
            <div className="m-tier-score" style={{ color: t.col }}>{t.range}</div>
            <div className="m-tier-label">Trust score</div>
            <div className="m-tier-mult">{t.mult}</div>
            <div style={{ fontSize: 10, color: 'var(--tx-3)' }}>borrow mult.</div>
            <div className="m-tier-name" style={{ color: t.col }}>{t.name}</div>
          </div>
        ))}
      </div>

      <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--r)', overflow: 'hidden', background: 'var(--surface)' }}>
        <div className="m-borrow-table">
          <div className="m-borrow-head">
            <span>Asset</span>
            <span>Supply APY</span>
            <span>Borrow APY</span>
            <span>Utilization</span>
            <span>TVL</span>
            <span></span>
          </div>
          {markets.map((m, i) => (
            <div key={i} className="m-borrow-row">
              <div className="m-asset-cell">
                <div className="m-asset-icon">{m.symbol}</div>
                <div>
                  <div className="m-asset-name">{m.asset}</div>
                  <div className="m-asset-sub">{m.trustMultiplier}× multiplier</div>
                </div>
              </div>
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{m.supplyApy}%</span>
              <span style={{ color: 'var(--info)', fontWeight: 600 }}>{m.borrowApy}%</span>
              <div className="m-util-cell">
                <div className="m-util-bar">
                  <div className="m-util-fill" style={{ width: `${m.utilization}%` }} />
                </div>
                <span className="m-util-pct">{m.utilization}%</span>
              </div>
              <span style={{ color: 'var(--tx-2)', fontFamily: 'var(--mono)', fontSize: 11 }}>{m.tvl}</span>
              <div className="m-borrow-btns">
                <button className="m-btn-supply" onClick={() => showToast('success', `Supply ${m.asset}`, 'Position opened')}>Supply</button>
                <button className="m-btn-borrow" onClick={() => showToast('success', `Borrow ${m.asset}`, 'Undercollateralised loan initiated')}>Borrow</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: 16, fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--tx-3)', lineHeight: 1.8 }}>
        Enforcement: <span style={{ color: 'var(--tx-2)' }}>SybilNet.sol</span> —
        GNN trust score is updated on-chain every 512 blocks. Score drop below tier threshold triggers automatic partial repayment.
        No traditional collateral required for Platinum and Gold tier wallets.
      </div>
    </>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'nfts',   label: 'NFT Exchange' },
  { id: 'swap',   label: 'Swap' },
  { id: 'pools',  label: 'Liquidity' },
  { id: 'borrow', label: 'Borrow' },
];

const FILTERS = [
  { id: 'all',      label: 'All'         },
  { id: 'verified', label: 'Verified'    },
  { id: 'human',    label: 'Human-Only'  },
  { id: 'mythic',   label: 'Mythic'      },
];

export default function MarketplacePage() {
  const { address, isConnected } = useAccount();
  const [tab, setTab]     = useState('nfts');
  const [data, setData]   = useState(null);
  const [load, setLoad]   = useState(true);
  const [filt, setFilt]   = useState('all');
  const [query, setQuery] = useState('');
  const [toast, setToast] = useState(null);

  const showToast = useCallback((type, title, msg) => setToast({ type, title, msg }), []);

  useEffect(() => {
    fetch('/api/marketplace').then(r => r.json()).then(setData).finally(() => setLoad(false));
  }, []);

  const nfts = useMemo(() => {
    if (!data?.nfts) return [];
    let list = data.nfts;
    if (filt === 'verified') list = list.filter(n => n.verified);
    if (filt === 'human')    list = list.filter(n => n.tags.includes('Human-Only'));
    if (filt === 'mythic')   list = list.filter(n => n.rarity === 'Mythic');
    if (query) {
      const q = query.toLowerCase();
      list = list.filter(n => n.name.toLowerCase().includes(q) || n.collection.toLowerCase().includes(q));
    }
    return list;
  }, [data, filt, query]);

  const stats = data?.stats;

  return (
    <div className="m-shell">
      {/* ── Nav ── */}
      <nav className="m-nav">
        <div className="m-nav-left">
          <Link href="/" className="m-logo">
            <div className="m-logo-mark">SN</div>
            Sybil-Net
          </Link>
          <div className="m-tabs">
            {TABS.map(t => (
              <button key={t.id} className={`m-tab ${tab === t.id ? 'on' : ''}`} onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="m-nav-right">
          {stats && (
            <div className="m-ticker">
              <span className="m-ticker-dot" />
              <span>SYBL {stats.sntPrice}</span>
              <span className="m-ticker-up">+{stats.sntChange24h}%</span>
            </div>
          )}
          <WalletBtn />
        </div>
      </nav>

      {/* ── Ticker strip ── */}
      <div className="m-ticker-bar">
        {TICKER_DATA.map((t, i) => (
          <div key={i} className="m-ticker-item">
            <span>{t.sym}</span>
            <span style={{ color: t.chg.startsWith('+') ? 'var(--accent)' : t.chg.startsWith('-') ? 'var(--danger)' : 'var(--tx-2)' }}>
              {t.val}
            </span>
            {t.chg && (
              <span style={{ color: t.chg.startsWith('+') ? 'var(--accent)' : t.chg.startsWith('-') ? 'var(--danger)' : 'var(--tx-3)', fontSize: 10 }}>
                {t.chg}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* ── Body ── */}
      <div className="m-body">
        <div className="m-page">

          {/* Stats strip */}
          {load ? (
            <div className="m-loading"><div className="m-spinner" /> loading market data</div>
          ) : stats && (
            <div className="m-stats-strip">
              {[
                { label: 'All-time volume', val: stats.totalVolume, cls: '' },
                { label: 'Total value locked', val: stats.totalTVL, cls: 'lime' },
                { label: 'Wash trades blocked', val: stats.washTradesBlocked.toLocaleString(), cls: 'red', chg: '24h', down: true },
                { label: 'Verified traders', val: stats.humanTraders.toLocaleString(), cls: '' },
                { label: 'NFT listings', val: `${stats.verifiedListings}/${stats.totalListings}`, cls: 'dim' },
                { label: 'Active pools', val: stats.activePools, cls: 'lime' },
              ].map((s) => (
                <div key={s.label} className="m-stat">
                  <div className="m-stat-label">{s.label}</div>
                  <div className={`m-stat-val ${s.cls}`}>{s.val}</div>
                  {s.chg && <div className={`m-stat-change ${s.down ? 'down' : 'up'}`}>{s.chg}</div>}
                </div>
              ))}
            </div>
          )}

          {/* Connect alert */}
          {!isConnected && (
            <div className="m-alert">
              <span style={{ fontFamily: 'var(--mono)', color: 'var(--accent)', fontSize: 12 }}>!</span>
              <span>
                <strong>Connect wallet</strong> to access trust-gated features —
                undercollateralised borrowing up to <strong>3.5× stake</strong>, verified-only pools, and exclusive listings.
              </span>
            </div>
          )}

          {/* ── NFT Exchange ── */}
          {tab === 'nfts' && (
            <div className="m-section">
              {/* trending */}
              {data?.trending && (
                <>
                  <div className="m-section-head">
                    <span className="m-section-title">Trending Collections</span>
                    <span className="m-section-meta">updated 2m ago</span>
                  </div>
                  <div className="m-trending" style={{ marginBottom: 36 }}>
                    <div className="m-trending-head">
                      <span>#</span><span>Collection</span><span>Floor</span><span>24h %</span><span>Volume</span><span>Status</span>
                    </div>
                    {data.trending.map(c => (
                      <div key={c.rank} className="m-trending-row">
                        <span className="m-rank">{c.rank}</span>
                        <div className="m-col-name">
                          {c.verified ? <span className="m-dot-v" /> : <span className="m-dot-f" />}
                          {c.collection}
                        </div>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>Ξ {c.floor}</span>
                        <span className={c.change >= 0 ? 'm-up' : 'm-down'}>{c.change >= 0 ? '+' : ''}{c.change}%</span>
                        <span className="m-dim">{c.volume}</span>
                        <span style={{ fontSize: 9, fontWeight: 700, fontFamily: 'var(--mono)', textTransform: 'uppercase', color: c.verified ? 'var(--accent)' : 'var(--danger)' }}>
                          {c.verified ? 'Verified' : 'Flagged'}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* nft table */}
              <div className="m-section-head">
                <span className="m-section-title">
                  Listings
                  <span style={{ fontFamily: 'var(--mono)', fontWeight: 400, color: 'var(--tx-3)', marginLeft: 8 }}>{nfts.length}</span>
                </span>
                <div className="m-nft-controls">
                  {FILTERS.map(f => (
                    <button key={f.id} className={`m-chip ${filt === f.id ? 'on' : ''}`} onClick={() => setFilt(f.id)}>
                      {f.label}
                    </button>
                  ))}
                  <input className="m-search" placeholder="search…" value={query} onChange={e => setQuery(e.target.value)} />
                </div>
              </div>

              <div style={{ border: '1px solid var(--line)', borderRadius: 'var(--r)', overflow: 'hidden', background: 'var(--surface)' }}>
                <div className="m-nft-table">
                  <div className="m-nft-head">
                    <span></span>
                    <span>Name</span>
                    <span>Rarity</span>
                    <span>Trust</span>
                    <span>Price</span>
                    <span>Activity</span>
                    <span>Status</span>
                    <span></span>
                  </div>
                  {nfts.length === 0
                    ? <div className="m-empty">No listings match.</div>
                    : nfts.map(nft => (
                        <NftRow
                          key={nft.id}
                          nft={nft}
                          onBuy={n => showToast('success', `Bid placed on ${n.name}`, `Ξ ${n.price}`)}
                        />
                      ))
                  }
                </div>
              </div>
            </div>
          )}

          {/* ── Swap ── */}
          {tab === 'swap' && (
            <div className="m-section">
              <div className="m-section-head">
                <span className="m-section-title">Token Swap</span>
                <span className="m-section-meta">AMM v3 · wash-trade oracle active</span>
              </div>
              {data?.pairs && <SwapSection pairs={data.pairs} showToast={showToast} />}
            </div>
          )}

          {/* ── Liquidity ── */}
          {tab === 'pools' && (
            <div className="m-section">
              <div className="m-section-head">
                <span className="m-section-title">Liquidity Pools</span>
                <span className="m-section-meta">Verified-only pools block bot LPs at oracle level</span>
              </div>
              {data?.pools && <PoolsSection pools={data.pools} showToast={showToast} />}
            </div>
          )}

          {/* ── Borrow ── */}
          {tab === 'borrow' && (
            <div className="m-section">
              <div className="m-section-head">
                <span className="m-section-title">Undercollateralised Credit</span>
                <span className="m-section-meta">GNN trust score = collateral tier</span>
              </div>
              {data?.markets && <BorrowSection markets={data.markets} showToast={showToast} />}
            </div>
          )}

        </div>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
