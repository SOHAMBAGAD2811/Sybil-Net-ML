// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title  SybilNet
 * @author Sybil-Net Project
 * @notice Decentralised identity protocol where wallets stake ETH to mint a
 *         "Humanity Credential".  A trusted GNN oracle continuously monitors
 *         the on-chain transaction graph.  If a wallet is flagged as a Sybil
 *         attacker, the oracle calls `slash()` which destroys the stake and
 *         burns the credential.
 *
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  User Stakes ETH ──► Credential Minted ──► GNN monitors topology       │
 * │         ▲                                         │                    │
 * │         │                    Sybil detected?      │                    │
 * │         │                         ├── Yes ────► Slash + Burn           │
 * │         │                         └── No  ────► Credential stays valid │
 * │  Credential enables:                                                    │
 * │    • Undercollateralised DeFi loans (Credit Hub)                       │
 * │    • Verified NFT marketplace access (Asset Exchange)                  │
 * │    • Protected yield farming (Yield Hub)                               │
 * └─────────────────────────────────────────────────────────────────────────┘
 *
 * Roles:
 *   DEFAULT_ADMIN_ROLE — protocol admin (multisig in production)
 *   ORACLE_ROLE        — GNN backend; may call slash() and reportSuspicious()
 *   GUARDIAN_ROLE      — emergency pause only
 */
contract SybilNet is AccessControl, ReentrancyGuard, Pausable {

    // ─── Roles ────────────────────────────────────────────────────────────
    bytes32 public constant ORACLE_ROLE   = keccak256("ORACLE_ROLE");
    bytes32 public constant GUARDIAN_ROLE = keccak256("GUARDIAN_ROLE");

    // ─── Configuration ────────────────────────────────────────────────────
    /// Minimum stake required to mint a Humanity Credential (0.01 ETH)
    uint256 public minStake = 0.01 ether;

    /// Duration after slashing during which the wallet is permanently banned
    uint256 public constant BAN_DURATION = 365 days;

    /// Share of slashed stake sent to the slash reporter (in basis points, e.g. 1000 = 10%)
    uint256 public slashReporterFeeBps = 1000;

    /// Treasury address — receives the remainder of slashed funds
    address payable public treasury;

    // ─── Credential state ─────────────────────────────────────────────────
    enum CredentialStatus { None, Active, Suspended, Revoked }

    struct Credential {
        CredentialStatus status;
        uint256          stakedAmount;   // ETH locked by this wallet
        uint256          issuedAt;       // block.timestamp of minting
        uint256          sybilScore;     // 0–100; updated by oracle (100 = definite Sybil)
        uint256          slashedAt;      // timestamp of slash event (0 if not slashed)
        uint256          warnCount;      // number of oracle warnings before slash
    }

    /// wallet address → credential
    mapping(address => Credential) public credentials;

    /// Total ETH currently staked in the protocol
    uint256 public totalStaked;

    /// Total ETH slashed since deployment
    uint256 public totalSlashed;

    // ─── Events ───────────────────────────────────────────────────────────
    event CredentialMinted(address indexed wallet, uint256 stakedAmount, uint256 timestamp);
    event CredentialRevoked(address indexed wallet, string reason);
    event SybilWarning(address indexed wallet, uint256 newScore, uint256 warnCount);
    event WalletSlashed(address indexed wallet, uint256 slashedAmount, uint256 reporterFee, address indexed reporter);
    event StakeWithdrawn(address indexed wallet, uint256 amount);
    event OracleScoreUpdated(address indexed wallet, uint256 oldScore, uint256 newScore);
    event MinStakeUpdated(uint256 oldMin, uint256 newMin);
    event TreasuryUpdated(address oldTreasury, address newTreasury);

    // ─── Errors ───────────────────────────────────────────────────────────
    error InsufficientStake(uint256 sent, uint256 required);
    error CredentialAlreadyActive();
    error NoActiveCredential();
    error WalletBanned(address wallet, uint256 bannedUntil);
    error ScoreOutOfRange(uint256 score);
    error NothingToWithdraw();
    error WithdrawalLocked();
    error TransferFailed();
    error InvalidAddress();
    error InvalidBps(uint256 bps);

    // ─── Modifiers ────────────────────────────────────────────────────────
    modifier hasActiveCredential(address wallet) {
        if (credentials[wallet].status != CredentialStatus.Active) {
            revert NoActiveCredential();
        }
        _;
    }

    modifier notBanned(address wallet) {
        Credential storage c = credentials[wallet];
        if (c.status == CredentialStatus.Revoked) {
            uint256 bannedUntil = c.slashedAt + BAN_DURATION;
            if (block.timestamp < bannedUntil) {
                revert WalletBanned(wallet, bannedUntil);
            }
        }
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────
    constructor(address _treasury) {
        if (_treasury == address(0)) revert InvalidAddress();
        treasury = payable(_treasury);

        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(GUARDIAN_ROLE,      msg.sender);
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  USER FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Stake ETH and mint a Humanity Credential for the caller.
     * @dev    Caller must send at least `minStake` wei.
     *         Re-staking is allowed after a ban has expired.
     */
    function mintCredential()
        external
        payable
        nonReentrant
        whenNotPaused
        notBanned(msg.sender)
    {
        if (msg.value < minStake) {
            revert InsufficientStake(msg.value, minStake);
        }
        if (credentials[msg.sender].status == CredentialStatus.Active) {
            revert CredentialAlreadyActive();
        }

        credentials[msg.sender] = Credential({
            status:       CredentialStatus.Active,
            stakedAmount: msg.value,
            issuedAt:     block.timestamp,
            sybilScore:   0,
            slashedAt:    0,
            warnCount:    0
        });

        totalStaked += msg.value;

        emit CredentialMinted(msg.sender, msg.value, block.timestamp);
    }

    /**
     * @notice Voluntarily withdraw stake and surrender the Humanity Credential.
     * @dev    Not callable while the credential is Suspended (pending slash review).
     */
    function withdrawStake()
        external
        nonReentrant
        whenNotPaused
        hasActiveCredential(msg.sender)
    {
        Credential storage c = credentials[msg.sender];
        uint256 amount = c.stakedAmount;

        if (amount == 0) revert NothingToWithdraw();

        c.status       = CredentialStatus.Revoked;
        c.stakedAmount = 0;
        totalStaked   -= amount;

        emit StakeWithdrawn(msg.sender, amount);
        emit CredentialRevoked(msg.sender, "voluntary_withdrawal");

        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  ORACLE FUNCTIONS  (called by the GNN backend)
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Update the Sybil score for a wallet based on the latest GNN output.
     * @param  wallet    The wallet address to update.
     * @param  newScore  New Sybil probability score, 0–100.
     *                   • 0–29  : considered clean
     *                   • 30–69 : warning zone
     *                   • 70–100: high-risk, triggers suspension
     */
    function updateSybilScore(address wallet, uint256 newScore)
        external
        onlyRole(ORACLE_ROLE)
        whenNotPaused
        hasActiveCredential(wallet)
    {
        if (newScore > 100) revert ScoreOutOfRange(newScore);

        Credential storage c = credentials[wallet];
        uint256 oldScore = c.sybilScore;
        c.sybilScore = newScore;

        emit OracleScoreUpdated(wallet, oldScore, newScore);

        // Auto-suspend if score crosses the high-risk threshold
        if (newScore >= 70 && c.status == CredentialStatus.Active) {
            c.status = CredentialStatus.Suspended;
            c.warnCount += 1;
            emit SybilWarning(wallet, newScore, c.warnCount);
        }
    }

    /**
     * @notice Slash a wallet identified as a Sybil attacker by the GNN oracle.
     *         Destroys their staked ETH (split: reporter fee + treasury).
     *         Burns the Humanity Credential and bans the wallet for BAN_DURATION.
     *
     * @param  wallet    The Sybil wallet to slash.
     * @param  reporter  Address that receives the slash reporter fee (could be
     *                   the oracle itself or a human whistleblower).
     */
    function slash(address wallet, address payable reporter)
        external
        nonReentrant
        onlyRole(ORACLE_ROLE)
        whenNotPaused
    {
        if (reporter == address(0)) revert InvalidAddress();

        Credential storage c = credentials[wallet];

        // Allow slashing of both Active and Suspended credentials
        require(
            c.status == CredentialStatus.Active ||
            c.status == CredentialStatus.Suspended,
            "SybilNet: wallet not slashable"
        );

        uint256 slashAmount = c.stakedAmount;

        // Update state BEFORE transfers (CEI pattern)
        c.status       = CredentialStatus.Revoked;
        c.stakedAmount = 0;
        c.slashedAt    = block.timestamp;
        totalStaked   -= slashAmount;
        totalSlashed  += slashAmount;

        emit WalletSlashed(wallet, slashAmount, 0, reporter);
        emit CredentialRevoked(wallet, "gnn_sybil_detection");

        // ── Distribute slashed funds ─────────────────────────────────────
        uint256 reporterFee = (slashAmount * slashReporterFeeBps) / 10_000;
        uint256 treasuryAmt = slashAmount - reporterFee;

        if (reporterFee > 0) {
            (bool ok1, ) = reporter.call{value: reporterFee}("");
            if (!ok1) revert TransferFailed();
        }
        if (treasuryAmt > 0) {
            (bool ok2, ) = treasury.call{value: treasuryAmt}("");
            if (!ok2) revert TransferFailed();
        }
    }

    /**
     * @notice Batch-slash multiple Sybil wallets in a single tx (gas efficient
     *         for large bot rings identified by the GNN).
     */
    function batchSlash(address[] calldata wallets, address payable reporter)
        external
        nonReentrant
        onlyRole(ORACLE_ROLE)
        whenNotPaused
    {
        if (reporter == address(0)) revert InvalidAddress();

        uint256 totalSlashBatch = 0;

        for (uint256 i = 0; i < wallets.length; i++) {
            Credential storage c = credentials[wallets[i]];
            if (
                c.status != CredentialStatus.Active &&
                c.status != CredentialStatus.Suspended
            ) continue;

            uint256 amt = c.stakedAmount;
            c.status       = CredentialStatus.Revoked;
            c.stakedAmount = 0;
            c.slashedAt    = block.timestamp;
            totalStaked   -= amt;
            totalSlashed  += amt;
            totalSlashBatch += amt;

            emit WalletSlashed(wallets[i], amt, 0, reporter);
            emit CredentialRevoked(wallets[i], "gnn_batch_slash");
        }

        // Single distribution for the whole batch
        uint256 reporterFee = (totalSlashBatch * slashReporterFeeBps) / 10_000;
        uint256 treasuryAmt = totalSlashBatch - reporterFee;

        if (reporterFee > 0) {
            (bool ok1, ) = reporter.call{value: reporterFee}("");
            if (!ok1) revert TransferFailed();
        }
        if (treasuryAmt > 0) {
            (bool ok2, ) = treasury.call{value: treasuryAmt}("");
            if (!ok2) revert TransferFailed();
        }
    }

    /**
     * @notice Lift a Suspension if the oracle re-evaluates a wallet as clean.
     */
    function liftSuspension(address wallet)
        external
        onlyRole(ORACLE_ROLE)
        whenNotPaused
    {
        Credential storage c = credentials[wallet];
        require(c.status == CredentialStatus.Suspended, "SybilNet: not suspended");
        c.status     = CredentialStatus.Active;
        c.sybilScore = 0;
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  ADMIN FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    function setMinStake(uint256 newMin) external onlyRole(DEFAULT_ADMIN_ROLE) {
        emit MinStakeUpdated(minStake, newMin);
        minStake = newMin;
    }

    function setTreasury(address payable newTreasury)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (newTreasury == address(0)) revert InvalidAddress();
        emit TreasuryUpdated(treasury, newTreasury);
        treasury = newTreasury;
    }

    function setSlashReporterFee(uint256 newBps)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (newBps > 3000) revert InvalidBps(newBps); // cap at 30%
        slashReporterFeeBps = newBps;
    }

    function pause()   external onlyRole(GUARDIAN_ROLE) { _pause(); }
    function unpause() external onlyRole(GUARDIAN_ROLE) { _unpause(); }

    // ═══════════════════════════════════════════════════════════════════════
    //  VIEW FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    /// @notice Returns true only if the wallet holds a currently Active credential.
    function isVerifiedHuman(address wallet) external view returns (bool) {
        return credentials[wallet].status == CredentialStatus.Active;
    }

    /// @notice Returns the current Sybil risk score (0–100) for a wallet.
    function getSybilScore(address wallet) external view returns (uint256) {
        return credentials[wallet].sybilScore;
    }

    /// @notice Returns the full credential struct for a wallet.
    function getCredential(address wallet)
        external
        view
        returns (Credential memory)
    {
        return credentials[wallet];
    }
}
