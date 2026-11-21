# Sybil-Net: Formal Problem Statement
## Official Project Information Sheet & Proposal Document

---

## 1. Executive Problem Statement (Short Summary)

> Public blockchain networks rely on permissionless, pseudo-anonymous public-key cryptography where generating digital identities carries near-zero marginal computational or financial cost. Malicious actors exploit this structural vulnerability by deploying automated, multi-account "Sybil" bot farms to siphon token airdrops, hijack DAO governance voting, execute wash trading, and extract liquidity rewards. Existing mitigation techniques—such as static rule heuristics, centralized KYC, and video Proof-of-Humanity—either fail against adaptive AI scripts, ruin scalability, violate user privacy, or produce offline advisory reports that lack on-chain financial penalties and pre-confirmation mempool protection. Consequently, there is an urgent need for an end-to-end protocol that combines inductive Graph Neural Networks (GraphSAGE) to detect bot farm topologies, automated smart contract stake slashing, zero-knowledge (zk-SNARK) privacy credentials, and real-time mempool interception.

---

## 2. Comprehensive Problem Statement (Detailed Project Information Sheet Format)

### A. Context & Background
Decentralized Web3 protocols operate on permissionless public ledgers where identity is anchored to cryptographic key pairs rather than verified real-world human identities. While this guarantees censorship resistance, it creates a fundamental security dilemma: creating 10,000 distinct wallet addresses costs zero marginal capital or computation. Without a centralized identity issuer, protocols cannot distinguish between 10,000 unique human participants and a single malicious entity controlling 10,000 automated scripts.

### B. Exploitation Vectors & Impact
Coordinated Sybil bot farms exploit this identity weakness across core Web3 ecosystem pillars:
1. **Airdrop & Token Distribution Exploitation:** Coordinated wallet fleets simulate organic transaction patterns to siphon off community token allocations meant for early adopters.
2. **DAO Governance Hijacking:** Attackers acquire fractional governance tokens across thousands of synthetic accounts to pass malicious proposals and drain community treasuries.
3. **DeFi Liquidity & Wash Trading Manipulation:** Wallet rings trade assets circularly among themselves to manipulate floor prices, inflate volume metrics, and extract yield farming rewards.

### C. Limitations & Failure Modes of Existing Defenses

| Defense Mechanism | Operational Mechanism | Fundamental Shortcoming / Failure Mode |
| :--- | :--- | :--- |
| **Static Heuristic Rules** | Hardcoded filters (e.g., `tx_count > 5`) | Easily gamed by bot operators tuning script parameters dynamically |
| **Centralized KYC Verification** | Third-party passport/ID checks | Privacy-invasive, single point of data breach, violates Web3 decentralization |
| **Proof-of-Humanity Services** | Social video & peer sign-off | Extreme user friction, non-scalable, vulnerable to AI deepfakes & collusive rings |
| **Offline ML Forensics** | Static batch model scoring | Advisory reports only; no automated smart contract slashing or financial loss for attackers |
| **Post-Block Detection** | Forensic inspection on confirmed blocks | Blind to real-time pending transactions in the mempool (sandwich bots / MEV attacks) |

### D. Identified Research & Engineering Gap
Current solutions treat detection, on-chain enforcement, privacy, and speed as isolated domains. There is no existing end-to-end framework that bridges:
- **Inductive GNN topology scoring** (generalizing to newly created wallets without full graph retraining);
- **Direct cryptoeconomic enforcement** (automatically slashing staked collateral upon detection);
- **Zero-knowledge privacy credentials** (proving identity without exposing on-chain wallet history); and
- **Pre-confirmation mempool monitoring** (intercepting threats before block inclusion).

---

## 3. Project Objective Statement

To solve the formal problem defined above, **Sybil-Net** implements a 4-layer protocol specifying four core technical deliverables:

1. **Inductive GNN Detection Engine:** PyTorch Geometric GraphSAGE model trained on 12 graph-theoretic node features to classify bot farm topologies with **>95% F1-score**.
2. **Stake-Backed On-Chain Enforcement:** `SybilNet.sol` smart contract requiring 0.01 ETH staking with an automated Web3 Oracle Bridge executing **automated financial slashing** and credential revocation for scores >70.
3. **Zero-Knowledge Privacy Credentials:** Circom 2.0 Groth16 zk-SNARK proof system (`sybil_credential.circom` & `ZKVerifier.sol`) enabling private identity attestation in **<200,000 gas**.
4. **Pre-Confirmation Mempool Protection:** Asynchronous Python WebSocket listener scoring pending transactions in **<45ms** prior to block confirmation.
