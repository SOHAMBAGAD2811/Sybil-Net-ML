const { expect }        = require("chai");
const { ethers }        = require("hardhat");
const { loadFixture }   = require("@nomicfoundation/hardhat-toolbox/network-helpers");

// ─── Fixture ──────────────────────────────────────────────────────────────────
async function deploySybilNetFixture() {
  const [admin, oracle, user1, user2, user3, treasury, reporter] =
    await ethers.getSigners();

  const SybilNet = await ethers.getContractFactory("SybilNet");
  const sybilNet = await SybilNet.deploy(treasury.address);
  await sybilNet.waitForDeployment();

  // Grant roles
  const ORACLE_ROLE   = await sybilNet.ORACLE_ROLE();
  const GUARDIAN_ROLE = await sybilNet.GUARDIAN_ROLE();
  await sybilNet.grantRole(ORACLE_ROLE,   oracle.address);
  await sybilNet.grantRole(GUARDIAN_ROLE, admin.address);

  const MIN_STAKE = await sybilNet.minStake(); // 0.01 ETH

  return { sybilNet, admin, oracle, user1, user2, user3, treasury, reporter, MIN_STAKE, ORACLE_ROLE };
}

// ─────────────────────────────────────────────────────────────────────────────
describe("SybilNet", function () {

  // ── Deployment ──────────────────────────────────────────────────────────
  describe("Deployment", function () {
    it("sets the treasury correctly", async function () {
      const { sybilNet, treasury } = await loadFixture(deploySybilNetFixture);
      expect(await sybilNet.treasury()).to.equal(treasury.address);
    });

    it("sets minStake to 0.01 ETH", async function () {
      const { sybilNet } = await loadFixture(deploySybilNetFixture);
      expect(await sybilNet.minStake()).to.equal(ethers.parseEther("0.01"));
    });

    it("grants DEFAULT_ADMIN_ROLE to deployer", async function () {
      const { sybilNet, admin } = await loadFixture(deploySybilNetFixture);
      const ADMIN = await sybilNet.DEFAULT_ADMIN_ROLE();
      expect(await sybilNet.hasRole(ADMIN, admin.address)).to.be.true;
    });
  });

  // ── Minting ─────────────────────────────────────────────────────────────
  describe("mintCredential()", function () {
    it("mints a credential when stake >= minStake", async function () {
      const { sybilNet, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await expect(sybilNet.connect(user1).mintCredential({ value: MIN_STAKE }))
        .to.emit(sybilNet, "CredentialMinted")
        .withArgs(user1.address, MIN_STAKE, await ethers.provider.getBlock("latest").then(b => b?.timestamp + 1));

      expect(await sybilNet.isVerifiedHuman(user1.address)).to.be.true;
    });

    it("reverts when stake is below minimum", async function () {
      const { sybilNet, user1 } = await loadFixture(deploySybilNetFixture);
      const tooLow = ethers.parseEther("0.001");
      await expect(
        sybilNet.connect(user1).mintCredential({ value: tooLow })
      ).to.be.revertedWithCustomError(sybilNet, "InsufficientStake");
    });

    it("reverts when user already has an active credential", async function () {
      const { sybilNet, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await expect(
        sybilNet.connect(user1).mintCredential({ value: MIN_STAKE })
      ).to.be.revertedWithCustomError(sybilNet, "CredentialAlreadyActive");
    });

    it("increases totalStaked by the staked amount", async function () {
      const { sybilNet, user1, user2, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await sybilNet.connect(user2).mintCredential({ value: MIN_STAKE });
      expect(await sybilNet.totalStaked()).to.equal(MIN_STAKE * 2n);
    });
  });

  // ── Score updates ────────────────────────────────────────────────────────
  describe("updateSybilScore()", function () {
    it("updates score and emits event", async function () {
      const { sybilNet, oracle, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await expect(sybilNet.connect(oracle).updateSybilScore(user1.address, 45))
        .to.emit(sybilNet, "OracleScoreUpdated")
        .withArgs(user1.address, 0, 45);
      expect(await sybilNet.getSybilScore(user1.address)).to.equal(45);
    });

    it("auto-suspends wallet when score >= 70", async function () {
      const { sybilNet, oracle, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await expect(sybilNet.connect(oracle).updateSybilScore(user1.address, 75))
        .to.emit(sybilNet, "SybilWarning");

      const cred = await sybilNet.getCredential(user1.address);
      expect(cred.status).to.equal(2); // Suspended = 2
    });

    it("reverts if score > 100", async function () {
      const { sybilNet, oracle, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await expect(
        sybilNet.connect(oracle).updateSybilScore(user1.address, 101)
      ).to.be.revertedWithCustomError(sybilNet, "ScoreOutOfRange");
    });

    it("reverts if caller is not oracle", async function () {
      const { sybilNet, user1, user2, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await expect(
        sybilNet.connect(user2).updateSybilScore(user1.address, 50)
      ).to.be.revertedWithCustomError(sybilNet, "AccessControlUnauthorizedAccount");
    });
  });

  // ── Slashing ─────────────────────────────────────────────────────────────
  describe("slash()", function () {
    it("slashes the stake and revokes credential", async function () {
      const { sybilNet, oracle, user1, treasury, reporter, MIN_STAKE } =
        await loadFixture(deploySybilNetFixture);

      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });

      const treasuryBefore  = await ethers.provider.getBalance(treasury.address);
      const reporterBefore  = await ethers.provider.getBalance(reporter.address);

      await expect(sybilNet.connect(oracle).slash(user1.address, reporter.address))
        .to.emit(sybilNet, "WalletSlashed")
        .to.emit(sybilNet, "CredentialRevoked");

      // Credential is revoked
      expect(await sybilNet.isVerifiedHuman(user1.address)).to.be.false;
      const cred = await sybilNet.getCredential(user1.address);
      expect(cred.status).to.equal(3); // Revoked = 3
      expect(cred.stakedAmount).to.equal(0);

      // Funds distributed (10% reporter, 90% treasury)
      const reporterFee = MIN_STAKE * 1000n / 10000n;
      const treasuryAmt = MIN_STAKE - reporterFee;

      expect(await ethers.provider.getBalance(treasury.address))
        .to.equal(treasuryBefore + treasuryAmt);
      expect(await ethers.provider.getBalance(reporter.address))
        .to.equal(reporterBefore + reporterFee);
    });

    it("totalSlashed increases correctly", async function () {
      const { sybilNet, oracle, user1, reporter, MIN_STAKE } =
        await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await sybilNet.connect(oracle).slash(user1.address, reporter.address);
      expect(await sybilNet.totalSlashed()).to.equal(MIN_STAKE);
    });

    it("reverts if wallet has no active credential", async function () {
      const { sybilNet, oracle, user1, reporter } = await loadFixture(deploySybilNetFixture);
      await expect(
        sybilNet.connect(oracle).slash(user1.address, reporter.address)
      ).to.be.revertedWith("SybilNet: wallet not slashable");
    });
  });

  // ── Batch slash ──────────────────────────────────────────────────────────
  describe("batchSlash()", function () {
    it("slashes multiple wallets in one tx", async function () {
      const { sybilNet, oracle, user1, user2, user3, reporter, MIN_STAKE } =
        await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await sybilNet.connect(user2).mintCredential({ value: MIN_STAKE });
      await sybilNet.connect(user3).mintCredential({ value: MIN_STAKE });

      await sybilNet.connect(oracle).batchSlash(
        [user1.address, user2.address, user3.address],
        reporter.address
      );

      expect(await sybilNet.isVerifiedHuman(user1.address)).to.be.false;
      expect(await sybilNet.isVerifiedHuman(user2.address)).to.be.false;
      expect(await sybilNet.isVerifiedHuman(user3.address)).to.be.false;
      expect(await sybilNet.totalSlashed()).to.equal(MIN_STAKE * 3n);
    });
  });

  // ── Voluntary withdrawal ─────────────────────────────────────────────────
  describe("withdrawStake()", function () {
    it("returns stake to user and revokes credential", async function () {
      const { sybilNet, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });

      const balBefore = await ethers.provider.getBalance(user1.address);
      const tx = await sybilNet.connect(user1).withdrawStake();
      const receipt = await tx.wait();
      const gasCost = receipt.gasUsed * tx.gasPrice;

      expect(await ethers.provider.getBalance(user1.address))
        .to.be.closeTo(balBefore + MIN_STAKE - gasCost, ethers.parseEther("0.0001"));

      expect(await sybilNet.isVerifiedHuman(user1.address)).to.be.false;
    });
  });

  // ── Ban mechanism ────────────────────────────────────────────────────────
  describe("Ban mechanism", function () {
    it("prevents slashed wallet from re-minting within ban period", async function () {
      const { sybilNet, oracle, user1, reporter, MIN_STAKE } =
        await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
      await sybilNet.connect(oracle).slash(user1.address, reporter.address);

      await expect(
        sybilNet.connect(user1).mintCredential({ value: MIN_STAKE })
      ).to.be.revertedWithCustomError(sybilNet, "WalletBanned");
    });
  });

  // ── Pause ────────────────────────────────────────────────────────────────
  describe("Emergency pause", function () {
    it("blocks mintCredential when paused", async function () {
      const { sybilNet, admin, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(admin).pause();
      await expect(
        sybilNet.connect(user1).mintCredential({ value: MIN_STAKE })
      ).to.be.revertedWithCustomError(sybilNet, "EnforcedPause");
    });

    it("resumes after unpause", async function () {
      const { sybilNet, admin, user1, MIN_STAKE } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(admin).pause();
      await sybilNet.connect(admin).unpause();
      await expect(
        sybilNet.connect(user1).mintCredential({ value: MIN_STAKE })
      ).to.emit(sybilNet, "CredentialMinted");
    });
  });

  // ── Admin controls ───────────────────────────────────────────────────────
  describe("Admin controls", function () {
    it("admin can update minStake", async function () {
      const { sybilNet, admin } = await loadFixture(deploySybilNetFixture);
      const newMin = ethers.parseEther("0.05");
      await expect(sybilNet.connect(admin).setMinStake(newMin))
        .to.emit(sybilNet, "MinStakeUpdated");
      expect(await sybilNet.minStake()).to.equal(newMin);
    });

    it("admin can update slash reporter fee", async function () {
      const { sybilNet, admin } = await loadFixture(deploySybilNetFixture);
      await sybilNet.connect(admin).setSlashReporterFee(500); // 5%
      expect(await sybilNet.slashReporterFeeBps()).to.equal(500);
    });

    it("reverts if slash reporter fee exceeds 30%", async function () {
      const { sybilNet, admin } = await loadFixture(deploySybilNetFixture);
      await expect(
        sybilNet.connect(admin).setSlashReporterFee(3001)
      ).to.be.revertedWithCustomError(sybilNet, "InvalidBps");
    });
  });
});
