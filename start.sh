#!/bin/bash
set -e
export HARDHAT_TELEMETRY_OPTOUT=1
export CI=true

echo "===================================================="
echo "🚀 Starting Sybil-Net: End-to-End System            "
echo "===================================================="

# 1. Kill any existing instances
echo "[1/5] Cleaning up old processes..."
pkill -f "hardhat node" || true
pkill -f "next" || true
sleep 2

# 2. Start Hardhat node in the background
echo "[2/5] Starting local Hardhat blockchain..."
cd contracts
npx hardhat node > ../hardhat_node.log 2>&1 &
HARDHAT_PID=$!
sleep 4 # wait for node to boot

# 3. Compile and deploy contracts
echo "[3/5] Compiling and deploying smart contracts..."
npx hardhat compile
npx hardhat run scripts/deploy.js --network localhost
# Setup Presentation State
echo "[3.5/5] Setting up presentation state..."
npx hardhat run scripts/setup_presentation.js --network localhost

# 4. Generate Mock ML data
echo "[4/5] Generating mock ML data for UI..."
cd ..
mkdir -p data/processed
echo "node_id,sybil_probability,classification" > data/processed/node_scores.csv
echo "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266,0.12,Human" >> data/processed/node_scores.csv
echo "0x70997970C51812dc3A010C7d01b50e0d17dc79C8,0.95,Sybil" >> data/processed/node_scores.csv

# 5. Start Frontend
echo "[5/5] Starting Next.js frontend..."
cd frontend
npm install --legacy-peer-deps
npm run dev &
NEXT_PID=$!

echo "===================================================="
echo "✅ System is live!"
echo "📡 Blockchain:   http://127.0.0.1:8545"
echo "🌐 Frontend:     http://localhost:3000"
echo "===================================================="
echo "Press Ctrl+C to stop all services."

# Wait for user interrupt
wait
