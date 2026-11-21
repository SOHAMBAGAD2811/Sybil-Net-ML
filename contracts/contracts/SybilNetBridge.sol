// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

/**
 * @title  ISybilNet
 * @notice Interface to read credential state from the core SybilNet contract.
 */
interface ISybilNet {
    enum CredentialStatus { None, Active, Suspended, Revoked }

    struct Credential {
        CredentialStatus status;
        uint256          stakedAmount;
        uint256          issuedAt;
        uint256          sybilScore;
        uint256          slashedAt;
        uint256          warnCount;
    }

    function isVerifiedHuman(address wallet) external view returns (bool);
    function getSybilScore(address wallet) external view returns (uint256);
    function getCredential(address wallet) external view returns (Credential memory);
}

/**
 * @title  SybilNetBridge
 * @author Sybil-Net Project
 * @notice Cross-Chain Credential Bridge (Week 7)
 *
 *         Enables Humanity Credentials from the core SybilNet contract to be
 *         portable across L2 chains (Polygon, Arbitrum, Base) using a
 *         Lock-and-Mint pattern:
 *
 *         Source chain:
 *           1. User calls lockCredential(destChainId)
 *           2. Contract verifies they hold an Active credential via ISybilNet
 *           3. Emits CredentialLocked event (picked up by the bridge relay)
 *
 *         Destination chain:
 *           1. Bridge operator calls mintBridgedCredential() with oracle signature
 *           2. Contract verifies the signature and mints a BridgedCredential
 *           3. isBridgedHuman() returns true for the wallet
 *
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │   Source Chain                              Destination Chain (L2)     │
 * │   ─────────────                             ──────────────────────     │
 * │   lockCredential(chainId)                                             │
 * │     └─► CredentialLocked event ──relay──► mintBridgedCredential()     │
 * │                                             └─► BridgedCredential    │
 * │   unlockCredential()                          isBridgedHuman() ✓     │
 * │     └─► CredentialUnlocked                                           │
 * │                                           revokeBridgedCredential() │
 * │                                             └─► credential removed  │
 * └─────────────────────────────────────────────────────────────────────────┘
 *
 * Roles:
 *   DEFAULT_ADMIN_ROLE    — protocol admin
 *   BRIDGE_OPERATOR_ROLE  — cross-chain relay service
 */
contract SybilNetBridge is AccessControl, ReentrancyGuard, Pausable {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    // ─── Roles ────────────────────────────────────────────────────────────
    bytes32 public constant BRIDGE_OPERATOR_ROLE = keccak256("BRIDGE_OPERATOR_ROLE");

    // ─── Core contract reference ──────────────────────────────────────────
    ISybilNet public sybilNet;

    // ─── Supported chains ─────────────────────────────────────────────────
    mapping(uint256 => string) public supportedChains;
    mapping(uint256 => bool)   public isChainSupported;

    // ─── Lock records (source chain side) ─────────────────────────────────
    struct LockRecord {
        address wallet;
        uint256 destChainId;
        uint256 sybilScore;
        uint256 stakedAmount;
        uint256 nonce;
        uint256 lockedAt;
        bool    isLocked;
    }

    mapping(address => LockRecord) public lockRecords;
    mapping(address => uint256)    public lockNonces;

    // ─── Bridged credentials (destination chain side) ─────────────────────
    struct BridgedCredential {
        address wallet;
        uint256 sybilScore;
        uint256 sourceStake;
        uint256 sourceChainId;
        uint256 bridgedAt;
        bool    isActive;
    }

    mapping(address => BridgedCredential) public bridgedCredentials;

    /// Total bridged credentials currently active
    uint256 public totalBridged;

    /// Oracle signer address — must match the signature in mintBridgedCredential
    address public oracleSigner;

    // ─── Events ───────────────────────────────────────────────────────────
    event CredentialLocked(
        address indexed wallet,
        uint256 destChainId,
        uint256 sybilScore,
        uint256 stakedAmount,
        uint256 nonce,
        uint256 timestamp
    );
    event CredentialUnlocked(address indexed wallet, uint256 timestamp);
    event BridgedCredentialMinted(
        address indexed wallet,
        uint256 sybilScore,
        uint256 sourceStake,
        uint256 sourceChainId,
        uint256 timestamp
    );
    event BridgedCredentialRevoked(address indexed wallet, string reason, uint256 timestamp);
    event ChainAdded(uint256 chainId, string name);
    event ChainRemoved(uint256 chainId);
    event OracleSignerUpdated(address oldSigner, address newSigner);

    // ─── Errors ───────────────────────────────────────────────────────────
    error NoActiveCredential();
    error AlreadyLocked();
    error NotLocked();
    error UnsupportedChain(uint256 chainId);
    error AlreadyBridged();
    error NotBridged();
    error InvalidSignature();
    error InvalidAddress();
    error InvalidNonce(uint256 expected, uint256 got);

    // ─── Constructor ──────────────────────────────────────────────────────
    constructor(address _sybilNet, address _oracleSigner) {
        if (_sybilNet == address(0) || _oracleSigner == address(0))
            revert InvalidAddress();

        sybilNet     = ISybilNet(_sybilNet);
        oracleSigner = _oracleSigner;

        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(BRIDGE_OPERATOR_ROLE, msg.sender);

        // Register default supported chains
        _addChain(137,   "Polygon");
        _addChain(42161, "Arbitrum");
        _addChain(8453,  "Base");
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  SOURCE CHAIN FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Lock your Humanity Credential for bridging to a destination chain.
     * @param  destChainId  The chain ID to bridge the credential to.
     */
    function lockCredential(uint256 destChainId)
        external
        whenNotPaused
    {
        if (!isChainSupported[destChainId])
            revert UnsupportedChain(destChainId);
        if (lockRecords[msg.sender].isLocked)
            revert AlreadyLocked();
        if (!sybilNet.isVerifiedHuman(msg.sender))
            revert NoActiveCredential();

        ISybilNet.Credential memory cred = sybilNet.getCredential(msg.sender);
        uint256 nonce = lockNonces[msg.sender]++;

        lockRecords[msg.sender] = LockRecord({
            wallet:       msg.sender,
            destChainId:  destChainId,
            sybilScore:   cred.sybilScore,
            stakedAmount: cred.stakedAmount,
            nonce:        nonce,
            lockedAt:     block.timestamp,
            isLocked:     true
        });

        emit CredentialLocked(
            msg.sender,
            destChainId,
            cred.sybilScore,
            cred.stakedAmount,
            nonce,
            block.timestamp
        );
    }

    /**
     * @notice Unlock a previously locked credential (cancel the bridge).
     */
    function unlockCredential() external whenNotPaused {
        if (!lockRecords[msg.sender].isLocked)
            revert NotLocked();

        lockRecords[msg.sender].isLocked = false;

        emit CredentialUnlocked(msg.sender, block.timestamp);
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  DESTINATION CHAIN FUNCTIONS (Bridge Operator)
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Mint a bridged credential on the destination chain.
     * @dev    Called by the BRIDGE_OPERATOR_ROLE after verifying the lock
     *         event on the source chain.
     *
     * @param  wallet         The wallet address receiving the bridged credential.
     * @param  sybilScore     The Sybil score from the source chain.
     * @param  sourceStake    The staked amount on the source chain.
     * @param  sourceChainId  The chain ID where the original credential lives.
     * @param  nonce          Lock nonce (must match source chain lock record).
     * @param  oracleSignature  EIP-191 signature from the oracle signer over
     *                          the message hash of (wallet, score, stake, chainId, nonce).
     */
    function mintBridgedCredential(
        address wallet,
        uint256 sybilScore,
        uint256 sourceStake,
        uint256 sourceChainId,
        uint256 nonce,
        bytes calldata oracleSignature
    )
        external
        onlyRole(BRIDGE_OPERATOR_ROLE)
        whenNotPaused
    {
        if (wallet == address(0)) revert InvalidAddress();
        if (bridgedCredentials[wallet].isActive) revert AlreadyBridged();

        // Verify oracle signature
        bytes32 messageHash = keccak256(abi.encodePacked(
            wallet, sybilScore, sourceStake, sourceChainId, nonce
        ));
        bytes32 ethSignedHash = messageHash.toEthSignedMessageHash();
        address recovered = ethSignedHash.recover(oracleSignature);

        if (recovered != oracleSigner) revert InvalidSignature();

        bridgedCredentials[wallet] = BridgedCredential({
            wallet:        wallet,
            sybilScore:    sybilScore,
            sourceStake:   sourceStake,
            sourceChainId: sourceChainId,
            bridgedAt:     block.timestamp,
            isActive:      true
        });

        totalBridged++;

        emit BridgedCredentialMinted(
            wallet, sybilScore, sourceStake, sourceChainId, block.timestamp
        );
    }

    /**
     * @notice Revoke a bridged credential (e.g. if the source chain slashed).
     */
    function revokeBridgedCredential(address wallet, string calldata reason)
        external
        onlyRole(BRIDGE_OPERATOR_ROLE)
        whenNotPaused
    {
        if (!bridgedCredentials[wallet].isActive) revert NotBridged();

        bridgedCredentials[wallet].isActive = false;
        totalBridged--;

        emit BridgedCredentialRevoked(wallet, reason, block.timestamp);
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  ADMIN FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    function addChain(uint256 chainId, string calldata name)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        _addChain(chainId, name);
    }

    function removeChain(uint256 chainId)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        isChainSupported[chainId] = false;
        delete supportedChains[chainId];
        emit ChainRemoved(chainId);
    }

    function setOracleSigner(address newSigner)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (newSigner == address(0)) revert InvalidAddress();
        emit OracleSignerUpdated(oracleSigner, newSigner);
        oracleSigner = newSigner;
    }

    function setSybilNet(address _sybilNet)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (_sybilNet == address(0)) revert InvalidAddress();
        sybilNet = ISybilNet(_sybilNet);
    }

    function pause()   external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    // ═══════════════════════════════════════════════════════════════════════
    //  VIEW FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    /// @notice Returns true if the wallet has an active bridged credential.
    function isBridgedHuman(address wallet) external view returns (bool) {
        return bridgedCredentials[wallet].isActive;
    }

    /// @notice Returns the full bridged credential struct.
    function getBridgedCredential(address wallet)
        external
        view
        returns (BridgedCredential memory)
    {
        return bridgedCredentials[wallet];
    }

    /// @notice Returns the lock record for a wallet on the source chain.
    function getLockRecord(address wallet)
        external
        view
        returns (LockRecord memory)
    {
        return lockRecords[wallet];
    }

    /// @notice Check if a credential is currently locked for bridging.
    function isCredentialLocked(address wallet) external view returns (bool) {
        return lockRecords[wallet].isLocked;
    }

    // ─── Internal ─────────────────────────────────────────────────────────

    function _addChain(uint256 chainId, string memory name) internal {
        supportedChains[chainId] = name;
        isChainSupported[chainId] = true;
        emit ChainAdded(chainId, name);
    }
}
