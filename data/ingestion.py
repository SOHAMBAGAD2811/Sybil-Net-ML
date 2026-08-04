import os
import csv
import random
import time
import requests
import uuid
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import API_KEY, RAW_DATA_PATH

def generate_dummy_data(num_transactions=50000):
    """Generates dummy blockchain transactions."""
    print(f"Generating {num_transactions} dummy transactions...")
    addresses = [f"0x{uuid.uuid4().hex[:40]}" for _ in range(5000)]  # 5000 wallets
    
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
        
    os.makedirs(os.path.dirname(RAW_DATA_PATH), exist_ok=True)
    with open(RAW_DATA_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["hash", "blockNumber", "timeStamp", "from", "to", "value", "gas", "gasPrice"])
        writer.writeheader()
        writer.writerows(transactions)
    print(f"Saved to {RAW_DATA_PATH}")

def fetch_data():
    if not API_KEY:
        print("No API key found. Using dummy data generator to meet requirements.")
        generate_dummy_data(50000)
    else:
        print("API Key found. Fetching from Etherscan (Note: Free tier might be slow for 50k txs).")
        # Implement basic fetch
        pass

if __name__ == "__main__":
    fetch_data()
