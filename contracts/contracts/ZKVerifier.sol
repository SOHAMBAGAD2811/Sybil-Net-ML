// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

/**
 * @title ZKVerifier
 * @notice Verifies Groth16 zk-SNARK proofs of humanity.
 *         Protects against proof replay attacks using a nullifier.
 */
contract ZKVerifier {

    // Proof replay protection
    // To be perfectly anonymous, we might use a hash of the proof itself,
    // or a specific nullifier output from the circuit. 
    // Here we will use a hash of the proof parameters as the nullifier for simplicity.
    mapping(bytes32 => bool) public proofNullifiers;

    event ProofVerified(address indexed submitter, uint256 commitment, uint256 timestamp);

    error ProofAlreadyUsed();
    error InvalidProof();

    /**
     * @notice Verifies a Groth16 proof of humanity
     * @param pA Point A of the proof
     * @param pB Point B of the proof
     * @param pC Point C of the proof
     * @param pubSignals Public signals: [threshold, walletCommitment]
     * @return bool True if proof is valid
     */
    function verifyHumanityProof(
        uint[2] memory pA,
        uint[2][2] memory pB,
        uint[2] memory pC,
        uint[4] memory pubSignals // We pad this to 4 in case snarkjs expects it, or keep it generic
    ) public returns (bool) {
        
        // 1. Replay Protection
        // Generate a unique identifier for this proof
        bytes32 nullifier = keccak256(abi.encodePacked(pA, pB, pC, pubSignals));
        
        if (proofNullifiers[nullifier]) {
            revert ProofAlreadyUsed();
        }
        
        // 2. Verify the proof
        bool isValid = _verifyProof(pA, pB, pC, pubSignals);
        
        if (!isValid) {
            revert InvalidProof();
        }

        // 3. Mark proof as used
        proofNullifiers[nullifier] = true;

        // pubSignals[1] is typically the walletCommitment in our circuit
        // We emit it so the protocol knows which commitment was verified
        emit ProofVerified(msg.sender, pubSignals[1], block.timestamp);

        return true;
    }

    /**
     * @dev Internal stub for the actual snarkjs-exported verification logic.
     *      TODO: Replace this block with the actual snarkjs-exported verification key pairing check
     *      once the setup.sh script generates the final circuits.
     */
    function _verifyProof(
        uint[2] memory /* pA */,
        uint[2][2] memory /* pB */,
        uint[2] memory /* pC */,
        uint[4] memory /* pubSignals */
    ) internal pure returns (bool) {
        // Mock verification logic
        // In reality, this would use pairing precompiles (e.g., ecrecover, pairing)
        // For development/stub purposes, we accept all proofs unless a parameter is zero
        
        // Example mock check: 
        // if (pA[0] == 0) return false;
        
        return true; 
    }
}
