import os
import csv
import random
import time
import requests
import uuid
import json
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import ALCHEMY_API_KEY, API_KEY, RAW_DATA_PATH

# ─────────────────────────────────────────────────────────────────────────────
#  Alchemy provider  (replaces Etherscan)
#  Docs: https://docs.alchemy.com/reference/alchemy-gettransactions
#  Free tier: 300M CUs / month  (no rate cap on basic calls)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_from_alchemy(api_key, target_transactions=50000):
    """Fetch transactions from a seed address using Alchemy's JSON-RPC API."""
    print("Fetching transactions via Alchemy JSON-RPC API...")

    # Ethereum Mainnet endpoint
    url = f"https://eth-mainnet.g.alchemy.com/v2/{api_key}"
    seed_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"  # vitalik.eth

    headers = {"Content-Type": "application/json"}

    # ── 1. Get the latest block number ──────────────────────────────────────
    payload_blocknum = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": []
    }
    try:
        r = requests.post(url, json=payload_blocknum, headers=headers, timeout=15)
        r.raise_for_status()
        latest_block = int(r.json()["result"], 16)
        print(f"Latest block: {latest_block:,}")
    except Exception as e:
        print(f"Error reaching Alchemy: {e}")
        print("Falling back to dummy data generator...")
        generate_dummy_data(target_transactions)
        return

    # ── 2. Use alchemy_getAssetTransfers to pull TX history ─────────────────
    #    This endpoint paginates up to 1000 results per call.
    payload_transfers = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "alchemy_getAssetTransfers",
        "params": [{
            "fromBlock": "0x0",
            "toBlock": "latest",
            "fromAddress": seed_address,
            "category": ["external"],          # normal ETH transfers
            "withMetadata": True,
            "excludeZeroValue": True,
            "maxCount": "0x3E8"               # 1000 per page
        }]
    }

    all_transactions = []
    page_key = None
    max_pages = 50   # guard against infinite pagination (50 × 1000 = 50 k)

    for page in range(max_pages):
        if page_key:
            payload_transfers["params"][0]["pageKey"] = page_key
        elif "pageKey" in payload_transfers["params"][0]:
            del payload_transfers["params"][0]["pageKey"]

        try:
            r = requests.post(url, json=payload_transfers, headers=headers, timeout=20)
            r.raise_for_status()
            result = r.json().get("result", {})
        except Exception as e:
            print(f"Alchemy transfer error on page {page}: {e}")
            break

        transfers = result.get("transfers", [])
        if not transfers:
            break

        for tx in transfers:
            all_transactions.append({
                "hash": tx.get("hash", ""),
                "blockNumber": int(tx.get("blockNum", "0x0"), 16),
                "timeStamp": tx.get("metadata", {}).get("blockTimestamp", ""),
                "from": tx.get("from", ""),
                "to": tx.get("to", ""),
                "value": str(int(float(tx.get("value", 0)) * 10**18)),  # convert ETH→wei
                "gas": "21000",       # alchemy_getAssetTransfers doesn't return gas
                "gasPrice": "0",
            })

        print(f"  Page {page + 1}: fetched {len(transfers)} transfers (total {len(all_transactions):,})")

        page_key = result.get("pageKey")
        if not page_key or len(all_transactions) >= target_transactions:
            break

    if not all_transactions:
        print("No transactions returned from Alchemy. Falling back to dummy data.")
        generate_dummy_data(target_transactions)
        return

    print(f"Fetched {len(all_transactions):,} transactions from Alchemy.")
    _save_to_csv(all_transactions)


def _save_to_csv(transactions):
    """Write a list of transaction dicts to the raw CSV file."""
    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    fieldnames = ["hash", "blockNumber", "timeStamp", "from", "to", "value", "gas", "gasPrice"]
    with open(RAW_DATA_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(transactions)
    print(f"Saved to {RAW_DATA_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
#  Dummy data fallback
# ─────────────────────────────────────────────────────────────────────────────

def generate_dummy_data(num_transactions=50000):
    """Generates dummy blockchain transactions."""
    print(f"Generating {num_transactions} dummy transactions...")
    addresses = [f"0x{uuid.uuid4().hex[:40]}" for _ in range(5000)]

    transactions = []
    for i in range(num_transactions):
        sender = random.choice(addresses)
        receiver = random.choice(addresses)
        while receiver == sender:
            receiver = random.choice(addresses)

        transactions.append({
            "hash": f"0x{uuid.uuid4().hex}",
            "blockNumber": random.randint(10000000, 15000000),
            "timeStamp": int(time.time()) - random.randint(0, 1000000),
            "from": sender,
            "to": receiver,
            "value": str(random.randint(10**15, 10**20)),
            "gas": str(random.randint(21000, 100000)),
            "gasPrice": str(random.randint(10**9, 5 * 10**10)),
        })

    _save_to_csv(transactions)


# ─────────────────────────────────────────────────────────────────────────────
#  Legacy Etherscan fallback (kept for users who still have an Etherscan key)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_from_etherscan(api_key, target_transactions=50000):
    print("Fetching from Etherscan (legacy)...")
    seed_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    url = (
        f"https://api.etherscan.io/api?module=account&action=txlist"
        f"&address={seed_address}&startblock=0&endblock=99999999"
        f"&page=1&offset=10000&sort=asc&apikey={api_key}"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Network error when connecting to Etherscan: {e}")
        print("Falling back to dummy data generator...")
        generate_dummy_data(target_transactions)
        return

    if data.get("status") != "1":
        print(f"Error fetching data: {data.get('message')}")
        print("Falling back to dummy data generator...")
        generate_dummy_data(target_transactions)
        return

    _save_to_csv(data["result"])
    print(f"Saved {len(data['result'])} Etherscan transactions.")


# ─────────────────────────────────────────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def fetch_data():
    if ALCHEMY_API_KEY:
        fetch_from_alchemy(ALCHEMY_API_KEY)
    elif API_KEY:
        # Legacy: user still has an Etherscan key
        fetch_from_etherscan(API_KEY)
    else:
        print("No API key found (ALCHEMY_API_KEY or ETHERSCAN_API_KEY).")
        print("Using dummy data generator to meet requirements.")
        generate_dummy_data(50000)


if __name__ == "__main__":
    fetch_data()
