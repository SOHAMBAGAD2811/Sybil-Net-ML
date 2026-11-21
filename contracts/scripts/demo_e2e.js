const { ethers } = require("hardhat");
const deployments = require("../frontend/lib/deployments.json");

async function main() {
  console.log("=========================================");
  console.log("🔥 Sybil-Net End-to-End Simulation 🔥");
  console.log("=========================================\n");

  const [oracleAdmin, humanUser, botUser] = await ethers.getSigners();

  const SybilNet = await ethers.getContractAt("SybilNet", deployments.SybilNet);
  const Governance = await ethers.getContractAt("SybilNetGovernance", deployments.SybilNetGovernance);
  const Marketplace = await ethers.getContractAt("SybilMarketplace", deployments.SybilMarketplace);

  const minStake = await SybilNet.minStake();

  console.log("1️⃣  Users stake 0.01 ETH to mint credentials...");
  await SybilNet.connect(humanUser).mintCredential({ value: minStake });
  await SybilNet.connect(botUser).mintCredential({ value: minStake });
  console.log("   ✅ Human User credential minted: ", humanUser.address);
  console.log("   ✅ Bot User credential minted:   ", botUser.address);

  console.log("\n2️⃣  Users attempt to claim exclusive airdrop on the Marketplace...");
  await Marketplace.connect(humanUser).claimExclusiveAirdrop();
  console.log("   ✅ Human User successfully claimed airdrop!");
  await Marketplace.connect(botUser).claimExclusiveAirdrop();
  console.log("   ✅ Bot User successfully claimed airdrop (for now...)");

  console.log("\n3️⃣  🤖 GNN Oracle analyzes mempool transactions...");
  console.log("   ⏳ Detecting wash-ring topologies...");
  console.log("   🚨 Bot User flagged with 95% Sybil probability!");
  
  // Oracle suspends and slashes the bot
  await SybilNet.connect(oracleAdmin).updateSybilScore(botUser.address, 95);
  await SybilNet.connect(oracleAdmin).slash(botUser.address, oracleAdmin.address);
  console.log("   💥 Bot User's stake slashed & credential revoked!");

  console.log("\n4️⃣  Bot User attempts to claim airdrop again from another contract...");
  try {
    await Marketplace.connect(botUser).claimExclusiveAirdrop();
  } catch (err) {
    console.log("   🚫 Bot User blocked! Transaction reverted: NotVerifiedHuman");
  }

  console.log("\n5️⃣  🏛️ Governance: Human User thinks Bot User was wrongly slashed.");
  console.log("   📝 Creating a Slash Appeal Proposal...");
  
  const calldata = SybilNet.interface.encodeFunctionData("liftSuspension", [botUser.address]);
  await Governance.connect(humanUser).createProposal(
    0, // SLASH_APPEAL
    "Appeal: Bot User is actually a high-frequency market maker, not a wash trader.",
    deployments.SybilNet,
    calldata
  );
  console.log("   ✅ Proposal created (ID: 0) by Human User.");

  console.log("   🗳️ Human User casts FOR vote...");
  await Governance.connect(humanUser).castVote(0, 0); // Vote FOR

  console.log("\n=========================================");
  console.log("🏁 End of Demo.");
  console.log("=========================================");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
