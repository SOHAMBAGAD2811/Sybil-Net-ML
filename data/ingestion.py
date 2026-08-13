import os
import csv
import random
import time
import requests
import uuid
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ALCHEMY_API_KEY, API_KEY, RAW_DATA_PATH

# ─────────────────────────────────────────────────────────────────────────────
#  Alchemy provider
#  Docs: https://docs.alchemy.com/reference/alchemy-gettransactions
#  Free tier: 300M CUs / month
# ─────────────────────────────────────────────────────────────────────────────

# Well-known high-activity Ethereum addresses to crawl for a richer dataset
SEED_ADDRESSES = [
    "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",  # vitalik.eth
    "0x00000000219ab540356cBB839Cbe05303d7705Fa",  # ETH2 deposit contract
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH contract
    "0xBE0eB53F46cd790Cd13851d5EFf43D12404d33E8",  # Binance cold wallet
    "0x28C6c06298d514Db089934071355E5743bf21d60",  # Binance hot wallet 14
]


def _validate_alchemy_key(api_key: str) -> bool:
    """Reject only completely blank keys — let the live API decide the rest."""
    return bool(api_key and api_key.strip() and api_key != "your_alchemy_api_key_here")


def fetch_from_alchemy(api_key: str, target_transactions: int = 50_000):
    """
    Fetch transactions from multiple seed addresses using Alchemy's
    alchemy_getAssetTransfers JSON-RPC endpoint.
    Paginates until target_transactions is reached or all pages exhausted.
    Falls back to synthetic data on any fatal error.
    """
    if not _validate_alchemy_key(api_key):
        print(
            "[Alchemy] No API key set in .env (ALCHEMY_API_KEY is blank or placeholder).\n"
            "  → Get a FREE key at https://dashboard.alchemy.com/\n"
            "  → Paste it as ALCHEMY_API_KEY=<your_key> in your .env file.\n"
            "  → Falling back to synthetic Sybil data generator."
        )
        generate_sybil_synthetic_data(target_transactions)
        return

    print(f"[Alchemy] Key loaded ({len(api_key)} chars). Verifying with live API…")

    url = f"https://eth-mainnet.g.alchemy.com/v2/{api_key}"
    headers = {"Content-Type": "application/json"}

    # ── 1. Verify the key is live ────────────────────────────────────────────
    try:
        r = requests.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        resp_json = r.json()

        if "error" in resp_json:
            err = resp_json["error"]
            print(
                f"[Alchemy] API key rejected by server: {err.get('message', err)}\n"
                "  → Your key may be expired, over-quota, or copied incorrectly.\n"
                "  → Regenerate it at https://dashboard.alchemy.com/\n"
                "  → Falling back to synthetic Sybil data generator."
            )
            generate_sybil_synthetic_data(target_transactions)
            return

        latest_block = int(resp_json["result"], 16)
        print(f"[Alchemy] Connected ✓  Latest block: {latest_block:,}")

    except requests.exceptions.ConnectionError:
        print("[Alchemy] Network error — no internet connection?  Falling back to synthetic data.")
        generate_sybil_synthetic_data(target_transactions)
        return
    except Exception as e:
        print(f"[Alchemy] Unexpected error during connection check: {e}\n  → Falling back to synthetic data.")
        generate_sybil_synthetic_data(target_transactions)
        return

    # ── 2. Crawl seed addresses ──────────────────────────────────────────────
    all_transactions = []

    for seed in SEED_ADDRESSES:
        if len(all_transactions) >= target_transactions:
            break

        print(f"[Alchemy] Crawling {seed[:12]}…")
        page_key = None
        max_pages = 50   # 50 × 1000 = 50 k per address

        for page in range(max_pages):
            if len(all_transactions) >= target_transactions:
                break

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": "0x0",
                    "toBlock": "latest",
                    "fromAddress": seed,
                    "category": ["external"],
                    "withMetadata": True,
                    "excludeZeroValue": True,
                    "maxCount": "0x3E8",   # 1 000 per page
                }],
            }
            if page_key:
                payload["params"][0]["pageKey"] = page_key

            try:
                r = requests.post(url, json=payload, headers=headers, timeout=20)
                r.raise_for_status()
                resp_json = r.json()
            except Exception as e:
                print(f"[Alchemy] Transfer fetch error (page {page + 1}): {e} — stopping this address.")
                break

            if "error" in resp_json:
                print(f"[Alchemy] API error on page {page + 1}: {resp_json['error'].get('message')} — stopping.")
                break

            result = resp_json.get("result", {})
            transfers = result.get("transfers", [])
            if not transfers:
                break

            for tx in transfers:
                raw_value = tx.get("value", 0) or 0
                all_transactions.append({
                    "hash": tx.get("hash", ""),
                    "blockNumber": int(tx.get("blockNum", "0x0"), 16),
                    "timeStamp": tx.get("metadata", {}).get("blockTimestamp", ""),
                    "from": tx.get("from", ""),
                    "to": tx.get("to", ""),
                    "value": str(int(float(raw_value) * 10**18)),
                    "gas": "21000",
                    "gasPrice": "0",
                })

            print(f"  Page {page + 1}: +{len(transfers):,} transfers  (total {len(all_transactions):,})")
            page_key = result.get("pageKey")
            if not page_key:
                break

    if not all_transactions:
        print("[Alchemy] No transactions returned from any seed address.  Falling back to synthetic data.")
        generate_sybil_synthetic_data(target_transactions)
        return

    print(f"[Alchemy] Fetched {len(all_transactions):,} transactions total.")
    _save_to_csv(all_transactions)


def _save_to_csv(transactions: list):
    """Write a list of transaction dicts to the raw CSV file."""
    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    fieldnames = ["hash", "blockNumber", "timeStamp", "from", "to", "value", "gas", "gasPrice"]
    with open(RAW_DATA_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(transactions)
    print(f"[Pipeline] Saved {len(transactions):,} rows → {RAW_DATA_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
#  Realistic Sybil synthetic data generator
#  Produces four realistic attack patterns that a GNN can actually learn from:
#    1. Hub-and-spoke bot farm  — one controller, N worker wallets
#    2. Wash-trading ring       — small circular loops cycling value
#    3. Layered Sybil cluster   — hierarchical multi-hop fan-out
#    4. Normal honest users     — random organic background noise
# ─────────────────────────────────────────────────────────────────────────────

def _addr(prefix: str = "") -> str:
    """Generate a realistic-looking Ethereum address."""
    return f"0x{prefix}{uuid.uuid4().hex[:40 - len(prefix)]}"


def generate_sybil_synthetic_data(num_transactions: int = 50_000):
    """
    Generate a synthetic blockchain dataset that contains realistic Sybil
    attack patterns mixed with honest organic activity.

    Pattern breakdown (roughly):
        30 % — Hub-and-spoke bot farms  (high out-degree central node)
        20 % — Wash-trading rings       (circular reciprocal loops)
        15 % — Layered Sybil clusters   (hierarchical fan-out)
        35 % — Honest background noise  (organic random transfers)
    """
    print(f"[Synthetic] Generating {num_transactions:,} transactions with realistic Sybil patterns…")

    transactions = []
    now = int(time.time())

    # ── Shared address pools ─────────────────────────────────────────────────
    # Honest users — large pool to create organic-looking background
    honest_pool = [_addr("aa") for _ in range(3_000)]

    # Bot farm controllers + their worker wallets
    NUM_BOT_FARMS = 15
    bot_farms = []
    for _ in range(NUM_BOT_FARMS):
        controller = _addr("b0")
        workers = [_addr("b1") for _ in range(random.randint(20, 80))]
        bot_farms.append({"controller": controller, "workers": workers})

    # Wash-trade rings
    NUM_RINGS = 25
    wash_rings = []
    for _ in range(NUM_RINGS):
        ring_size = random.randint(3, 8)
        wash_rings.append([_addr("cc") for _ in range(ring_size)])

    # Layered Sybil clusters  (root → mid-layer → leaf)
    NUM_CLUSTERS = 10
    sybil_clusters = []
    for _ in range(NUM_CLUSTERS):
        root = _addr("dd")
        mids = [_addr("d1") for _ in range(random.randint(5, 10))]
        leaves = {m: [_addr("d2") for _ in range(random.randint(5, 15))] for m in mids}
        sybil_clusters.append({"root": root, "mids": mids, "leaves": leaves})

    def _tx(frm, to, value_wei=None, block_offset=0, gas=21_000):
        return {
            "hash": f"0x{uuid.uuid4().hex}",
            "blockNumber": random.randint(18_000_000, 22_000_000) + block_offset,
            "timeStamp": now - random.randint(0, 31_536_000),  # last ~1 year
            "from": frm,
            "to": to,
            "value": str(value_wei or random.randint(10**15, 5 * 10**18)),
            "gas": str(gas),
            "gasPrice": str(random.randint(10**9, 5 * 10**10)),
        }

    # ── 1. Hub-and-spoke bot farm transactions (30 %) ────────────────────────
    hub_target = int(num_transactions * 0.30)
    while len(transactions) < hub_target:
        farm = random.choice(bot_farms)
        ctrl = farm["controller"]
        workers = farm["workers"]

        # Controller fans out funds to workers (funding event)
        worker = random.choice(workers)
        transactions.append(_tx(ctrl, worker, value_wei=random.randint(10**16, 10**17)))

        # Workers fan funds back to controller (collection event)
        transactions.append(_tx(worker, ctrl, value_wei=random.randint(10**14, 10**15)))

        # Workers occasionally interact with each other (coordination)
        if random.random() < 0.3:
            w2 = random.choice(workers)
            if w2 != worker:
                transactions.append(_tx(worker, w2, value_wei=random.randint(10**13, 10**14)))

    # ── 2. Wash-trading ring transactions (20 %) ─────────────────────────────
    ring_target = int(num_transactions * 0.20)
    ring_txs = []
    while len(ring_txs) < ring_target:
        ring = random.choice(wash_rings)
        # Cycle money around the ring
        amount = random.randint(10**17, 10**18)
        for i in range(len(ring)):
            frm = ring[i]
            to  = ring[(i + 1) % len(ring)]
            ring_txs.append(_tx(frm, to, value_wei=amount))
            # Slight value bleed to obscure perfect circularity
            amount = int(amount * random.uniform(0.97, 1.02))
    transactions.extend(ring_txs[:ring_target])

    # ── 3. Layered Sybil cluster transactions (15 %) ─────────────────────────
    cluster_target = int(num_transactions * 0.15)
    cluster_txs = []
    while len(cluster_txs) < cluster_target:
        cluster = random.choice(sybil_clusters)
        root = cluster["root"]
        mid  = random.choice(cluster["mids"])
        leaf = random.choice(cluster["leaves"][mid])

        # Root funds mid, mid funds leaf (hierarchical fan-out)
        cluster_txs.append(_tx(root, mid))
        cluster_txs.append(_tx(mid, leaf))
        # Leaf sends a tiny amount back up the chain (siphoning pattern)
        if random.random() < 0.5:
            cluster_txs.append(_tx(leaf, root, value_wei=random.randint(10**13, 10**14)))
    transactions.extend(cluster_txs[:cluster_target])

    # ── 4. Honest background noise (fill remainder) ──────────────────────────
    while len(transactions) < num_transactions:
        frm = random.choice(honest_pool)
        to  = random.choice(honest_pool)
        while to == frm:
            to = random.choice(honest_pool)
        transactions.append(_tx(frm, to))

    # Shuffle so patterns aren't all clumped together in the CSV
    random.shuffle(transactions)
    transactions = transactions[:num_transactions]

    # ── Build ground-truth label map ────────────────────────────────────────
    bot_addrs = (
        {f["controller"] for f in bot_farms} |
        {w for f in bot_farms for w in f["workers"]}
    )
    ring_addrs    = {a for r in wash_rings for a in r}
    cluster_addrs = (
        {c["root"] for c in sybil_clusters} |
        {m for c in sybil_clusters for m in c["mids"]} |
        {l for c in sybil_clusters for leaves in c["leaves"].values() for l in leaves}
    )
    all_sybil = bot_addrs | ring_addrs | cluster_addrs

    print(f"[Synthetic] Pattern summary:")
    print(f"  Bot farm addresses   : {len(bot_addrs):,}  ({NUM_BOT_FARMS} farms)")
    print(f"  Wash-trade addresses : {len(ring_addrs):,}  ({NUM_RINGS} rings)")
    print(f"  Sybil cluster addrs  : {len(cluster_addrs):,}  ({NUM_CLUSTERS} clusters)")
    print(f"  Honest addresses     : {len(honest_pool):,}")
    print(f"  Total Sybil wallets  : {len(all_sybil):,}")

    _save_to_csv(transactions)

    # ── Save ground-truth labels ─────────────────────────────────────────────
    all_addrs = set()
    for tx in transactions:
        all_addrs.add(tx["from"])
        all_addrs.add(tx["to"])

    labels_path = os.path.join(os.path.dirname(RAW_DATA_PATH), "labels.csv")
    with open(labels_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["address", "is_sybil"])
        writer.writeheader()
        for addr in all_addrs:
            writer.writerow({"address": addr, "is_sybil": 1 if addr in all_sybil else 0})
    n_sybil_saved = sum(1 for a in all_addrs if a in all_sybil)
    n_human_saved = len(all_addrs) - n_sybil_saved
    print(f"[Synthetic] Labels saved → {labels_path}")
    print(f"            Sybil={n_sybil_saved:,}  Human={n_human_saved:,}")


# ─────────────────────────────────────────────────────────────────────────────
#  Legacy Etherscan fallback
# ─────────────────────────────────────────────────────────────────────────────

def fetch_from_etherscan(api_key: str, target_transactions: int = 50_000):
    """Legacy Etherscan fallback — only used if ALCHEMY_API_KEY is absent."""
    print("[Etherscan] Using legacy Etherscan fallback…")
    seed_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    url = (
        f"https://api.etherscan.io/api?module=account&action=txlist"
        f"&address={seed_address}&startblock=0&endblock=99999999"
        f"&page=1&offset=10000&sort=asc&apikey={api_key}"
    )
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Etherscan] Network error: {e}  → Falling back to synthetic data.")
        generate_sybil_synthetic_data(target_transactions)
        return

    if data.get("status") != "1":
        msg = data.get("message", "unknown error")
        print(f"[Etherscan] API returned error: {msg}  → Falling back to synthetic data.")
        generate_sybil_synthetic_data(target_transactions)
        return

    results = data["result"]
    print(f"[Etherscan] Fetched {len(results):,} transactions.")
    _save_to_csv(results)


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def fetch_data():
    if ALCHEMY_API_KEY:
        fetch_from_alchemy(ALCHEMY_API_KEY)
    elif API_KEY:
        fetch_from_etherscan(API_KEY)
    else:
        print("[Pipeline] No API key configured (ALCHEMY_API_KEY / ETHERSCAN_API_KEY).")
        print("  → Running with synthetic Sybil data generator.")
        print("  → To use real data: add ALCHEMY_API_KEY=<your_key> to your .env file.")
        print("  → Get a free key at: https://dashboard.alchemy.com/\n")
        generate_sybil_synthetic_data(50_000)


if __name__ == "__main__":
    fetch_data()
