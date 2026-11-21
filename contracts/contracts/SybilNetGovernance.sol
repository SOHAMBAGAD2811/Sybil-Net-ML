// SPDX-License-Identifier: MIT
pragma solidity ^0.8.27;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title  ISybilNetGov
 * @notice Minimal interface to the core SybilNet contract for governance ops.
 */
interface ISybilNetGov {
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
    function getCredential(address wallet) external view returns (Credential memory);
    function liftSuspension(address wallet) external;
}

/**
 * @title  SybilNetGovernance
 * @author Sybil-Net Project
 * @notice On-chain Governance & DAO (Week 8)
 *
 *         Decentralised dispute resolution and protocol parameter governance
 *         gated by the Humanity Credential.  Only verified humans may propose
 *         and vote — one-human-one-vote.
 *
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │                       Governance Lifecycle                             │
 * │                                                                        │
 * │   createProposal()              castVote()             executeProposal()│
 * │        │                           │                        │          │
 * │        ▼                           ▼                        ▼          │
 * │   ┌──────────┐  time  ┌──────────┐  end   ┌───────────┐  delay  ┌────┐│
 * │   │ Pending  │ ──────►│  Active  │ ──────►│ Succeeded │ ──────►│Exec││
 * │   └──────────┘        └──────────┘        └───────────┘        └────┘│
 * │                            │                   │                      │
 * │                            │ votes              │ expired              │
 * │                            ▼                   ▼                      │
 * │                       ┌──────────┐       ┌──────────┐                │
 * │                       │ Defeated │       │ Expired  │                │
 * │                       └──────────┘       └──────────┘                │
 * │                                                                        │
 * │   Proposal Types:                                                      │
 * │     SLASH_APPEAL     — Dispute a slash; reinstates credential          │
 * │     PARAMETER_CHANGE — Update protocol config (minStake, fees, etc.)  │
 * │     ROLE_CHANGE      — Grant or revoke protocol roles                 │
 * └─────────────────────────────────────────────────────────────────────────┘
 *
 * Roles:
 *   DEFAULT_ADMIN_ROLE — protocol admin (parameter updates, emergency)
 */
contract SybilNetGovernance is AccessControl, ReentrancyGuard, Pausable {

    // ─── Enums ────────────────────────────────────────────────────────────
    enum ProposalType  { SLASH_APPEAL, PARAMETER_CHANGE, ROLE_CHANGE }
    enum VoteType      { FOR, AGAINST, ABSTAIN }
    enum ProposalState { Pending, Active, Succeeded, Defeated, Queued, Executed, Expired, Cancelled }

    // ─── Structs ──────────────────────────────────────────────────────────
    struct Proposal {
        uint256       id;
        address       proposer;
        ProposalType  proposalType;
        string        description;
        uint256       votesFor;
        uint256       votesAgainst;
        uint256       votesAbstain;
        uint256       startTime;
        uint256       endTime;
        address       executionTarget;
        bytes         executionCalldata;
        bool          executed;
        bool          cancelled;
    }

    // ─── State ────────────────────────────────────────────────────────────
    ISybilNetGov public sybilNet;

    uint256 public votingPeriod   = 3 days;
    uint256 public executionDelay = 1 days;
    uint256 public quorumBps      = 1000;       // 10% of credential holders

    /// Admin-managed count of active credential holders (for quorum calc)
    uint256 public credentialHolderCount;

    uint256 public proposalCount;

    mapping(uint256 => Proposal) public proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    // ─── Events ───────────────────────────────────────────────────────────
    event ProposalCreated(
        uint256 indexed proposalId,
        address indexed proposer,
        ProposalType proposalType,
        string description
    );
    event VoteCast(
        uint256 indexed proposalId,
        address indexed voter,
        VoteType vote
    );
    event ProposalExecuted(uint256 indexed proposalId);
    event ProposalCancelled(uint256 indexed proposalId);
    event VotingPeriodUpdated(uint256 oldPeriod, uint256 newPeriod);
    event ExecutionDelayUpdated(uint256 oldDelay, uint256 newDelay);
    event QuorumUpdated(uint256 oldBps, uint256 newBps);
    event CredentialHolderCountUpdated(uint256 oldCount, uint256 newCount);

    // ─── Errors ───────────────────────────────────────────────────────────
    error NotVerifiedHuman();
    error ProposalNotActive();
    error AlreadyVoted();
    error ProposalNotExecutable();
    error InvalidProposal();
    error ExecutionFailed();
    error NotProposerOrAdmin();
    error QuorumNotReached();
    error VotingNotEnded();
    error InvalidAddress();
    error InvalidValue();

    // ─── Modifiers ────────────────────────────────────────────────────────
    modifier onlyVerifiedHuman() {
        if (!sybilNet.isVerifiedHuman(msg.sender)) revert NotVerifiedHuman();
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────
    constructor(address _sybilNet) {
        if (_sybilNet == address(0)) revert InvalidAddress();
        sybilNet = ISybilNetGov(_sybilNet);

        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  PROPOSAL MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Create a new governance proposal.
     * @param  proposalType   Type of proposal (SLASH_APPEAL, PARAMETER_CHANGE, ROLE_CHANGE).
     * @param  description    Human-readable description of the proposal.
     * @param  target         Contract address to call if proposal is executed.
     *                        For SLASH_APPEAL: the SybilNet contract address.
     *                        For PARAMETER_CHANGE / ROLE_CHANGE: the target contract.
     * @param  data           ABI-encoded calldata for the execution call.
     *                        For SLASH_APPEAL: abi.encodeWithSignature("liftSuspension(address)", wallet)
     */
    function createProposal(
        ProposalType proposalType,
        string calldata description,
        address target,
        bytes calldata data
    )
        external
        whenNotPaused
        onlyVerifiedHuman
        returns (uint256)
    {
        if (bytes(description).length == 0) revert InvalidProposal();
        if (proposalType != ProposalType.SLASH_APPEAL && target == address(0))
            revert InvalidAddress();

        // For SLASH_APPEAL, default target to SybilNet if not specified
        address execTarget = target;
        if (proposalType == ProposalType.SLASH_APPEAL && target == address(0)) {
            execTarget = address(sybilNet);
        }

        uint256 id = proposalCount++;

        proposals[id] = Proposal({
            id:                id,
            proposer:          msg.sender,
            proposalType:      proposalType,
            description:       description,
            votesFor:          0,
            votesAgainst:      0,
            votesAbstain:      0,
            startTime:         block.timestamp,
            endTime:           block.timestamp + votingPeriod,
            executionTarget:   execTarget,
            executionCalldata: data,
            executed:          false,
            cancelled:         false
        });

        emit ProposalCreated(id, msg.sender, proposalType, description);
        return id;
    }

    /**
     * @notice Cast a vote on an active proposal.
     * @param  proposalId  The proposal to vote on.
     * @param  vote        FOR, AGAINST, or ABSTAIN.
     */
    function castVote(uint256 proposalId, VoteType vote)
        external
        whenNotPaused
        onlyVerifiedHuman
    {
        if (getProposalState(proposalId) != ProposalState.Active)
            revert ProposalNotActive();
        if (hasVoted[proposalId][msg.sender])
            revert AlreadyVoted();

        hasVoted[proposalId][msg.sender] = true;

        Proposal storage p = proposals[proposalId];

        if (vote == VoteType.FOR) {
            p.votesFor++;
        } else if (vote == VoteType.AGAINST) {
            p.votesAgainst++;
        } else {
            p.votesAbstain++;
        }

        emit VoteCast(proposalId, msg.sender, vote);
    }

    /**
     * @notice Execute a succeeded proposal after the execution delay.
     * @param  proposalId  The proposal to execute.
     */
    function executeProposal(uint256 proposalId)
        external
        nonReentrant
        whenNotPaused
    {
        ProposalState state = getProposalState(proposalId);
        if (state != ProposalState.Succeeded) revert ProposalNotExecutable();

        Proposal storage p = proposals[proposalId];

        // Check execution delay has passed
        if (block.timestamp < p.endTime + executionDelay)
            revert VotingNotEnded();

        // Check quorum
        uint256 totalVotes = p.votesFor + p.votesAgainst + p.votesAbstain;
        uint256 requiredVotes = (credentialHolderCount * quorumBps) / 10_000;
        if (requiredVotes > 0 && totalVotes < requiredVotes)
            revert QuorumNotReached();

        p.executed = true;

        emit ProposalExecuted(proposalId);

        // Execute the proposal's calldata on the target
        if (p.executionTarget != address(0) && p.executionCalldata.length > 0) {
            (bool success, ) = p.executionTarget.call(p.executionCalldata);
            if (!success) revert ExecutionFailed();
        }
    }

    /**
     * @notice Cancel a proposal. Only the proposer or an admin may cancel.
     * @param  proposalId  The proposal to cancel.
     */
    function cancelProposal(uint256 proposalId) external whenNotPaused {
        Proposal storage p = proposals[proposalId];

        if (msg.sender != p.proposer && !hasRole(DEFAULT_ADMIN_ROLE, msg.sender))
            revert NotProposerOrAdmin();

        ProposalState state = getProposalState(proposalId);
        if (state == ProposalState.Executed || state == ProposalState.Cancelled)
            revert InvalidProposal();

        p.cancelled = true;

        emit ProposalCancelled(proposalId);
    }

    // ═══════════════════════════════════════════════════════════════════════
    //  ADMIN FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    function setVotingPeriod(uint256 newPeriod)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (newPeriod == 0) revert InvalidValue();
        emit VotingPeriodUpdated(votingPeriod, newPeriod);
        votingPeriod = newPeriod;
    }

    function setExecutionDelay(uint256 newDelay)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        emit ExecutionDelayUpdated(executionDelay, newDelay);
        executionDelay = newDelay;
    }

    function setQuorumBps(uint256 newBps)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (newBps > 10_000) revert InvalidValue();
        emit QuorumUpdated(quorumBps, newBps);
        quorumBps = newBps;
    }

    function setCredentialHolderCount(uint256 count)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        emit CredentialHolderCountUpdated(credentialHolderCount, count);
        credentialHolderCount = count;
    }

    function setSybilNet(address _sybilNet)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        if (_sybilNet == address(0)) revert InvalidAddress();
        sybilNet = ISybilNetGov(_sybilNet);
    }

    function pause()   external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    // ═══════════════════════════════════════════════════════════════════════
    //  VIEW FUNCTIONS
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * @notice Compute the current state of a proposal dynamically.
     */
    function getProposalState(uint256 proposalId) public view returns (ProposalState) {
        if (proposalId >= proposalCount) revert InvalidProposal();

        Proposal storage p = proposals[proposalId];

        if (p.cancelled) return ProposalState.Cancelled;
        if (p.executed)  return ProposalState.Executed;

        // Voting is still active
        if (block.timestamp < p.endTime) return ProposalState.Active;

        // Voting has ended — determine outcome
        if (p.votesFor <= p.votesAgainst) return ProposalState.Defeated;

        // votesFor > votesAgainst — proposal succeeded
        // Check if execution window has expired (2x execution delay beyond voting end)
        if (block.timestamp > p.endTime + executionDelay * 2) {
            return ProposalState.Expired;
        }

        return ProposalState.Succeeded;
    }

    /**
     * @notice Return the full proposal struct.
     */
    function getProposal(uint256 proposalId)
        external
        view
        returns (Proposal memory)
    {
        if (proposalId >= proposalCount) revert InvalidProposal();
        return proposals[proposalId];
    }

    /**
     * @notice Return the total number of votes cast on a proposal.
     */
    function getTotalVotes(uint256 proposalId)
        external
        view
        returns (uint256)
    {
        Proposal storage p = proposals[proposalId];
        return p.votesFor + p.votesAgainst + p.votesAbstain;
    }

    /**
     * @notice Return the quorum threshold (number of votes needed).
     */
    function getQuorumThreshold() external view returns (uint256) {
        return (credentialHolderCount * quorumBps) / 10_000;
    }
}
