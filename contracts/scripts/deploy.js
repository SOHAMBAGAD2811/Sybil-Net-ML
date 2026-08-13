const { ethers } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying SybilNet with account:", deployer.address);
  console.log(
    "Account balance:",
    ethers.formatEther(await ethers.provider.getBalance(deployer.address)),
    "ETH"
  );

  // Treasury defaults to the deployer for local dev; use a multisig on mainnet
  const treasury = deployer.address;

  const SybilNet = await ethers.getContractFactory("SybilNet");
  const sybilNet = await SybilNet.deploy(treasury);
  await sybilNet.waitForDeployment();

  const address = await sybilNet.getAddress();
  console.log("\n✅ SybilNet deployed to:", address);
  console.log("   Treasury:            ", treasury);
  console.log("   Min stake:           ", ethers.formatEther(await sybilNet.minStake()), "ETH");

  // Grant ORACLE_ROLE to the deployer for local testing
  // In production: grant to the GNN backend service wallet
  const ORACLE_ROLE = await sybilNet.ORACLE_ROLE();
  await sybilNet.grantRole(ORACLE_ROLE, deployer.address);
  console.log("   ORACLE_ROLE granted to deployer (dev mode)");

  console.log("\n💡 Next steps:");
  console.log("   1. Set SYBILNET_ADDRESS=" + address + " in your .env");
  console.log("   2. Grant ORACLE_ROLE to your GNN backend wallet");
  console.log("   3. Call mintCredential() with >= 0.01 ETH to issue credentials");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
