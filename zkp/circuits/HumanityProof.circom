pragma circom 2.0.0;

include "../../node_modules/circomlib/circuits/poseidon.circom";
include "../../node_modules/circomlib/circuits/comparators.circom";

template HumanityProof() {
    // Private Inputs
    signal input sybilScore;
    signal input secret;
    signal input walletAddress;

    // Public Inputs
    signal input threshold;
    signal input walletCommitment;

    // Output
    signal output isHuman;

    // 1. Verify score is less than threshold
    // Assuming scores are between 0 and 100, 8 bits is enough.
    component lessThan = LessThan(8);
    lessThan.in[0] <== sybilScore;
    lessThan.in[1] <== threshold;

    // We enforce that the score is indeed strictly less than threshold
    lessThan.out === 1;
    isHuman <== lessThan.out;

    // 2. Verify wallet commitment matches Poseidon(walletAddress, secret)
    component poseidon = Poseidon(2);
    poseidon.inputs[0] <== walletAddress;
    poseidon.inputs[1] <== secret;

    poseidon.out === walletCommitment;
}

// threshold and walletCommitment are public
component main {public [threshold, walletCommitment]} = HumanityProof();
