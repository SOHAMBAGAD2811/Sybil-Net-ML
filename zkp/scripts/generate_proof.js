const snarkjs = require("snarkjs");
const fs = require("fs");
const path = require("path");

async function run() {
    // Arguments: walletAddress, secret, sybilScore, threshold, walletCommitment
    const args = process.argv.slice(2);
    if (args.length !== 5) {
        console.error("Usage: node generate_proof.js <walletAddress> <secret> <sybilScore> <threshold> <walletCommitment>");
        process.exit(1);
    }

    const [walletAddress, secret, sybilScore, threshold, walletCommitment] = args;

    const input = {
        walletAddress: walletAddress,
        secret: secret,
        sybilScore: sybilScore,
        threshold: threshold,
        walletCommitment: walletCommitment
    };

    console.log("Generating proof for input:", input);

    const wasmPath = path.join(__dirname, "../circuits/HumanityProof_js/HumanityProof.wasm");
    const zkeyPath = path.join(__dirname, "../keys/HumanityProof_final.zkey");
    const proofPath = path.join(__dirname, "../proofs/proof.json");
    const publicPath = path.join(__dirname, "../proofs/public.json");

    try {
        // Step 1: Generate Groth16 proof and public signals
        const { proof, publicSignals } = await snarkjs.groth16.fullProve(input, wasmPath, zkeyPath);

        console.log("Proof generated successfully.");

        // Step 2: Save the proof and public signals to files
        fs.writeFileSync(proofPath, JSON.stringify(proof, null, 2));
        fs.writeFileSync(publicPath, JSON.stringify(publicSignals, null, 2));

        console.log(`Proof saved to ${proofPath}`);
        console.log(`Public signals saved to ${publicPath}`);
    } catch (err) {
        console.error("Error generating proof:", err);
        process.exit(1);
    }
}

run().then(() => {
    process.exit(0);
});
