// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

interface ISybilNetMarket {
    function isVerifiedHuman(address wallet) external view returns (bool);
}

/**
 * @title SybilMarketplace
 * @notice A demonstration dApp that uses SybilNet for sybil-resistance.
 *         It offers an exclusive "Airdrop" (or premium service) that can 
 *         ONLY be claimed by verified humans holding an active credential.
 */
contract SybilMarketplace {
    ISybilNetMarket public sybilNet;
    
    mapping(address => bool) public hasClaimed;
    uint256 public totalClaims;
    uint256 public constant REWARD_AMOUNT = 100; // Mock tokens

    event AirdropClaimed(address indexed user, uint256 amount);

    error NotVerifiedHuman();
    error AlreadyClaimed();

    constructor(address _sybilNet) {
        sybilNet = ISybilNetMarket(_sybilNet);
    }

    /**
     * @notice Claims a reward. Fails if the user is a suspected bot (revoked/suspended credential)
     *         or if they haven't staked for a Humanity Credential.
     */
    function claimExclusiveAirdrop() external {
        // 1. Check SybilNet
        if (!sybilNet.isVerifiedHuman(msg.sender)) {
            revert NotVerifiedHuman();
        }

        // 2. State checks
        if (hasClaimed[msg.sender]) {
            revert AlreadyClaimed();
        }

        // 3. Effects
        hasClaimed[msg.sender] = true;
        totalClaims++;

        emit AirdropClaimed(msg.sender, REWARD_AMOUNT);
    }
}
