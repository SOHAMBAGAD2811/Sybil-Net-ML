const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);

  const treasury = deployer.address;

  // 1. Core SybilNet
  const SybilNet = await ethers.getContractFactory("SybilNet");
  const sybilNet = await SybilNet.deploy(treasury);
  await sybilNet.waitForDeployment();
  const sybilNetAddr = await sybilNet.getAddress();
  console.log("✅ SybilNet deployed to:", sybilNetAddr);

  // 2. Cross-Chain Bridge
  const Bridge = await ethers.getContractFactory("SybilNetBridge");
  const bridge = await Bridge.deploy(sybilNetAddr, deployer.address);
  await bridge.waitForDeployment();
  const bridgeAddr = await bridge.getAddress();
  console.log("✅ SybilNetBridge deployed to:", bridgeAddr);

  // 3. Governance
  const Governance = await ethers.getContractFactory("SybilNetGovernance");
  const governance = await Governance.deploy(sybilNetAddr);
  await governance.waitForDeployment();
  const govAddr = await governance.getAddress();
  console.log("✅ SybilNetGovernance deployed to:", govAddr);

  // 4. Marketplace (The purpose!)
  const Marketplace = await ethers.getContractFactory("SybilMarketplace");
  const marketplace = await Marketplace.deploy(sybilNetAddr);
  await marketplace.waitForDeployment();
  const marketAddr = await marketplace.getAddress();
  console.log("✅ SybilMarketplace deployed to:", marketAddr);

  // Grant necessary roles
  const ORACLE_ROLE = await sybilNet.ORACLE_ROLE();
  const ADMIN_ROLE = await sybilNet.DEFAULT_ADMIN_ROLE();
  const BRIDGE_OPERATOR_ROLE = await bridge.BRIDGE_OPERATOR_ROLE();

  await sybilNet.grantRole(ORACLE_ROLE, deployer.address);
  await sybilNet.grantRole(ORACLE_ROLE, govAddr);
  await sybilNet.grantRole(ADMIN_ROLE, govAddr);
  await bridge.grantRole(BRIDGE_OPERATOR_ROLE, deployer.address);

  // Export addresses and ABIs for the frontend
  const frontendDir = path.join(__dirname, "../../frontend/lib");
  if (!fs.existsSync(frontendDir)) {
    fs.mkdirSync(frontendDir, { recursive: true });
  }

  const deployments = {
    SybilNet: sybilNetAddr,
    SybilNetBridge: bridgeAddr,
    SybilNetGovernance: govAddr,
    SybilMarketplace: marketAddr,
  };

  fs.writeFileSync(
    path.join(frontendDir, "deployments.json"),
    JSON.stringify(deployments, null, 2)
  );

  // Copy ABIs
  const copyAbi = (contractName) => {
    const artifact = require(`../artifacts/contracts/${contractName}.sol/${contractName}.json`);
    fs.writeFileSync(
      path.join(frontendDir, `${contractName}ABI.json`),
      JSON.stringify(artifact.abi, null, 2)
    );
  };

  copyAbi("SybilNet");
  copyAbi("SybilNetBridge");
  copyAbi("SybilNetGovernance");
  copyAbi("SybilMarketplace");

  console.log("\n✅ Exported addresses and ABIs to frontend/lib/");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
