const { ethers, network } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const human = "0x285C0312ce4d3C1cD8C1649DfFc373B744110c5c";
  const sybil = "0x166Cee66374774eC3827F2429E986DA87539c48b";

  const [deployer] = await ethers.getSigners();

  // 1. Fund both wallets
  console.log(`Funding Human (${human}) with 100 ETH...`);
  await deployer.sendTransaction({ to: human, value: ethers.parseEther("100") });
  
  console.log(`Funding Sybil (${sybil}) with 100 ETH...`);
  await deployer.sendTransaction({ to: sybil, value: ethers.parseEther("100") });

  // 2. Setup the Sybil account on-chain
  console.log("Pre-slashing the Sybil account on-chain...");
  await network.provider.request({
    method: "hardhat_impersonateAccount",
    params: [sybil],
  });
  const sybilSigner = await ethers.getSigner(sybil);

  const deployments = require("../../frontend/lib/deployments.json");
  const sybilNet = await ethers.getContractAt("SybilNet", deployments.SybilNet);

  try {
    // Try to mint (in case it wasn't minted yet)
    await sybilNet.connect(sybilSigner).mintCredential({ value: ethers.parseEther("0.01") });
  } catch (e) {
    // Might already be minted/banned if run twice, ignore
  }
  
  try {
    // Oracle flags and slashes the Sybil
    await sybilNet.connect(deployer).updateSybilScore(sybil, 95);
    await sybilNet.connect(deployer).slash(sybil, deployer.address);
  } catch (e) {
    // Might already be slashed, ignore
  }

  await network.provider.request({
    method: "hardhat_stopImpersonatingAccount",
    params: [sybil],
  });

  // 3. Update the ML data CSV for the frontend
  console.log("Updating ML data (node_scores.csv) for the UI...");
  const csvPath = path.join(__dirname, "../../data/processed/node_scores.csv");
  let csvContent = "node_id,sybil_probability,classification\n";
  csvContent += `${human.toLowerCase()},0.12,Human\n`;
  csvContent += `${sybil.toLowerCase()},0.95,Sybil\n`;
  fs.writeFileSync(csvPath, csvContent);

  console.log("✅ Presentation Setup Complete!");
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
