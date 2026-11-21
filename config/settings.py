import os
from dotenv import load_dotenv

load_dotenv()

# Alchemy API key (replaces Etherscan)
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "")

# Legacy Etherscan key (kept for backward compatibility)
API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_DATA_PATH = os.path.join(DATA_DIR, "raw", "transactions.csv")
PROCESSED_DATA_PATH = os.path.join(DATA_DIR, "processed")

# Multichain data paths (Week 7)
RAW_MULTICHAIN_PATH = os.path.join(DATA_DIR, "raw", "transactions_multichain.csv")
RAW_MULTICHAIN_LABELS_PATH = os.path.join(DATA_DIR, "raw", "labels_multichain.csv")

# ─────────────────────────────────────────────────────────────────────────────
#  Cross-Chain Configuration (Week 7)
# ─────────────────────────────────────────────────────────────────────────────

CHAINS = {
    "ethereum": {"chain_id": 1,     "alchemy_subdomain": "eth-mainnet"},
    "polygon":  {"chain_id": 137,   "alchemy_subdomain": "polygon-mainnet"},
    "arbitrum": {"chain_id": 42161, "alchemy_subdomain": "arb-mainnet"},
    "base":     {"chain_id": 8453,  "alchemy_subdomain": "base-mainnet"},
}

# Well-known bridge contract addresses (used for bridge edge detection)
BRIDGE_CONTRACTS = {
    "polygon_bridge":  "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",
    "arbitrum_bridge": "0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a",
    "base_bridge":     "0x3154Cf16ccdb4C6d922629664174b904d80F2C35",
}

# Flat set of all bridge addresses for fast lookup
BRIDGE_ADDRESSES = set(BRIDGE_CONTRACTS.values())

# Create processed directory if it doesn't exist
os.makedirs(PROCESSED_DATA_PATH, exist_ok=True)
