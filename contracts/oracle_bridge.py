"""
contracts/oracle_bridge.py
─────────────────────────────────────────────────────────────────────────────
GNN → Smart Contract Oracle Bridge
─────────────────────────────────────────────────────────────────────────────

This script reads the GNN output (node_scores.csv) and submits Sybil
detections to the deployed SybilNet smart contract via the oracle role.

Usage (against a local Hardhat node):
    1.  In one terminal: cd contracts && npx hardhat node
    2.  In another:      cd contracts && npx hardhat run scripts/deploy.js --network localhost
    3.  Set SYBILNET_ADDRESS in ../.env
    4.  python oracle_bridge.py

Requirements:
    pip install web3 python-dotenv
"""

import os
import sys
import json
import time
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

# ── Try to import web3 ───────────────────────────────────────────────────────
try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware
except ImportError:
    print("[Oracle] web3 not installed. Run: pip install web3")
    sys.exit(1)

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ─────────────────────────────────────────────────────────────────────────────
#  Config — read from environment
# ─────────────────────────────────────────────────────────────────────────────

RPC_URL          = os.getenv("RPC_URL",          "http://127.0.0.1:8545")   # local Hardhat
CONTRACT_ADDRESS = os.getenv("SYBILNET_ADDRESS", "")
ORACLE_PRIVKEY   = os.getenv("ORACLE_PRIVATE_KEY", "")

# Sybil score thresholds
SLASH_THRESHOLD  = int(os.getenv("SLASH_THRESHOLD",  "85"))   # GNN prob > 85% → slash
WARN_THRESHOLD   = int(os.getenv("WARN_THRESHOLD",   "60"))   # 60–85% → score update only

SCORES_PATH = Path(__file__).parent.parent / "data" / "processed" / "node_scores.csv"
ABI_PATH    = Path(__file__).parent / "artifacts" / "contracts" / "SybilNet.sol" / "SybilNet.json"


def load_abi() -> list:
    if not ABI_PATH.exists():
        print(f"[Oracle] ABI not found at {ABI_PATH}")
        print("         Run: cd contracts && npx hardhat compile")
        sys.exit(1)
    with open(ABI_PATH) as f:
        return json.load(f)["abi"]


def load_scores() -> pd.DataFrame:
    if not SCORES_PATH.exists():
        print(f"[Oracle] node_scores.csv not found at {SCORES_PATH}")
        print("         Run the GNN pipeline first: python models/gnn.py")
        sys.exit(1)
    df = pd.read_csv(SCORES_PATH)
    print(f"[Oracle] Loaded {len(df):,} wallet scores from {SCORES_PATH}")
    return df


def run_oracle():
    print("=== Sybil-Net Oracle Bridge ===\n")

    # ── Validate env ─────────────────────────────────────────────────────────
    if not CONTRACT_ADDRESS:
        print("[Oracle] SYBILNET_ADDRESS not set in .env")
        print("         Deploy first: cd contracts && npx hardhat run scripts/deploy.js --network localhost")
        sys.exit(1)
    if not ORACLE_PRIVKEY:
        print("[Oracle] ORACLE_PRIVATE_KEY not set in .env")
        sys.exit(1)

    # ── Connect to node ───────────────────────────────────────────────────────
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        print(f"[Oracle] Cannot connect to RPC at {RPC_URL}")
        sys.exit(1)

    print(f"[Oracle] Connected to {RPC_URL}  (chain {w3.eth.chain_id})")

    oracle_account = w3.eth.account.from_key(ORACLE_PRIVKEY)
    oracle_address = oracle_account.address
    print(f"[Oracle] Oracle wallet: {oracle_address}")
    print(f"[Oracle] Balance:       {w3.from_wei(w3.eth.get_balance(oracle_address), 'ether'):.4f} ETH\n")

    # ── Load contract ─────────────────────────────────────────────────────────
    abi      = load_abi()
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=abi,
    )
    print(f"[Oracle] Contract:    {CONTRACT_ADDRESS}")
    print(f"[Oracle] Min stake:   {w3.from_wei(contract.functions.minStake().call(), 'ether')} ETH")
    print(f"[Oracle] Total staked: {w3.from_wei(contract.functions.totalStaked().call(), 'ether')} ETH\n")

    # ── Load GNN scores ───────────────────────────────────────────────────────
    df = load_scores()

    # Convert sybil_probability (0–1) to contract score (0–100)
    df["contract_score"] = (df["sybil_probability"] * 100).round().astype(int).clip(0, 100)

    # Only process wallets that have a credential on-chain
    # (In production: filter by checking isVerifiedHuman() for each wallet)
    slash_candidates = df[df["contract_score"] >= SLASH_THRESHOLD]
    warn_candidates  = df[(df["contract_score"] >= WARN_THRESHOLD) &
                          (df["contract_score"] <  SLASH_THRESHOLD)]

    print(f"[Oracle] Slash candidates (score >= {SLASH_THRESHOLD}): {len(slash_candidates):,}")
    print(f"[Oracle] Warn candidates  (score >= {WARN_THRESHOLD}):  {len(warn_candidates):,}\n")

    # ── Submit score updates ──────────────────────────────────────────────────
    nonce = w3.eth.get_transaction_count(oracle_address)
    submitted = 0

    for _, row in warn_candidates.iterrows():
        wallet = row["node_id"]
        score  = int(row["contract_score"])

        # Skip if not a valid Ethereum address (synthetic data uses non-checksummed addrs)
        try:
            checksummed = Web3.to_checksum_address(wallet)
        except Exception:
            continue

        # Check if wallet has an active credential on-chain
        try:
            if not contract.functions.isVerifiedHuman(checksummed).call():
                continue
        except Exception:
            continue

        try:
            tx = contract.functions.updateSybilScore(checksummed, score).build_transaction({
                "from":     oracle_address,
                "nonce":    nonce,
                "gas":      100_000,
                "gasPrice": w3.eth.gas_price,
            })
            signed = oracle_account.sign_transaction(tx)
            w3.eth.send_raw_transaction(signed.raw_transaction)
            nonce    += 1
            submitted += 1
            print(f"  ⚠️  Score update  {checksummed[:16]}…  score={score}")
        except Exception as e:
            print(f"  Error updating score for {wallet[:16]}: {e}")

    # ── Submit slashes ────────────────────────────────────────────────────────
    slashed = 0
    for _, row in slash_candidates.iterrows():
        wallet = row["node_id"]
        try:
            checksummed = Web3.to_checksum_address(wallet)
        except Exception:
            continue

        try:
            if not contract.functions.isVerifiedHuman(checksummed).call():
                continue
        except Exception:
            continue

        try:
            tx = contract.functions.slash(checksummed, oracle_address).build_transaction({
                "from":     oracle_address,
                "nonce":    nonce,
                "gas":      150_000,
                "gasPrice": w3.eth.gas_price,
            })
            signed = oracle_account.sign_transaction(tx)
            w3.eth.send_raw_transaction(signed.raw_transaction)
            nonce   += 1
            slashed += 1
            print(f"  🚨 Slashed        {checksummed[:16]}…  score={row['contract_score']}")
        except Exception as e:
            print(f"  Error slashing {wallet[:16]}: {e}")

    print(f"\n[Oracle] Done.  Score updates={submitted}  Slashes={slashed}")
    print(f"[Oracle] Total slashed on-chain: "
          f"{w3.from_wei(contract.functions.totalSlashed().call(), 'ether')} ETH")


if __name__ == "__main__":
    run_oracle()
