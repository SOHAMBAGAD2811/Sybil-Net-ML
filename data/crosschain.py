"""
data/crosschain.py
─────────────────────────────────────────────────────────────────────────────
Week 7 — Multi-Chain Data Ingestion

Extends the Week-1 single-chain ingestion to fetch and unify transaction
data from Ethereum, Polygon, Arbitrum, and Base.  Falls back to a synthetic
multi-chain Sybil generator when no API key is available.
─────────────────────────────────────────────────────────────────────────────
"""

import os
import csv
import random
import time
import uuid
import sys

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import (
    ALCHEMY_API_KEY, CHAINS, BRIDGE_CONTRACTS, BRIDGE_ADDRESSES,
    RAW_MULTICHAIN_PATH, RAW_MULTICHAIN_LABELS_PATH,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Alchemy multi-chain fetcher
# ─────────────────────────────────────────────────────────────────────────────

# Seed addresses per chain (high-activity wallets to crawl)
SEED_ADDRESSES_BY_CHAIN = {
    "ethereum": [
        "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # vitalik.eth
        "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",  # Binance cold
    ],
    "polygon": [
        "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # WMATIC
        "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC.e on Polygon
    ],
    "arbitrum": [
        "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH on Arbitrum
        "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",  # USDT on Arbitrum
    ],
    "base": [
        "0x4200000000000000000000000000000000000006",  # WETH on Base
        "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
    ],
}


def _validate_key(api_key: str) -> bool:
    return bool(api_key and api_key.strip() and api_key != "your_alchemy_api_key_here")


def fetch_multichain_data(
    api_key: str = "",
    target_per_chain: int = 12_500,
):
    """
    Fetch transactions from all configured chains using Alchemy.
    Falls back to synthetic multi-chain data if the key is invalid.
    """
    api_key = api_key or ALCHEMY_API_KEY

    if not _validate_key(api_key):
        print(
            "[Multichain] No ALCHEMY_API_KEY set → generating synthetic multi-chain data.\n"
            "  → Get a FREE key at https://dashboard.alchemy.com/"
        )
        generate_multichain_synthetic_data(target_per_chain * len(CHAINS))
        return

    all_transactions = []

    for chain_name, chain_cfg in CHAINS.items():
        subdomain = chain_cfg["alchemy_subdomain"]
        chain_id  = chain_cfg["chain_id"]
        url = f"https://{subdomain}.g.alchemy.com/v2/{api_key}"
        headers = {"Content-Type": "application/json"}

        # Verify connectivity
        try:
            r = requests.post(
                url,
                json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
                headers=headers, timeout=15,
            )
            r.raise_for_status()
            resp = r.json()
            if "error" in resp:
                print(f"[Multichain] {chain_name}: API error — {resp['error'].get('message')}. Skipping.")
                continue
            latest = int(resp["result"], 16)
            print(f"[Multichain] {chain_name}: connected ✓  Latest block: {latest:,}")
        except Exception as e:
            print(f"[Multichain] {chain_name}: connection failed ({e}). Skipping.")
            continue

        seeds = SEED_ADDRESSES_BY_CHAIN.get(chain_name, [])
        chain_txs = []

        for seed in seeds:
            if len(chain_txs) >= target_per_chain:
                break
            page_key = None
            for page in range(20):
                if len(chain_txs) >= target_per_chain:
                    break
                payload = {
                    "jsonrpc": "2.0", "id": 1,
                    "method": "alchemy_getAssetTransfers",
                    "params": [{
                        "fromBlock": "0x0", "toBlock": "latest",
                        "fromAddress": seed, "category": ["external"],
                        "withMetadata": True, "excludeZeroValue": True,
                        "maxCount": "0x3E8",
                    }],
                }
                if page_key:
                    payload["params"][0]["pageKey"] = page_key
                try:
                    r = requests.post(url, json=payload, headers=headers, timeout=20)
                    r.raise_for_status()
                    resp = r.json()
                except Exception:
                    break
                if "error" in resp:
                    break
                result = resp.get("result", {})
                transfers = result.get("transfers", [])
                if not transfers:
                    break

                for tx in transfers:
                    raw_value = tx.get("value", 0) or 0
                    to_addr = tx.get("to", "")
                    from_addr = tx.get("from", "")
                    is_bridge = (
                        to_addr in BRIDGE_ADDRESSES or
                        from_addr in BRIDGE_ADDRESSES
                    )
                    chain_txs.append({
                        "hash": tx.get("hash", ""),
                        "blockNumber": int(tx.get("blockNum", "0x0"), 16),
                        "timeStamp": tx.get("metadata", {}).get("blockTimestamp", ""),
                        "from": from_addr,
                        "to": to_addr,
                        "value": str(int(float(raw_value) * 10**18)),
                        "gas": "21000",
                        "gasPrice": "0",
                        "chain_id": chain_id,
                        "is_bridge_tx": is_bridge,
                    })
                page_key = result.get("pageKey")
                if not page_key:
                    break

        print(f"[Multichain] {chain_name}: {len(chain_txs):,} transactions fetched.")
        all_transactions.extend(chain_txs)

    if not all_transactions:
        print("[Multichain] No transactions from any chain. Falling back to synthetic data.")
        generate_multichain_synthetic_data(target_per_chain * len(CHAINS))
        return

    print(f"[Multichain] Total: {len(all_transactions):,} transactions across {len(CHAINS)} chains.")
    _save_multichain_csv(all_transactions)


def _save_multichain_csv(transactions: list):
    """Write multichain transactions to CSV."""
    os.makedirs(os.path.dirname(RAW_MULTICHAIN_PATH), exist_ok=True)
    fieldnames = [
        "hash", "blockNumber", "timeStamp", "from", "to",
        "value", "gas", "gasPrice", "chain_id", "is_bridge_tx",
    ]
    with open(RAW_MULTICHAIN_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(transactions)
    print(f"[Multichain] Saved {len(transactions):,} rows → {RAW_MULTICHAIN_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
#  Synthetic multi-chain Sybil data generator
# ─────────────────────────────────────────────────────────────────────────────

def _addr(prefix: str = "") -> str:
    return f"0x{prefix}{uuid.uuid4().hex[:40 - len(prefix)]}"


def generate_multichain_synthetic_data(num_transactions: int = 50_000):
    """
    Generate synthetic multi-chain blockchain data with cross-chain Sybil
    patterns including bridge hops, cross-chain wash rings, and multi-chain
    bot farms.

    Pattern breakdown:
        25 % — Cross-chain bot farms  (controller on ETH, workers spread across L2s)
        20 % — Cross-chain wash rings (circular trades hopping between chains)
        15 % — Bridge hop laundering  (funds routed through bridge contracts)
        40 % — Honest multi-chain users (organic activity across 1-3 chains)
    """
    print(f"[Synthetic-MC] Generating {num_transactions:,} multi-chain transactions…")

    random.seed(42)
    now = int(time.time())
    chain_ids = [cfg["chain_id"] for cfg in CHAINS.values()]
    transactions = []

    # Bridge contract addresses (synthetic stand-ins)
    bridge_addrs = [_addr("bb") for _ in range(3)]

    # ── Cross-chain bot farms (25%) ──────────────────────────────────────────
    NUM_FARMS = 12
    bot_farms = []
    for _ in range(NUM_FARMS):
        controller = _addr("b0")
        # Workers spread across different chains
        workers = []
        for chain_id in chain_ids:
            n_workers = random.randint(5, 20)
            workers.extend(
                {"addr": _addr("b1"), "chain_id": chain_id}
                for _ in range(n_workers)
            )
        bot_farms.append({"controller": controller, "workers": workers})

    # ── Cross-chain wash rings (20%) ─────────────────────────────────────────
    NUM_RINGS = 20
    wash_rings = []
    for _ in range(NUM_RINGS):
        ring_size = random.randint(3, 6)
        # Ring members on different chains
        ring = [
            {"addr": _addr("cc"), "chain_id": random.choice(chain_ids)}
            for _ in range(ring_size)
        ]
        wash_rings.append(ring)

    # ── Honest multi-chain users ─────────────────────────────────────────────
    honest_pool = []
    for _ in range(2_000):
        addr = _addr("aa")
        active_chains = random.sample(chain_ids, k=random.randint(1, 3))
        honest_pool.append({"addr": addr, "chains": active_chains})

    def _tx(frm, to, chain_id, is_bridge=False, value_wei=None):
        return {
            "hash": f"0x{uuid.uuid4().hex}",
            "blockNumber": random.randint(18_000_000, 22_000_000),
            "timeStamp": now - random.randint(0, 31_536_000),
            "from": frm,
            "to": to,
            "value": str(value_wei or random.randint(10**15, 5 * 10**18)),
            "gas": str(random.randint(21_000, 150_000)),
            "gasPrice": str(random.randint(10**9, 5 * 10**10)),
            "chain_id": chain_id,
            "is_bridge_tx": is_bridge,
        }

    # ── 1. Cross-chain bot farms (25%) ───────────────────────────────────────
    farm_target = int(num_transactions * 0.25)
    while len(transactions) < farm_target:
        farm = random.choice(bot_farms)
        ctrl = farm["controller"]
        worker = random.choice(farm["workers"])
        chain_id = worker["chain_id"]

        # Controller → worker (funding)
        transactions.append(_tx(ctrl, worker["addr"], chain_id,
                                value_wei=random.randint(10**16, 10**17)))
        # Worker → controller (collection)
        transactions.append(_tx(worker["addr"], ctrl, chain_id,
                                value_wei=random.randint(10**14, 10**15)))

        # Cross-chain hop via bridge
        if random.random() < 0.3:
            bridge = random.choice(bridge_addrs)
            other_chain = random.choice([c for c in chain_ids if c != chain_id])
            transactions.append(_tx(worker["addr"], bridge, chain_id, is_bridge=True))
            transactions.append(_tx(bridge, ctrl, other_chain, is_bridge=True))

    # ── 2. Cross-chain wash rings (20%) ──────────────────────────────────────
    ring_target = int(num_transactions * 0.20) + len(transactions)
    while len(transactions) < ring_target:
        ring = random.choice(wash_rings)
        amount = random.randint(10**17, 10**18)
        for i in range(len(ring)):
            frm = ring[i]
            to = ring[(i + 1) % len(ring)]

            if frm["chain_id"] != to["chain_id"]:
                # Cross-chain hop through bridge
                bridge = random.choice(bridge_addrs)
                transactions.append(_tx(frm["addr"], bridge, frm["chain_id"],
                                        is_bridge=True, value_wei=amount))
                transactions.append(_tx(bridge, to["addr"], to["chain_id"],
                                        is_bridge=True, value_wei=int(amount * 0.99)))
            else:
                transactions.append(_tx(frm["addr"], to["addr"], frm["chain_id"],
                                        value_wei=amount))
            amount = int(amount * random.uniform(0.97, 1.02))

    # ── 3. Bridge hop laundering (15%) ───────────────────────────────────────
    launder_target = int(num_transactions * 0.15) + len(transactions)
    launder_wallets = [_addr("dd") for _ in range(100)]
    while len(transactions) < launder_target:
        wallet = random.choice(launder_wallets)
        bridge = random.choice(bridge_addrs)
        src_chain = random.choice(chain_ids)
        dst_chain = random.choice([c for c in chain_ids if c != src_chain])
        amount = random.randint(10**17, 5 * 10**18)

        transactions.append(_tx(wallet, bridge, src_chain, is_bridge=True, value_wei=amount))
        transactions.append(_tx(bridge, wallet, dst_chain, is_bridge=True,
                                value_wei=int(amount * 0.995)))

    # ── 4. Honest multi-chain users (fill remainder) ─────────────────────────
    while len(transactions) < num_transactions:
        user1 = random.choice(honest_pool)
        user2 = random.choice(honest_pool)
        while user2["addr"] == user1["addr"]:
            user2 = random.choice(honest_pool)
        # Pick a chain both are on, or any if no overlap
        shared = list(set(user1["chains"]) & set(user2["chains"]))
        chain_id = random.choice(shared) if shared else random.choice(user1["chains"])
        transactions.append(_tx(user1["addr"], user2["addr"], chain_id))

    random.shuffle(transactions)
    transactions = transactions[:num_transactions]

    # ── Build ground-truth labels ────────────────────────────────────────────
    bot_addrs = (
        {f["controller"] for f in bot_farms} |
        {w["addr"] for f in bot_farms for w in f["workers"]}
    )
    ring_addrs = {m["addr"] for r in wash_rings for m in r}
    launder_addrs = set(launder_wallets)
    bridge_addrs_set = set(bridge_addrs)
    all_sybil = bot_addrs | ring_addrs | launder_addrs | bridge_addrs_set

    print(f"[Synthetic-MC] Pattern summary:")
    print(f"  Bot farm addresses    : {len(bot_addrs):,}  ({NUM_FARMS} farms)")
    print(f"  Wash-ring addresses   : {len(ring_addrs):,}  ({NUM_RINGS} rings)")
    print(f"  Laundering addresses  : {len(launder_addrs):,}")
    print(f"  Bridge addresses      : {len(bridge_addrs_set):,}")
    print(f"  Honest addresses      : {len(honest_pool):,}")
    print(f"  Total Sybil wallets   : {len(all_sybil):,}")

    _save_multichain_csv(transactions)

    # ── Save ground-truth labels ─────────────────────────────────────────────
    all_addrs = set()
    for tx in transactions:
        all_addrs.add(tx["from"])
        all_addrs.add(tx["to"])

    os.makedirs(os.path.dirname(RAW_MULTICHAIN_LABELS_PATH), exist_ok=True)
    with open(RAW_MULTICHAIN_LABELS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["address", "is_sybil"])
        writer.writeheader()
        for addr in all_addrs:
            writer.writerow({"address": addr, "is_sybil": 1 if addr in all_sybil else 0})

    n_sybil = sum(1 for a in all_addrs if a in all_sybil)
    print(f"[Synthetic-MC] Labels saved → {RAW_MULTICHAIN_LABELS_PATH}")
    print(f"               Sybil={n_sybil:,}  Human={len(all_addrs) - n_sybil:,}")


if __name__ == "__main__":
    fetch_multichain_data()
