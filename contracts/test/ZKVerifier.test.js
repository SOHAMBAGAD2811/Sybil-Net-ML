const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ZKVerifier & SybilNet Integration", function () {
  let sybilNet, zkVerifier, owner, addr1, oracle;
  
  const mockProof = {
    pA: [1, 2],
    pB: [[3, 4], [5, 6]],
    pC: [7, 8],
    pubSignals: [70, 123456789, 0, 0] // threshold, walletCommitment, padding
  };

  beforeEach(async function () {
    [owner, addr1, oracle] = await ethers.getSigners();

    // Deploy ZKVerifier
    const ZKVerifier = await ethers.getContractFactory("ZKVerifier");
    zkVerifier = await ZKVerifier.deploy();

    // Deploy SybilNet
    const SybilNet = await ethers.getContractFactory("SybilNet");
    sybilNet = await SybilNet.deploy(owner.address);

    // Set ZKVerifier in SybilNet
    await sybilNet.setZKVerifier(await zkVerifier.getAddress());
  });

  it("Should deploy ZKVerifier successfully", async function () {
    expect(await zkVerifier.getAddress()).to.be.properAddress;
  });

  it("Should verify a mock valid humanity proof directly", async function () {
    const tx = await zkVerifier.verifyHumanityProof(
      mockProof.pA,
      mockProof.pB,
      mockProof.pC,
      mockProof.pubSignals
    );
    await tx.wait();

    // Check if event was emitted
    await expect(tx)
      .to.emit(zkVerifier, "ProofVerified")
      .withArgs(owner.address, mockProof.pubSignals[1], await ethers.provider.getBlock('latest').then(b => b.timestamp));
  });

  it("Should reject a replayed proof", async function () {
    await zkVerifier.verifyHumanityProof(
      mockProof.pA,
      mockProof.pB,
      mockProof.pC,
      mockProof.pubSignals
    );

    // Try again with the exact same proof
    await expect(
      zkVerifier.verifyHumanityProof(
        mockProof.pA,
        mockProof.pB,
        mockProof.pC,
        mockProof.pubSignals
      )
    ).to.be.revertedWithCustomError(zkVerifier, "ProofAlreadyUsed");
  });

  it("Should allow SybilNet to verify an anonymous proof", async function () {
    const tx = await sybilNet.connect(addr1).verifyAnonymous(
      mockProof.pA,
      mockProof.pB,
      mockProof.pC,
      mockProof.pubSignals
    );

    await expect(tx).to.emit(sybilNet, "AnonymousCredentialVerified");
  });

  it("Should prevent SybilNet from verifying a replayed proof", async function () {
    await sybilNet.connect(addr1).verifyAnonymous(
      mockProof.pA,
      mockProof.pB,
      mockProof.pC,
      mockProof.pubSignals
    );

    await expect(
      sybilNet.connect(addr1).verifyAnonymous(
        mockProof.pA,
        mockProof.pB,
        mockProof.pC,
        mockProof.pubSignals
      )
    ).to.be.revertedWithCustomError(zkVerifier, "ProofAlreadyUsed");
  });

  it("Should revert in SybilNet if ZKVerifier is not set", async function () {
    const SybilNet2 = await ethers.getContractFactory("SybilNet");
    const sybilNet2 = await SybilNet2.deploy(owner.address);

    await expect(
      sybilNet2.verifyAnonymous(
        mockProof.pA,
        mockProof.pB,
        mockProof.pC,
        mockProof.pubSignals
      )
    ).to.be.revertedWithCustomError(sybilNet2, "InvalidAddress");
  });
});
