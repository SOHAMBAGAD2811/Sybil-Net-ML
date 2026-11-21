import { NextResponse } from "next/server";
import { readFileSync, existsSync } from "fs";
import { join } from "path";

/**
 * GET /api/governance
 *
 * Returns governance proposal data for the dashboard.
 * Uses realistic mock data seeded from actual wallet addresses
 * in node_scores.csv for demo purposes.
 *
 * Response shape:
 *   {
 *     stats:          { total, active, executed, participationRate },
 *     proposals:      [ ... ],
 *     recentActivity: [ ... ],
 *   }
 */

const DATA_DIR = join(process.cwd(), "..", "data", "processed");
const SCORES_PATH = join(DATA_DIR, "node_scores.csv");

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

function getWalletAddresses() {
  if (!existsSync(SCORES_PATH)) return [];
  try {
    const raw = readFileSync(SCORES_PATH, "utf-8");
    const rows = parseCSV(raw);
    return rows.map((r) => r.node_id).filter(Boolean);
  } catch {
    return [];
  }
}

export async function GET() {
  try {
    const wallets = getWalletAddresses();

    // Use real wallet addresses from the dataset for realism
    const pick = (idx) =>
      wallets.length > idx ? wallets[idx] : `0x${idx.toString(16).padStart(40, "a")}`;

    const now = Math.floor(Date.now() / 1000);
    const DAY = 86400;

    // Generate mock proposals with realistic data
    const proposals = [
      {
        id: 0,
        type: "SLASH_APPEAL",
        description: `Appeal slash for wallet ${pick(42).slice(0, 12)}… — falsely flagged by GNN model during wash-ring sweep`,
        proposer: pick(10),
        votesFor: 18,
        votesAgainst: 4,
        votesAbstain: 2,
        status: "Active",
        startTime: now - DAY * 1,
        endTime: now + DAY * 2,
        quorumRequired: 30,
      },
      {
        id: 1,
        type: "PARAMETER_CHANGE",
        description: "Increase minimum stake from 0.01 ETH to 0.02 ETH to deter low-cost Sybil attacks",
        proposer: pick(25),
        votesFor: 32,
        votesAgainst: 8,
        votesAbstain: 5,
        status: "Succeeded",
        startTime: now - DAY * 5,
        endTime: now - DAY * 2,
        quorumRequired: 30,
      },
      {
        id: 2,
        type: "SLASH_APPEAL",
        description: `Appeal: wallet ${pick(88).slice(0, 12)}… was a legitimate market maker, not a wash trader`,
        proposer: pick(88),
        votesFor: 5,
        votesAgainst: 22,
        votesAbstain: 3,
        status: "Defeated",
        startTime: now - DAY * 8,
        endTime: now - DAY * 5,
        quorumRequired: 30,
      },
      {
        id: 3,
        type: "ROLE_CHANGE",
        description: "Grant ORACLE_ROLE to new GNN inference service address after backend migration",
        proposer: pick(5),
        votesFor: 28,
        votesAgainst: 2,
        votesAbstain: 1,
        status: "Executed",
        startTime: now - DAY * 12,
        endTime: now - DAY * 9,
        quorumRequired: 30,
      },
      {
        id: 4,
        type: "PARAMETER_CHANGE",
        description: "Reduce slash reporter fee from 10% to 5% to decrease bounty hunting incentives",
        proposer: pick(33),
        votesFor: 15,
        votesAgainst: 14,
        votesAbstain: 6,
        status: "Executed",
        startTime: now - DAY * 18,
        endTime: now - DAY * 15,
        quorumRequired: 30,
      },
      {
        id: 5,
        type: "SLASH_APPEAL",
        description: `Emergency appeal for ${pick(200).slice(0, 12)}… — bridge transaction flagged as cross-chain laundering`,
        proposer: pick(200),
        votesFor: 12,
        votesAgainst: 3,
        votesAbstain: 1,
        status: "Active",
        startTime: now - DAY * 0.5,
        endTime: now + DAY * 2.5,
        quorumRequired: 30,
      },
      {
        id: 6,
        type: "PARAMETER_CHANGE",
        description: "Increase voting period from 3 days to 5 days for more community participation",
        proposer: pick(15),
        votesFor: 20,
        votesAgainst: 18,
        votesAbstain: 7,
        status: "Defeated",
        startTime: now - DAY * 22,
        endTime: now - DAY * 19,
        quorumRequired: 30,
      },
      {
        id: 7,
        type: "SLASH_APPEAL",
        description: `Appeal for ${pick(150).slice(0, 12)}… — high-frequency DeFi user incorrectly clustered with bot farm`,
        proposer: pick(150),
        votesFor: 8,
        votesAgainst: 1,
        votesAbstain: 0,
        status: "Active",
        startTime: now - DAY * 0.2,
        endTime: now + DAY * 2.8,
        quorumRequired: 30,
      },
      {
        id: 8,
        type: "ROLE_CHANGE",
        description: "Revoke GUARDIAN_ROLE from deprecated multisig after key rotation",
        proposer: pick(3),
        votesFor: 35,
        votesAgainst: 0,
        votesAbstain: 2,
        status: "Executed",
        startTime: now - DAY * 30,
        endTime: now - DAY * 27,
        quorumRequired: 30,
      },
      {
        id: 9,
        type: "SLASH_APPEAL",
        description: `Appeal for wallet ${pick(300).slice(0, 12)}… — NFT collector falsely linked to wash-trading ring`,
        proposer: pick(300),
        votesFor: 25,
        votesAgainst: 10,
        votesAbstain: 4,
        status: "Executed",
        startTime: now - DAY * 25,
        endTime: now - DAY * 22,
        quorumRequired: 30,
      },
    ];

    // Compute stats
    const active = proposals.filter((p) => p.status === "Active").length;
    const executed = proposals.filter((p) => p.status === "Executed").length;
    const totalVotesCast = proposals.reduce(
      (sum, p) => sum + p.votesFor + p.votesAgainst + p.votesAbstain,
      0
    );
    const maxPossibleVotes = proposals.length * 30; // 30 potential voters
    const participationRate = maxPossibleVotes > 0
      ? Math.min(totalVotesCast / maxPossibleVotes, 1)
      : 0;

    const stats = {
      total: proposals.length,
      active,
      executed,
      participationRate: Math.round(participationRate * 100) / 100,
    };

    // Recent activity (mock events using real timestamps)
    const recentActivity = [
      { type: "vote", proposalId: 0, voter: pick(44), vote: "FOR", timestamp: now - 1200 },
      { type: "vote", proposalId: 5, voter: pick(55), vote: "FOR", timestamp: now - 2400 },
      { type: "created", proposalId: 7, proposer: pick(150), timestamp: now - 3600 * 5 },
      { type: "vote", proposalId: 0, voter: pick(60), vote: "AGAINST", timestamp: now - 3600 * 8 },
      { type: "vote", proposalId: 7, voter: pick(12), vote: "FOR", timestamp: now - 3600 * 10 },
      { type: "created", proposalId: 5, proposer: pick(200), timestamp: now - 3600 * 12 },
      { type: "executed", proposalId: 4, timestamp: now - DAY * 14 },
      { type: "vote", proposalId: 5, voter: pick(77), vote: "ABSTAIN", timestamp: now - 3600 * 16 },
      { type: "executed", proposalId: 3, timestamp: now - DAY * 8 },
      { type: "created", proposalId: 0, proposer: pick(10), timestamp: now - DAY * 1 },
    ];

    return NextResponse.json({ stats, proposals, recentActivity });
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to load governance data", details: error.message },
      { status: 500 }
    );
  }
}
