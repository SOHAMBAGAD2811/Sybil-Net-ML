const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("SybilNetBridge", function () {
  let sybilNet, bridge;
  let deployer, operator, user1, user2, treasury;
  let oracleWallet; // signer for bridge credential signatures

  const MIN_STAKE = ethers.parseEther("0.01");
  const POLYGON_CHAIN_ID = 137;
  const ARBITRUM_CHAIN_ID = 42161;
  const BASE_CHAIN_ID = 8453;

  /**
   * Helper: generate an oracle signature for mintBridgedCredential.
   */
  async function signBridgeMessage(wallet, sybilScore, sourceStake, sourceChainId, nonce) {
    const messageHash = ethers.solidityPackedKeccak256(
      ["address", "uint256", "uint256", "uint256", "uint256"],
      [wallet, sybilScore, sourceStake, sourceChainId, nonce]
    );
    return oracleWallet.signMessage(ethers.getBytes(messageHash));
  }

  beforeEach(async function () {
    [deployer, operator, user1, user2, treasury] = await ethers.getSigners();

    // Create a dedicated oracle signer wallet
    oracleWallet = ethers.Wallet.createRandom().connect(ethers.provider);

    // Deploy core SybilNet
    const SybilNet = await ethers.getContractFactory("SybilNet");
    sybilNet = await SybilNet.deploy(treasury.address);
    await sybilNet.waitForDeployment();

    // Deploy Bridge
    const Bridge = await ethers.getContractFactory("SybilNetBridge");
    bridge = await Bridge.deploy(
      await sybilNet.getAddress(),
      oracleWallet.address
    );
    await bridge.waitForDeployment();

    // Grant BRIDGE_OPERATOR_ROLE to operator
    const BRIDGE_OPERATOR_ROLE = await bridge.BRIDGE_OPERATOR_ROLE();
    await bridge.grantRole(BRIDGE_OPERATOR_ROLE, operator.address);

    // Mint a credential for user1 on the core contract
    const ORACLE_ROLE = await sybilNet.ORACLE_ROLE();
    await sybilNet.grantRole(ORACLE_ROLE, deployer.address);
    await sybilNet.connect(user1).mintCredential({ value: MIN_STAKE });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  Deployment
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Deployment", function () {
    it("should set the correct SybilNet reference", async function () {
      expect(await bridge.sybilNet()).to.equal(await sybilNet.getAddress());
    });

    it("should set the correct oracle signer", async function () {
      expect(await bridge.oracleSigner()).to.equal(oracleWallet.address);
    });

    it("should register default supported chains", async function () {
      expect(await bridge.isChainSupported(POLYGON_CHAIN_ID)).to.be.true;
      expect(await bridge.isChainSupported(ARBITRUM_CHAIN_ID)).to.be.true;
      expect(await bridge.isChainSupported(BASE_CHAIN_ID)).to.be.true;
      expect(await bridge.supportedChains(POLYGON_CHAIN_ID)).to.equal("Polygon");
    });

    it("should not support unregistered chains", async function () {
      expect(await bridge.isChainSupported(999)).to.be.false;
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  Lock Credential (Source Chain)
  // ═══════════════════════════════════════════════════════════════════════════

  describe("lockCredential", function () {
    it("should lock a valid credential", async function () {
      await expect(bridge.connect(user1).lockCredential(POLYGON_CHAIN_ID))
        .to.emit(bridge, "CredentialLocked")
        .withArgs(
          user1.address,
          POLYGON_CHAIN_ID,
          0, // sybilScore
          MIN_STAKE,
          0, // first nonce
          (await ethers.provider.getBlock("latest")).timestamp + 1
        );

      const lock = await bridge.getLockRecord(user1.address);
      expect(lock.isLocked).to.be.true;
      expect(lock.destChainId).to.equal(POLYGON_CHAIN_ID);
    });

    it("should reject locking without an active credential", async function () {
      await expect(
        bridge.connect(user2).lockCredential(POLYGON_CHAIN_ID)
      ).to.be.revertedWithCustomError(bridge, "NoActiveCredential");
    });

    it("should reject locking to an unsupported chain", async function () {
      await expect(
        bridge.connect(user1).lockCredential(999)
      ).to.be.revertedWithCustomError(bridge, "UnsupportedChain");
    });

    it("should reject double locking", async function () {
      await bridge.connect(user1).lockCredential(POLYGON_CHAIN_ID);
      await expect(
        bridge.connect(user1).lockCredential(ARBITRUM_CHAIN_ID)
      ).to.be.revertedWithCustomError(bridge, "AlreadyLocked");
    });

    it("should increment the lock nonce", async function () {
      await bridge.connect(user1).lockCredential(POLYGON_CHAIN_ID);
      expect(await bridge.lockNonces(user1.address)).to.equal(1);

      // Unlock and re-lock
      await bridge.connect(user1).unlockCredential();
      await bridge.connect(user1).lockCredential(ARBITRUM_CHAIN_ID);
      expect(await bridge.lockNonces(user1.address)).to.equal(2);
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  Unlock Credential
  // ═══════════════════════════════════════════════════════════════════════════

  describe("unlockCredential", function () {
    it("should unlock a locked credential", async function () {
      await bridge.connect(user1).lockCredential(POLYGON_CHAIN_ID);

      await expect(bridge.connect(user1).unlockCredential())
        .to.emit(bridge, "CredentialUnlocked");

      expect(await bridge.isCredentialLocked(user1.address)).to.be.false;
    });

    it("should reject unlocking when not locked", async function () {
      await expect(
        bridge.connect(user1).unlockCredential()
      ).to.be.revertedWithCustomError(bridge, "NotLocked");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  Mint Bridged Credential (Destination Chain)
  // ═══════════════════════════════════════════════════════════════════════════

  describe("mintBridgedCredential", function () {
    it("should mint with a valid oracle signature", async function () {
      const score = 10;
      const stake = MIN_STAKE;
      const chainId = 1; // bridged from Ethereum
      const nonce = 0;

      const sig = await signBridgeMessage(
        user1.address, score, stake, chainId, nonce
      );

      await expect(
        bridge.connect(operator).mintBridgedCredential(
          user1.address, score, stake, chainId, nonce, sig
        )
      ).to.emit(bridge, "BridgedCredentialMinted");

      expect(await bridge.isBridgedHuman(user1.address)).to.be.true;
      expect(await bridge.totalBridged()).to.equal(1);

      const cred = await bridge.getBridgedCredential(user1.address);
      expect(cred.sybilScore).to.equal(score);
      expect(cred.sourceChainId).to.equal(chainId);
      expect(cred.isActive).to.be.true;
    });

    it("should reject an invalid signature", async function () {
      const badSigner = ethers.Wallet.createRandom();
      const messageHash = ethers.solidityPackedKeccak256(
        ["address", "uint256", "uint256", "uint256", "uint256"],
        [user1.address, 10, MIN_STAKE, 1, 0]
      );
      const badSig = await badSigner.signMessage(ethers.getBytes(messageHash));

      await expect(
        bridge.connect(operator).mintBridgedCredential(
          user1.address, 10, MIN_STAKE, 1, 0, badSig
        )
      ).to.be.revertedWithCustomError(bridge, "InvalidSignature");
    });

    it("should reject double minting for the same wallet", async function () {
      const sig = await signBridgeMessage(user1.address, 10, MIN_STAKE, 1, 0);
      await bridge.connect(operator).mintBridgedCredential(
        user1.address, 10, MIN_STAKE, 1, 0, sig
      );

      const sig2 = await signBridgeMessage(user1.address, 10, MIN_STAKE, 1, 1);
      await expect(
        bridge.connect(operator).mintBridgedCredential(
          user1.address, 10, MIN_STAKE, 1, 1, sig2
        )
      ).to.be.revertedWithCustomError(bridge, "AlreadyBridged");
    });

    it("should reject minting from non-operator", async function () {
      const sig = await signBridgeMessage(user1.address, 10, MIN_STAKE, 1, 0);
      await expect(
        bridge.connect(user1).mintBridgedCredential(
          user1.address, 10, MIN_STAKE, 1, 0, sig
        )
      ).to.be.reverted;
    });

    it("should reject minting for zero address", async function () {
      const sig = await signBridgeMessage(ethers.ZeroAddress, 10, MIN_STAKE, 1, 0);
      await expect(
        bridge.connect(operator).mintBridgedCredential(
          ethers.ZeroAddress, 10, MIN_STAKE, 1, 0, sig
        )
      ).to.be.revertedWithCustomError(bridge, "InvalidAddress");
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  Revoke Bridged Credential
  // ═══════════════════════════════════════════════════════════════════════════

  describe("revokeBridgedCredential", function () {
    beforeEach(async function () {
      const sig = await signBridgeMessage(user1.address, 10, MIN_STAKE, 1, 0);
      await bridge.connect(operator).mintBridgedCredential(
        user1.address, 10, MIN_STAKE, 1, 0, sig
      );
    });

    it("should revoke an active bridged credential", async function () {
      await expect(
        bridge.connect(operator).revokeBridgedCredential(
          user1.address, "source_chain_slashed"
        )
      ).to.emit(bridge, "BridgedCredentialRevoked");

      expect(await bridge.isBridgedHuman(user1.address)).to.be.false;
      expect(await bridge.totalBridged()).to.equal(0);
    });

    it("should reject revoking when no bridged credential exists", async function () {
      await expect(
        bridge.connect(operator).revokeBridgedCredential(
          user2.address, "no_credential"
        )
      ).to.be.revertedWithCustomError(bridge, "NotBridged");
    });

    it("should reject revoking from non-operator", async function () {
      await expect(
        bridge.connect(user1).revokeBridgedCredential(
          user1.address, "unauthorized"
        )
      ).to.be.reverted;
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  //  Admin Functions
  // ═══════════════════════════════════════════════════════════════════════════

  describe("Admin", function () {
    it("should add a new supported chain", async function () {
      await expect(bridge.addChain(10, "Optimism"))
        .to.emit(bridge, "ChainAdded")
        .withArgs(10, "Optimism");

      expect(await bridge.isChainSupported(10)).to.be.true;
      expect(await bridge.supportedChains(10)).to.equal("Optimism");
    });

    it("should remove a supported chain", async function () {
      await expect(bridge.removeChain(POLYGON_CHAIN_ID))
        .to.emit(bridge, "ChainRemoved");

      expect(await bridge.isChainSupported(POLYGON_CHAIN_ID)).to.be.false;
    });

    it("should update oracle signer", async function () {
      const newSigner = ethers.Wallet.createRandom();
      await expect(bridge.setOracleSigner(newSigner.address))
        .to.emit(bridge, "OracleSignerUpdated");

      expect(await bridge.oracleSigner()).to.equal(newSigner.address);
    });

    it("should reject zero address for oracle signer", async function () {
      await expect(
        bridge.setOracleSigner(ethers.ZeroAddress)
      ).to.be.revertedWithCustomError(bridge, "InvalidAddress");
    });

    it("should pause and unpause", async function () {
      await bridge.pause();
      await expect(
        bridge.connect(user1).lockCredential(POLYGON_CHAIN_ID)
      ).to.be.reverted;

      await bridge.unpause();
      // Should work again after unpause
      await bridge.connect(user1).lockCredential(POLYGON_CHAIN_ID);
    });
  });
});
