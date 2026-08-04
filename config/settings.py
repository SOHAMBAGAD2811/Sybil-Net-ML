import os

API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
RAW_DATA_PATH = os.path.join(DATA_DIR, "raw", "transactions.csv")
PROCESSED_DATA_PATH = os.path.join(DATA_DIR, "processed")

# Create processed directory if it doesn't exist
os.makedirs(PROCESSED_DATA_PATH, exist_ok=True)
