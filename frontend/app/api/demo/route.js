import { NextResponse } from 'next/server';
import { ethers } from 'ethers';
import SybilMarketplaceABI from '../../../lib/SybilMarketplaceABI.json';
import SybilNetABI from '../../../lib/SybilNetABI.json';
import deployments from '../../../lib/deployments.json';

const HARDHAT_RPC = 'http://127.0.0.1:8545';

// ─── Custom error selectors (keccak256 of signature, first 4 bytes) ──────────
const CUSTOM_ERRORS = {
  '0x85718ab2': {
    title: 'Bot Detected — Access Denied',
    detail: 'The SybilNet oracle has flagged this address as a Sybil wallet. The smart contract reverted with NotVerifiedHuman().',
    type: 'NOT_HUMAN',
  },
  '0x646cf558': {
    title: 'Already Claimed',
    detail: 'This wallet has already claimed its airdrop. Each address can only claim once.',
    type: 'ALREADY_CLAIMED',
  },
  '0x80c490e2': {
    title: 'Credential Already Active',
    detail: 'This wallet already holds an active Humanity Credential. Proceed to Step 2 to claim the airdrop.',
    type: 'CREDENTIAL_ALREADY_ACTIVE',
  },
};

// Name → decoded error (for Hardhat message parsing fallback)
const ERROR_BY_NAME = {
  NotVerifiedHuman:       CUSTOM_ERRORS['0x85718ab2'],
  AlreadyClaimed:         CUSTOM_ERRORS['0x646cf558'],
  CredentialAlreadyActive: CUSTOM_ERRORS['0x80c490e2'],
  NoActiveCredential:     { title: 'No Active Credential', detail: 'This wallet has no active Humanity Credential.', type: 'NO_CREDENTIAL' },
  WalletBanned:           { title: 'Wallet Banned', detail: 'This wallet is temporarily banned by the SybilNet oracle.', type: 'BANNED' },
  InsufficientStake:      { title: 'Insufficient Stake', detail: 'The ETH value sent is below the required staking amount.', type: 'INSUFFICIENT_STAKE' },
};

function decodeRevertReason(error) {
  // 1. Try the raw 4-byte selector from the error data field
  const data =
    error?.info?.error?.data ||
    error?.data ||
    error?.error?.data;

  if (data && typeof data === 'string' && data.length >= 10) {
    const selector = data.slice(0, 10).toLowerCase();
    if (CUSTOM_ERRORS[selector]) return CUSTOM_ERRORS[selector];
  }

  const raw = error?.info?.error?.message || error?.message || 'Unknown error';

  // 2. Hardhat-specific format: "reverted with custom error 'ErrorName()'"
  const hardhatMatch = raw.match(/reverted with custom error '(\w+)\(\)'/i);
  if (hardhatMatch) {
    const name = hardhatMatch[1];
    if (ERROR_BY_NAME[name]) return ERROR_BY_NAME[name];
    return { title: `Reverted: ${name}`, detail: raw, type: 'REVERT' };
  }

  // 3. Name appears anywhere in the message
  for (const [name, decoded] of Object.entries(ERROR_BY_NAME)) {
    if (raw.includes(name)) return decoded;
  }

  // 4. Standard "execution reverted" with a string reason
  const match = raw.match(/execution reverted[:\s]*(.*)/i);
  if (match?.[1]) return { title: 'Transaction Reverted', detail: match[1].trim(), type: 'REVERT' };

  return { title: 'Transaction Failed', detail: raw, type: 'ERROR' };
}

// ─── GET /api/demo?action=STATUS&address=0x… ─────────────────────────────────
export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const address = searchParams.get('address');

    if (!address || !ethers.isAddress(address)) {
      return NextResponse.json({ error: 'Invalid address' }, { status: 400 });
    }

    const provider = new ethers.JsonRpcProvider(HARDHAT_RPC);
    const sybilNet    = new ethers.Contract(deployments.SybilNet,        SybilNetABI,         provider);
    const marketplace = new ethers.Contract(deployments.SybilMarketplace, SybilMarketplaceABI, provider);

    const [isHuman, hasClaimed, totalClaims] = await Promise.all([
      sybilNet.isVerifiedHuman(address),
      marketplace.hasClaimed(address),
      marketplace.totalClaims(),
    ]);

    return NextResponse.json({
      address,
      isHuman,
      hasClaimed,
      totalClaims: totalClaims.toString(),
    });
  } catch (err) {
    console.error('[Demo STATUS]', err.message);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

// ─── POST /api/demo ───────────────────────────────────────────────────────────
export async function POST(req) {
  let address;
  try {
    const body = await req.json();
    const { action } = body;
    address = body.address;

    if (!address || !action) {
      return NextResponse.json({ error: 'Missing parameters' }, { status: 400 });
    }
    if (!ethers.isAddress(address)) {
      return NextResponse.json({ error: 'Invalid Ethereum address' }, { status: 400 });
    }

    const provider = new ethers.JsonRpcProvider(HARDHAT_RPC);

    // ── Fund the impersonated account so it can always pay gas + value ────────
    // 10 ETH in hex (wei). Use lowercase address — Hardhat RPC methods require it.
    const addrLower = address.toLowerCase();
    const TEN_ETH_HEX = '0x8AC7230489E80000';
    await provider.send('hardhat_setBalance', [addrLower, TEN_ETH_HEX]);

    // ── Impersonate ───────────────────────────────────────────────────────────
    // NOTE: use JsonRpcSigner directly — provider.getSigner() validates against
    // eth_accounts which does NOT include impersonated addresses in ethers v6.
    await provider.send('hardhat_impersonateAccount', [addrLower]);
    const signer = new ethers.JsonRpcSigner(provider, address);

    let txHash = '';

    if (action === 'MINT') {
      const sybilNet = new ethers.Contract(deployments.SybilNet, SybilNetABI, signer);
      const tx = await sybilNet.mintCredential({ value: ethers.parseEther('0.01') });
      const receipt = await tx.wait();
      txHash = receipt.hash;

    } else if (action === 'CLAIM') {
      const marketplace = new ethers.Contract(deployments.SybilMarketplace, SybilMarketplaceABI, signer);
      const tx = await marketplace.claimExclusiveAirdrop();
      const receipt = await tx.wait();
      txHash = receipt.hash;

    } else {
      return NextResponse.json({ error: `Unknown action: ${action}` }, { status: 400 });
    }

    // ── Stop impersonating ────────────────────────────────────────────────────
    await provider.send('hardhat_stopImpersonatingAccount', [addrLower]);

    // ── Read updated state ────────────────────────────────────────────────────
    const sybilNet    = new ethers.Contract(deployments.SybilNet,        SybilNetABI,         provider);
    const marketplace = new ethers.Contract(deployments.SybilMarketplace, SybilMarketplaceABI, provider);
    const [isHuman, hasClaimed, totalClaims] = await Promise.all([
      sybilNet.isVerifiedHuman(address),
      marketplace.hasClaimed(address),
      marketplace.totalClaims(),
    ]);

    return NextResponse.json({
      success: true,
      hash: txHash,
      state: {
        isHuman,
        hasClaimed,
        totalClaims: totalClaims.toString(),
      },
    });

  } catch (error) {
    // Always stop impersonating even on failure
    try {
      if (address) {
        const provider = new ethers.JsonRpcProvider(HARDHAT_RPC);
        await provider.send('hardhat_stopImpersonatingAccount', [address.toLowerCase()]);
      }
    } catch (_) { /* best-effort */ }

    console.error('[Demo API Error]', error);
    const decoded = decodeRevertReason(error);
    return NextResponse.json({ error: decoded }, { status: 500 });
  }
}
