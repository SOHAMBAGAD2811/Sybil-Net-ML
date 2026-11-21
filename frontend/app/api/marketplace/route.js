import { NextResponse } from 'next/server';

const NFT_LISTINGS = [
  { id: 'nft-001', name: 'Sybil Sentinel #0042', collection: 'Sybil Sentinel Genesis', price: 0.48, lastSale: 0.31, trustScore: 96, verified: true, rarity: 'Legendary', rarityRank: 42, seller: '0xf39F…2266', bids: 7, timeLeft: '4h 22m', tags: ['Human-Only', 'Genesis'], emoji: '🛡️' },
  { id: 'nft-002', name: 'Graph Node #1187', collection: 'Network Topology Art', price: 0.12, lastSale: 0.09, trustScore: 88, verified: true, rarity: 'Rare', rarityRank: 187, seller: '0x7099…C8', bids: 2, timeLeft: '1d 6h', tags: ['Verified', 'Art'], emoji: '🕸️' },
  { id: 'nft-003', name: 'ZK Shield #0007', collection: 'ZK Proof Artifacts', price: 1.25, lastSale: 0.98, trustScore: 99, verified: true, rarity: 'Mythic', rarityRank: 7, seller: '0x3C44…3D', bids: 14, timeLeft: '2h 11m', tags: ['Human-Only', 'ZK', 'Mythic'], emoji: '⚡' },
  { id: 'nft-004', name: 'MEV Hunter #0291', collection: 'Mempool Defenders', price: 0.07, lastSale: 0.055, trustScore: 82, verified: true, rarity: 'Uncommon', rarityRank: 291, seller: '0x9098…85', bids: 1, timeLeft: '3d 14h', tags: ['MEV', 'Defenders'], emoji: '🔍' },
  { id: 'nft-005', name: 'Credentialed Whale #0001', collection: 'Sybil Sentinel Genesis', price: 4.5, lastSale: 3.8, trustScore: 100, verified: true, rarity: 'Mythic', rarityRank: 1, seller: '0x1CBd…55', bids: 31, timeLeft: '12h 00m', tags: ['Human-Only', 'Whale', 'Genesis', 'Mythic'], emoji: '🐋' },
  { id: 'nft-006', name: 'Bot Tombstone #9999', collection: 'Slashed Archives', price: 0.002, lastSale: 0.001, trustScore: 3, verified: false, rarity: 'Common', rarityRank: 9999, seller: '0xDEAD…BEEF', bids: 0, timeLeft: '7d 0h', tags: ['Slashed', 'Archive'], emoji: '💀' },
];

const SWAP_PAIRS = [
  { from: 'ETH', to: 'SYBL', rate: 1842.4, change24h: 3.12, liquidity: '4.2M', volume24h: '812K', fee: 0.3, trustGated: false },
  { from: 'SYBL', to: 'USDC', rate: 0.0054, change24h: -1.08, liquidity: '1.8M', volume24h: '340K', fee: 0.3, trustGated: false },
  { from: 'ETH', to: 'USDC', rate: 1841.0, change24h: 2.94, liquidity: '18.6M', volume24h: '5.1M', fee: 0.05, trustGated: false },
  { from: 'SYBL', to: 'WBTC', rate: 0.000000194, change24h: 0.44, liquidity: '620K', volume24h: '88K', fee: 0.3, trustGated: true },
];

const POOLS = [
  { name: 'ETH / SYBL', apy: 18.4, tvl: '$4.2M', humanOnly: true, risk: 'Low', volume24h: '$812K', token0: 'ETH', token1: 'SYBL' },
  { name: 'SYBL / USDC', apy: 24.7, tvl: '$1.8M', humanOnly: true, risk: 'Medium', volume24h: '$340K', token0: 'SYBL', token1: 'USDC' },
  { name: 'ETH / USDC', apy: 6.2, tvl: '$18.6M', humanOnly: false, risk: 'Low', volume24h: '$5.1M', token0: 'ETH', token1: 'USDC' },
  { name: 'SYBL / WBTC', apy: 41.2, tvl: '$620K', humanOnly: true, risk: 'High', volume24h: '$88K', token0: 'SYBL', token1: 'WBTC' },
];

const BORROW_MARKETS = [
  { asset: 'USDC', supplyApy: 4.8, borrowApy: 7.2, tvl: '$6.4M', utilization: 72, trustMultiplier: 3.5, symbol: '💵' },
  { asset: 'ETH', supplyApy: 2.1, borrowApy: 3.9, tvl: '1,204 ETH', utilization: 58, trustMultiplier: 2.8, symbol: '⟠' },
  { asset: 'WBTC', supplyApy: 1.4, borrowApy: 2.7, tvl: '48 BTC', utilization: 41, trustMultiplier: 2.0, symbol: '₿' },
];

const TRENDING = [
  { rank: 1, collection: 'Sybil Sentinel Genesis', floor: 0.48, change: 18.2, volume: '84 ETH', verified: true },
  { rank: 2, collection: 'ZK Proof Artifacts', floor: 1.25, change: 7.6, volume: '41 ETH', verified: true },
  { rank: 3, collection: 'Mempool Defenders', floor: 0.07, change: 4.1, volume: '12 ETH', verified: true },
  { rank: 4, collection: 'Network Topology Art', floor: 0.12, change: -2.3, volume: '9 ETH', verified: true },
  { rank: 5, collection: 'Slashed Archives', floor: 0.002, change: -88.0, volume: '0.1 ETH', verified: false },
];

const STATS = {
  totalVolume: '2,841 ETH',
  totalListings: 6,
  verifiedListings: 5,
  washTradesBlocked: 1847,
  humanTraders: 3219,
  activePools: 4,
  totalTVL: '$24.6M',
  sntPrice: '$0.0054',
  sntChange24h: 3.12,
};

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const section = searchParams.get('section') || 'all';
  switch (section) {
    case 'nfts':     return NextResponse.json({ nfts: NFT_LISTINGS });
    case 'swap':     return NextResponse.json({ pairs: SWAP_PAIRS });
    case 'pools':    return NextResponse.json({ pools: POOLS });
    case 'borrow':   return NextResponse.json({ markets: BORROW_MARKETS });
    case 'trending': return NextResponse.json({ trending: TRENDING });
    case 'stats':    return NextResponse.json({ stats: STATS });
    default:
      return NextResponse.json({ nfts: NFT_LISTINGS, pairs: SWAP_PAIRS, pools: POOLS, markets: BORROW_MARKETS, trending: TRENDING, stats: STATS });
  }
}
