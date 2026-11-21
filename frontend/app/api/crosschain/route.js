import { NextResponse } from "next/server";
import { readFileSync, existsSync } from "fs";
import { join } from "path";

/**
 * GET /api/crosschain
 *
 * Returns cross-chain analytics from features_multichain.csv.
 * Supports optional ?wallet=0x... query for per-wallet lookup.
 *
 * Response shape:
 *   {
 *     chains: [{ chainId, name, walletCount, sybilCount, humanCount }],
 *     crossChainWallets: number,
 *     bridgeTransactions: number,
 *     totalWallets: number,
 *     wallet?: { address, chains, scores, bridgeActivity }  // if ?wallet= provided
 *   }
 */

const DATA_DIR = join(process.cwd(), "..", "data", "processed");
const FEATURES_PATH = join(DATA_DIR, "features_multichain.csv");
const SCORES_PATH = join(DATA_DIR, "node_scores_multichain.csv");

const CHAIN_NAMES = {
  1: "Ethereum",
  137: "Polygon",
  42161: "Arbitrum",
  8453: "Base",
};

function parseCSV(content) {
  const lines = content.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    const obj = {};
    headers.forEach((h, i) => {
      obj[h.trim()] = values[i]?.trim() ?? "";
    });
    return obj;
  });
}

export async function GET(request) {
  try {
    // Check if multichain data exists
    if (!existsSync(FEATURES_PATH)) {
      return NextResponse.json(
        {
          chains: Object.entries(CHAIN_NAMES).map(([id, name]) => ({
            chainId: Number(id),
            name,
            walletCount: 0,
            sybilCount: 0,
            humanCount: 0,
          })),
          crossChainWallets: 0,
          bridgeTransactions: 0,
          totalWallets: 0,
          message: "No multichain data yet. Run: python main.py --multichain",
        },
        { status: 200 }
      );
    }

    const featuresRaw = readFileSync(FEATURES_PATH, "utf-8");
    const features = parseCSV(featuresRaw);

    // Load scores if available
    let scores = [];
    if (existsSync(SCORES_PATH)) {
      scores = parseCSV(readFileSync(SCORES_PATH, "utf-8"));
    }
    const scoreMap = {};
    scores.forEach((s) => {
      scoreMap[s.node_id] = {
        sybilProbability: parseFloat(s.sybil_probability || "0"),
        classification: s.classification || "Unknown",
      };
    });

    // Compute per-chain stats
    const crossChainWallets = features.filter(
      (f) => parseInt(f.num_chains_active || "1") > 1
    ).length;

    const totalBridgeTx = features.reduce(
      (sum, f) => sum + parseInt(f.bridge_tx_count || "0"),
      0
    );

    // Chain stats (approximate from num_chains_active)
    const chainStats = Object.entries(CHAIN_NAMES).map(([id, name]) => ({
      chainId: Number(id),
      name,
      walletCount: features.length, // all wallets potentially span all chains
      sybilCount: scores.filter((s) => s.classification === "Sybil").length,
      humanCount: scores.filter((s) => s.classification === "Human").length,
    }));

    // Handle per-wallet query
    const { searchParams } = new URL(request.url);
    const walletQuery = searchParams.get("wallet");
    let walletData = null;

    if (walletQuery) {
      const walletLower = walletQuery.toLowerCase();
      const feat = features.find(
        (f) => f.node_id?.toLowerCase() === walletLower
      );

      if (feat) {
        walletData = {
          address: feat.node_id,
          numChainsActive: parseInt(feat.num_chains_active || "1"),
          bridgeTxCount: parseInt(feat.bridge_tx_count || "0"),
          bridgeTxRatio: parseFloat(feat.bridge_tx_ratio || "0"),
          crossChainDegree: parseInt(feat.cross_chain_degree || "0"),
          bridgeHopCount: parseInt(feat.bridge_hop_count || "0"),
          inDegree: parseInt(feat.in_degree || "0"),
          outDegree: parseInt(feat.out_degree || "0"),
          pagerank: parseFloat(feat.pagerank || "0"),
          ...scoreMap[feat.node_id],
        };
      }
    }

    return NextResponse.json({
      chains: chainStats,
      crossChainWallets,
      bridgeTransactions: totalBridgeTx,
      totalWallets: features.length,
      ...(walletData ? { wallet: walletData } : {}),
    });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to load cross-chain data", details: error.message },
      { status: 500 }
    );
  }
}
