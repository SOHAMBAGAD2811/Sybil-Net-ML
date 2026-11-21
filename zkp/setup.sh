#!/bin/bash
set -e

echo "======================================"
echo " Sybil-Net zk-SNARK Setup script "
echo "======================================"

# Create directories
mkdir -p circuits keys proofs scripts

# Install dependencies
echo "Installing dependencies..."
npm install snarkjs circomlib circomlibjs

# Check for circom
if ! command -v circom &> /dev/null; then
    echo "circom could not be found, attempting to install globally via npm..."
    npm install -g circom
fi

cd circuits

# Compile the circuit
echo "Compiling HumanityProof.circom..."
circom HumanityProof.circom --r1cs --wasm --sym

cd ../keys

echo "Running Powers of Tau ceremony..."
# Start a new powers of tau ceremony
npx snarkjs powersoftau new bn128 12 pot12_0000.ptau -v

# Contribute to the ceremony
npx snarkjs powersoftau contribute pot12_0000.ptau pot12_0001.ptau --name="First contribution" -v -e="some random text for entropy"

# Prepare for Phase 2
npx snarkjs powersoftau prepare phase2 pot12_0001.ptau pot12_final.ptau -v

echo "Generating zkey..."
# Generate a .zkey file that will contain the proving and verification keys together.
npx snarkjs groth16 setup ../circuits/HumanityProof.r1cs pot12_final.ptau HumanityProof_0000.zkey

# Contribute to the phase 2 of the ceremony
npx snarkjs zkey contribute HumanityProof_0000.zkey HumanityProof_final.zkey --name="Second contribution" -v -e="Another random entropy"

# Export the verification key
echo "Exporting verification key..."
npx snarkjs zkey export verificationkey HumanityProof_final.zkey verification_key.json

# Export the Solidity Verifier
echo "Exporting Solidity Verifier..."
npx snarkjs zkey export solidityverifier HumanityProof_final.zkey ../../contracts/contracts/ZKVerifier.sol

echo "Setup complete!"
echo "The Solidity verifier has been written to contracts/contracts/ZKVerifier.sol."
