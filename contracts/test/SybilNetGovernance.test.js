const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SybilNetGovernance", function () {
  let sybilNet, governance;
  let deployer, user1, user2, user3, nonHolder, treasury;

  const MIN_STAKE = ethers.parseEther("0.01");
  const THREE_DAYS = 3 * 24 * 60 * 60;
  const ONE_DAY = 24 * 60 * 60;

  // Enums
  const ProposalType = { SLASH_APPEAL: 0, PARAMETER_CHANGE: 1, ROLE_CHANGE: 2 };
  const VoteType = { FOR: 0, AGAINST: 1, ABSTAIN: 2 };
  const ProposalState = {
    Pending: 0, Active: 1, Succeeded: 2, Defeated: 3,
    Queued: 4, Executed: 5, Expired: 6, Cancelled: 7,
  };

  async function advanceTime(seconds) {
    await ethers.provider.send("evm_increaseTime", [seconds]);
    await ethers.provider.send("evm_mine", []);
  }

  beforeEach(async function () {
    [deployer, user1, user2, user3, nonHolder, treasury] =
      await ethers.getSigners();

    // Deploy core SybilNet
    const SybilNet = await ethers.getContractFactory("SybilNet");
    sybilNet = await SybilNet.deploy(treasury.address);
    await sybilNet.waitForDeployment();

    // Grant ORACLE_ROLE to deployer for test setup
    const ORACLE_ROLE = await sybilNet.ORACLE_ROLE();
    await sybilNet.grantRole(ORACLE_ROLE, deployer.address);

    // Deploy Governance
    const Governance = await ethers.getContractFactory("SybilNetGovernance");
    governance = await Governance.deploy(await sybilNet.getAddress());
    await governance.waitForDeployment();

    // Grant ORACLE_ROLE to governance contract so it can call liftSuspension()
    await sybilNet.grantRole(ORACLE_ROLE, await governance.getAddress());

    // Mint credentials for user1, user2, user3
    await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
    await sybilNet.connect(user2).mintCredential({ value: MIN_STAKE });
    await sybilNet.connect(user3).mintCredential({ value: MIN_STAKE });

    // Set credential holder count for quorum calculation
    await governance.setCredentialHolderCount(3);
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  DEPLOYMENT
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Deployment", function () {
    it("should set the correct SybilNet reference", async function () {
      expect(await governance.sybilNet()).to.equal(
        await sybilNet.getAddress()
      );
    });

    it("should set default governance parameters", async function () {
      expect(await governance.votingPeriod()).to.equal(THREE_DAYS);
      expect(await governance.executionDelay()).to.equal(ONE_DAY);
      expect(await governance.quorumBps()).to.equal(1000);
    });

    it("should grant DEFAULT_ADMIN_ROLE to deployer", async function () {
      const ADMIN_ROLE = await governance.DEFAULT_ADMIN_ROLE();
      expect(await governance.hasRole(ADMIN_ROLE, deployer.address)).to.be.true;
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  PROPOSAL CREATION
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Proposal Creation", function () {
    it("should create a SLASH_APPEAL proposal", async function () {
      const calldata = sybilNet.interface.encodeFunctionData(
        "liftSuspension",
        [user1.address]
      );

      const tx = await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "Appeal slash for user1",
          await sybilNet.getAddress(),
          calldata
        );

      await expect(tx)
        .to.emit(governance, "ProposalCreated")
        .withArgs(0, user1.address, ProposalType.SLASH_APPEAL, "Appeal slash for user1");

      expect(await governance.proposalCount()).to.equal(1);
    });

    it("should create a PARAMETER_CHANGE proposal", async function () {
      const calldata = sybilNet.interface.encodeFunctionData("setMinStake", [
        ethers.parseEther("0.02"),
      ]);

      await governance
        .connect(user2)
        .createProposal(
          ProposalType.PARAMETER_CHANGE,
          "Increase min stake to 0.02 ETH",
          await sybilNet.getAddress(),
          calldata
        );

      const proposal = await governance.getProposal(0);
      expect(proposal.proposalType).to.equal(ProposalType.PARAMETER_CHANGE);
      expect(proposal.proposer).to.equal(user2.address);
    });

    it("should revert if caller has no credential", async function () {
      await expect(
        governance
          .connect(nonHolder)
          .createProposal(
            ProposalType.SLASH_APPEAL,
            "Some proposal",
            await sybilNet.getAddress(),
            "0x"
          )
      ).to.be.revertedWithCustomError(governance, "NotVerifiedHuman");
    });

    it("should revert with empty description", async function () {
      await expect(
        governance
          .connect(user1)
          .createProposal(
            ProposalType.SLASH_APPEAL,
            "",
            await sybilNet.getAddress(),
            "0x"
          )
      ).to.be.revertedWithCustomError(governance, "InvalidProposal");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  VOTING
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Voting", function () {
    beforeEach(async function () {
      // Create a proposal to vote on
      await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "Test proposal for voting",
          await sybilNet.getAddress(),
          "0x"
        );
    });

    it("should cast a FOR vote", async function () {
      const tx = await governance
        .connect(user1)
        .castVote(0, VoteType.FOR);

      await expect(tx)
        .to.emit(governance, "VoteCast")
        .withArgs(0, user1.address, VoteType.FOR);

      const proposal = await governance.getProposal(0);
      expect(proposal.votesFor).to.equal(1);
    });

    it("should cast an AGAINST vote", async function () {
      await governance.connect(user2).castVote(0, VoteType.AGAINST);

      const proposal = await governance.getProposal(0);
      expect(proposal.votesAgainst).to.equal(1);
    });

    it("should cast an ABSTAIN vote", async function () {
      await governance.connect(user3).castVote(0, VoteType.ABSTAIN);

      const proposal = await governance.getProposal(0);
      expect(proposal.votesAbstain).to.equal(1);
    });

    it("should revert on double vote", async function () {
      await governance.connect(user1).castVote(0, VoteType.FOR);

      await expect(
        governance.connect(user1).castVote(0, VoteType.AGAINST)
      ).to.be.revertedWithCustomError(governance, "AlreadyVoted");
    });

    it("should revert if caller has no credential", async function () {
      await expect(
        governance.connect(nonHolder).castVote(0, VoteType.FOR)
      ).to.be.revertedWithCustomError(governance, "NotVerifiedHuman");
    });

    it("should revert after voting period ends", async function () {
      await advanceTime(THREE_DAYS + 1);

      await expect(
        governance.connect(user1).castVote(0, VoteType.FOR)
      ).to.be.revertedWithCustomError(governance, "ProposalNotActive");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  PROPOSAL STATE
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Proposal State", function () {
    beforeEach(async function () {
      await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "State test proposal",
          await sybilNet.getAddress(),
          "0x"
        );
    });

    it("should be Active immediately after creation", async function () {
      expect(await governance.getProposalState(0)).to.equal(
        ProposalState.Active
      );
    });

    it("should transition to Succeeded when votesFor > votesAgainst after voting ends", async function () {
      await governance.connect(user1).castVote(0, VoteType.FOR);
      await governance.connect(user2).castVote(0, VoteType.FOR);

      await advanceTime(THREE_DAYS + 1);

      expect(await governance.getProposalState(0)).to.equal(
        ProposalState.Succeeded
      );
    });

    it("should transition to Defeated when votesAgainst >= votesFor after voting ends", async function () {
      await governance.connect(user1).castVote(0, VoteType.AGAINST);
      await governance.connect(user2).castVote(0, VoteType.AGAINST);

      await advanceTime(THREE_DAYS + 1);

      expect(await governance.getProposalState(0)).to.equal(
        ProposalState.Defeated
      );
    });

    it("should transition to Expired after 2x execution delay past voting end", async function () {
      await governance.connect(user1).castVote(0, VoteType.FOR);
      await governance.connect(user2).castVote(0, VoteType.FOR);

      // Advance past voting + 2x execution delay
      await advanceTime(THREE_DAYS + ONE_DAY * 2 + 1);

      expect(await governance.getProposalState(0)).to.equal(
        ProposalState.Expired
      );
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  EXECUTION
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Execution", function () {
    it("should execute a succeeded SLASH_APPEAL and lift suspension", async function () {
      // Suspend user3 via oracle
      await sybilNet.updateSybilScore(user3.address, 80);
      const cred = await sybilNet.getCredential(user3.address);
      expect(cred.status).to.equal(2); // Suspended

      // Create appeal proposal
      const calldata = sybilNet.interface.encodeFunctionData(
        "liftSuspension",
        [user3.address]
      );
      await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "Appeal: user3 is not a bot",
          await sybilNet.getAddress(),
          calldata
        );

      // Vote in favour
      await governance.connect(user1).castVote(0, VoteType.FOR);
      await governance.connect(user2).castVote(0, VoteType.FOR);

      // Advance past voting + execution delay
      await advanceTime(THREE_DAYS + ONE_DAY + 1);

      // Execute
      const tx = await governance.executeProposal(0);
      await expect(tx).to.emit(governance, "ProposalExecuted").withArgs(0);

      // Verify suspension was lifted
      const credAfter = await sybilNet.getCredential(user3.address);
      expect(credAfter.status).to.equal(1); // Active
      expect(credAfter.sybilScore).to.equal(0);
    });

    it("should execute a PARAMETER_CHANGE proposal", async function () {
      // Grant admin role to governance so it can call setMinStake
      const ADMIN_ROLE = await sybilNet.DEFAULT_ADMIN_ROLE();
      await sybilNet.grantRole(ADMIN_ROLE, await governance.getAddress());

      const newStake = ethers.parseEther("0.05");
      const calldata = sybilNet.interface.encodeFunctionData("setMinStake", [
        newStake,
      ]);

      await governance
        .connect(user1)
        .createProposal(
          ProposalType.PARAMETER_CHANGE,
          "Raise min stake to 0.05 ETH",
          await sybilNet.getAddress(),
          calldata
        );

      await governance.connect(user1).castVote(0, VoteType.FOR);
      await governance.connect(user2).castVote(0, VoteType.FOR);

      await advanceTime(THREE_DAYS + ONE_DAY + 1);
      await governance.executeProposal(0);

      expect(await sybilNet.minStake()).to.equal(newStake);
    });

    it("should revert execution before delay passes", async function () {
      await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "Early exec test",
          await sybilNet.getAddress(),
          "0x"
        );

      await governance.connect(user1).castVote(0, VoteType.FOR);
      await governance.connect(user2).castVote(0, VoteType.FOR);

      // Only advance past voting, not past execution delay
      await advanceTime(THREE_DAYS + 1);

      await expect(
        governance.executeProposal(0)
      ).to.be.revertedWithCustomError(governance, "VotingNotEnded");
    });

    it("should revert execution of a defeated proposal", async function () {
      await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "Defeated proposal test",
          await sybilNet.getAddress(),
          "0x"
        );

      await governance.connect(user1).castVote(0, VoteType.AGAINST);
      await governance.connect(user2).castVote(0, VoteType.AGAINST);

      await advanceTime(THREE_DAYS + ONE_DAY + 1);

      await expect(
        governance.executeProposal(0)
      ).to.be.revertedWithCustomError(governance, "ProposalNotExecutable");
    });

    it("should revert if quorum is not met", async function () {
      // Set high holder count so 1 vote is below 10% quorum
      await governance.setCredentialHolderCount(100);

      await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "Quorum test proposal",
          await sybilNet.getAddress(),
          "0x"
        );

      // Only 1 vote — below 10% of 100
      await governance.connect(user1).castVote(0, VoteType.FOR);

      await advanceTime(THREE_DAYS + ONE_DAY + 1);

      await expect(
        governance.executeProposal(0)
      ).to.be.revertedWithCustomError(governance, "QuorumNotReached");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  CANCELLATION
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Cancellation", function () {
    beforeEach(async function () {
      await governance
        .connect(user1)
        .createProposal(
          ProposalType.SLASH_APPEAL,
          "Cancellation test",
          await sybilNet.getAddress(),
          "0x"
        );
    });

    it("should allow proposer to cancel", async function () {
      const tx = await governance.connect(user1).cancelProposal(0);
      await expect(tx).to.emit(governance, "ProposalCancelled").withArgs(0);

      expect(await governance.getProposalState(0)).to.equal(
        ProposalState.Cancelled
      );
    });

    it("should allow admin to cancel", async function () {
      await governance.connect(deployer).cancelProposal(0);
      expect(await governance.getProposalState(0)).to.equal(
        ProposalState.Cancelled
      );
    });

    it("should revert cancellation by random user", async function () {
      await expect(
        governance.connect(user2).cancelProposal(0)
      ).to.be.revertedWithCustomError(governance, "NotProposerOrAdmin");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  ADMIN
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Admin", function () {
    it("should update voting period", async function () {
      const newPeriod = 7 * ONE_DAY; // 7 days
      const tx = await governance.setVotingPeriod(newPeriod);

      await expect(tx)
        .to.emit(governance, "VotingPeriodUpdated")
        .withArgs(THREE_DAYS, newPeriod);

      expect(await governance.votingPeriod()).to.equal(newPeriod);
    });

    it("should update quorum", async function () {
      const tx = await governance.setQuorumBps(2000); // 20%

      await expect(tx)
        .to.emit(governance, "QuorumUpdated")
        .withArgs(1000, 2000);

      expect(await governance.quorumBps()).to.equal(2000);
    });

    it("should update execution delay", async function () {
      const newDelay = 2 * ONE_DAY;
      await governance.setExecutionDelay(newDelay);
      expect(await governance.executionDelay()).to.equal(newDelay);
    });

    it("should revert admin calls from non-admin", async function () {
      await expect(
        governance.connect(user1).setVotingPeriod(100)
      ).to.be.reverted;
    });
  });
});
