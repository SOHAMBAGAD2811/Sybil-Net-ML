require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: "../.env" });

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    // Local Hardhat node (default for development)
    hardhat: {
      chainId: 31337,
    },
    // Sepolia testnet — set DEPLOYER_PRIVATE_KEY + ALCHEMY_API_KEY in ../.env
    sepolia: {
      url: `https://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY || ""}`,
      accounts: process.env.DEPLOYER_PRIVATE_KEY
        ? [process.env.DEPLOYER_PRIVATE_KEY]
        : [],
    },
  },
  gasReporter: {
    enabled: true,
    currency: "USD",
  },
};
