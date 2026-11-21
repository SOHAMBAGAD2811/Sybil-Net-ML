import argparse
import csv
import json
import subprocess
import os
import hashlib

def read_score(wallet):
    score_file = os.path.join(os.path.dirname(__file__), '../../data/processed/node_scores.csv')
    try:
        with open(score_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['node_id'].lower() == wallet.lower():
                    # Probability is 0.0 to 1.0, convert to 0-100 score
                    return int(float(row['sybil_probability']) * 100)
    except Exception as e:
        print(f"Error reading scores: {e}")
    return None

def poseidon_hash(wallet, secret):
    # This is a dummy hash in Python to demonstrate, but realistically 
    # we would compute Poseidon or call a JS helper.
    # For now, let's call a nodejs script to compute the actual Poseidon commitment
    # Or just write a small JS script to do it.
    script = """
const circomlibjs = require('circomlibjs');
async function run() {
    const poseidon = await circomlibjs.buildPoseidon();
    const F = poseidon.F;
    const res = poseidon([process.argv[1], process.argv[2]]);
    console.log(F.toString(res));
}
run();
"""
    tmp_file = "tmp_poseidon.js"
    with open(tmp_file, "w") as f:
        f.write(script)
    
    # Wallet needs to be a BigInt string. Convert eth address to int.
    wallet_int = str(int(wallet, 16))
    
    try:
        res = subprocess.check_output(["node", tmp_file, wallet_int, str(secret)])
        os.remove(tmp_file)
        return res.decode('utf-8').strip()
    except Exception as e:
        print(f"Error computing poseidon: {e}")
        os.remove(tmp_file)
        return None

def main():
    parser = argparse.ArgumentParser(description="Prove humanity via zk-SNARK")
    parser.add_argument("--wallet", required=True, help="Wallet address")
    parser.add_argument("--secret", required=True, type=int, help="Secret salt (integer)")
    parser.add_argument("--threshold", type=int, default=70, help="Humanity threshold (0-100)")
    args = parser.parse_args()

    print(f"Fetching score for {args.wallet}...")
    score = read_score(args.wallet)
    
    if score is None:
        print("Error: Wallet not found in node_scores.csv")
        return

    print(f"Sybil Score: {score}")
    
    if score >= args.threshold:
        print(f"Error: Score {score} is greater than or equal to threshold {args.threshold}. Cannot generate proof.")
        return

    print("Computing Poseidon commitment...")
    commitment = poseidon_hash(args.wallet, args.secret)
    if not commitment:
        return
    
    wallet_int = str(int(args.wallet, 16))
    
    # Call generate_proof.js
    script_path = os.path.join(os.path.dirname(__file__), 'generate_proof.js')
    
    print("Generating zero-knowledge proof...")
    try:
        subprocess.check_call(["node", script_path, wallet_int, str(args.secret), str(score), str(args.threshold), commitment])
    except subprocess.CalledProcessError:
        print("Failed to generate proof.")
        return

    # Rename proof files
    proof_hash = hashlib.sha256(args.wallet.encode()).hexdigest()[:8]
    proofs_dir = os.path.join(os.path.dirname(__file__), '../proofs')
    
    src_proof = os.path.join(proofs_dir, 'proof.json')
    src_public = os.path.join(proofs_dir, 'public.json')
    
    dst_proof = os.path.join(proofs_dir, f"{proof_hash}_proof.json")
    dst_public = os.path.join(proofs_dir, f"{proof_hash}_public.json")
    
    if os.path.exists(src_proof):
        os.rename(src_proof, dst_proof)
        os.rename(src_public, dst_public)
    
    print("\n" + "="*40)
    print(" ZK PROOF GENERATED SUCCESSFULLY ")
    print("="*40)
    print(f"Wallet (Masked): 0x{proof_hash}... ")
    print(f"Sybil Score:     {score}")
    print(f"Threshold:       {args.threshold}")
    print(f"Commitment:      {commitment[:16]}...")
    print(f"Proof File:      {dst_proof}")
    print(f"Public Sigs:     {dst_public}")
    print("="*40)

if __name__ == "__main__":
    main()
