# Sybil-Net — Mermaid Diagram Collection

> **How to use in draw.io:**
> 1. Open [draw.io](https://draw.io) → `Extras` → `Edit Diagram`
> 2. Paste any diagram block below (including the ` ```mermaid ` fences)
> 3. Click **OK** → draw.io renders it as a fully editable vector diagram
> 4. You can then style, recolour, and export as SVG / PNG / PDF

---

## Diagram Index

| # | Diagram | Description |
|---|---------|-------------|
| [D1](#d1--full-system-architecture) | Full System Architecture | All 5 layers end-to-end |
| [D2](#d2--end-to-end-data-pipeline) | End-to-End Data Pipeline | Ingestion → GNN → Contract |
| [D3](#d3--graphsage-neural-network-architecture) | GraphSAGE Architecture | Layer-by-layer model structure |
| [D4](#d4--sybil-attack-graph-patterns) | Sybil Attack Graph Patterns | 4 attack topologies |
| [D5](#d5--smart-contract-credential-state-machine) | Credential State Machine | None → Active → Suspended → Revoked |
| [D6](#d6--smart-contract-role-permissions) | Role Permissions | Admin / Oracle / Guardian / User |
| [D7](#d7--oracle-bridge-sequence) | Oracle Bridge Sequence | ML scores → on-chain calls |
| [D8](#d8--mempool-monitor-pipeline) | Mempool Monitor Pipeline | WebSocket → live GNN → alerts |
| [D9](#d9--zk-snark-proof-flow) | zk-SNARK Proof Flow | User proves humanity anonymously |
| [D10](#d10--cross-chain-bridge-topology) | Cross-Chain Bridge Topology | Multi-chain GNN ingestion |
| [D11](#d11--governance--dao-lifecycle) | Governance & DAO Lifecycle | Proposal → Vote → Execute |
| [D12](#d12--trust-verified-marketplace-ecosystem) | Marketplace Ecosystem | 3-pillar DeFi with credential gating |
| [D13](#d13--8-week-project-roadmap-gantt) | 8-Week Roadmap (Gantt) | Sprint timeline |
| [D14](#d14--slash-fund-distribution) | Slash Fund Distribution | ETH flow on slash event |
| [D15](#d15--feature-extraction-pipeline) | Feature Extraction Pipeline | 12 node features computed |

---

## D1 — Full System Architecture

```mermaid
flowchart TD
    subgraph DATA["🔗 Layer 1 — Data Pipeline"]
        A1["Alchemy API\nEthereum Mainnet"] --> B1["transactions.csv\n50,000 txns"]
        A2["Synthetic Sybil\nGenerator\n4 attack archetypes"] --> B1
        B1 --> C1["graph/builder.py\nNetworkX DiGraph\nNodes=wallets · Edges=txns"]
        C1 --> D1["features/extractor.py\n12 node-level features\nper wallet"]
    end

    subgraph ML["🧠 Layer 2 — ML Layer"]
        D1 --> E1["models/gnn.py\nGraphSAGE · 3 layers\n37,122 parameters"]
        E1 --> F1["node_scores.csv\nSybil probability 0-1\nper wallet"]
    end

    subgraph CHAIN["⛓️ Layer 3 — On-Chain Layer"]
        F1 --> G1["oracle_bridge.py\nPython web3.py"]
        G1 -->|"updateSybilScore()"| H1["SybilNet.sol\nSolidity 0.8.24\nOpenZeppelin"]
        H1 -->|"score less than 70"| I1["✅ Humanity Credential\nERC-721 minted\nstake locked"]
        H1 -->|"score ≥ 70"| J1["🚨 Slashed\nStake burned\n365-day ban"]
        USER["👤 User\nstakes 0.01 ETH"] -->|"mintCredential()"| H1
    end

    subgraph MKT["🏪 Layer 4 — Trust-Verified Marketplace"]
        I1 --> K1["🔄 Zero Wash-Trade\nNFT and Airdrop Exchange"]
        I1 --> L1["💳 Undercollateralised\nCredit Hub"]
        I1 --> M1["🌾 Sybil-Resistant\nYield Hub"]
    end

    subgraph MEMPOOL["⚡ Layer 5 — Mempool Monitor"]
        A1 -->|"WebSocket"| N1["Pending Tx Stream\nAlchemy subscription"]
        N1 --> O1["Live GNN Inference\n10 ms per batch\npre-confirmation"]
        O1 --> P1["mempool_alerts.json\nring-buffer 200 entries"]
        P1 --> Q1["Next.js Live Feed\n2s poll interval"]
    end

    style DATA fill:#1a2a4a,color:#fff,stroke:#5c8ae6
    style ML fill:#1a3a2a,color:#fff,stroke:#4caf7d
    style CHAIN fill:#3a1a1a,color:#fff,stroke:#e64c4c
    style MKT fill:#2a2a1a,color:#fff,stroke:#e6c34c
    style MEMPOOL fill:#2a1a3a,color:#fff,stroke:#b44ce6
```

---

## D2 — End-to-End Data Pipeline

```mermaid
flowchart LR
    subgraph INGEST["Step 1 — Ingest"]
        A["Alchemy API\neth_getLogs"] --> C["transactions.csv\n50k rows"]
        B["Synthetic Sybil\nGenerator"] --> C
    end

    subgraph GRAPH["Step 2 — Build Graph"]
        C --> D["graph/builder.py"]
        D --> E["NetworkX DiGraph\nNodes = wallets\nEdges = txns"]
        E --> F["graph.pkl\nserialised"]
    end

    subgraph FEAT["Step 3 — Extract Features"]
        F --> G["features/extractor.py"]
        G --> H["12 features x N nodes\nRobustScaler normalised"]
        H --> I["features.csv\nnodes.csv · edges.csv"]
    end

    subgraph TRAIN["Step 4 — Train GNN"]
        I --> J["models/gnn.py"]
        J --> K["GraphSAGE\n3-layer SAGEConv"]
        K --> L["sybil_sage.pt\ntrained weights"]
        K --> M["node_scores.csv\nSybil probability per wallet"]
    end

    subgraph ENFORCE["Step 5 — Enforce On-Chain"]
        M --> N["oracle_bridge.py"]
        N -->|"score ≥ 85%"| O["slash()"]
        N -->|"60 to 85%"| P["updateSybilScore()"]
        N -->|"less than 60%"| Q["No action"]
        O --> R["SybilNet.sol\nstake burned · ban applied"]
        P --> R
    end

    subgraph VIZ["Step 6 — Visualise"]
        F --> S["visualization/viewer.py"]
        S --> T["graph_visualization.html\nPyVis interactive"]
    end

    style INGEST fill:#eef2ff,stroke:#5c8ae6
    style GRAPH fill:#eefff2,stroke:#4caf7d
    style FEAT fill:#fff8ee,stroke:#e6a34c
    style TRAIN fill:#ffeef2,stroke:#e64c7d
    style ENFORCE fill:#f2eeff,stroke:#7d4ce6
    style VIZ fill:#eefff8,stroke:#4ce6b4
```

---

## D3 — GraphSAGE Neural Network Architecture

```mermaid
flowchart TD
    subgraph INPUT["Input Layer"]
        X["Feature Matrix\nX in R to N x 12\n4601 wallets x 12 features"]
        EI["Edge Index\n2 x E directed edges"]
    end

    subgraph L1["Layer 1 — SAGEConv"]
        SAG1["SAGEConv\n12 to 64\naggr = mean"]
        BN1["BatchNorm1d\n64 channels"]
        R1["ReLU"]
        D1["Dropout\np = 0.4"]
        SAG1 --> BN1 --> R1 --> D1
    end

    subgraph L2["Layer 2 — SAGEConv"]
        SAG2["SAGEConv\n64 to 32\naggr = mean"]
        BN2["BatchNorm1d\n32 channels"]
        R2["ReLU"]
        D2["Dropout\np = 0.4"]
        SAG2 --> BN2 --> R2 --> D2
    end

    subgraph L3["Layer 3 — SAGEConv"]
        SAG3["SAGEConv\n32 to 16\naggr = mean"]
        BN3["BatchNorm1d\n16 channels"]
        R3["ReLU"]
        SAG3 --> BN3 --> R3
    end

    subgraph OUTPUT["Output Layer"]
        LIN["Linear\n16 to 2"]
        SM["log_softmax\ndim = 1"]
        OUT["Output N x 2\nHuman · Sybil prob per node"]
        LIN --> SM --> OUT
    end

    X --> SAG1
    EI --> SAG1
    EI --> SAG2
    EI --> SAG3
    D1 --> SAG2
    D2 --> SAG3
    R3 --> LIN

    PARAMS["Total Parameters: 37122\nDevice: CPU\nTraining: Adam · CosineAnnealingLR\nEarly Stopping: patience=30"]

    style INPUT fill:#1a2a4a,color:#fff
    style L1 fill:#1a3a2a,color:#fff
    style L2 fill:#2a2a1a,color:#fff
    style L3 fill:#3a1a2a,color:#fff
    style OUTPUT fill:#1a1a3a,color:#fff
    style PARAMS fill:#f5f5f5,stroke:#aaa,color:#333
```

---

## D4 — Sybil Attack Graph Patterns

```mermaid
flowchart TD
    subgraph HUB["Pattern 1 — Hub-and-Spoke Bot Farm"]
        HC["🔴 Controller\nhigh out-degree\nhigh betweenness"]
        HB1["🔴 Bot 1"]
        HB2["🔴 Bot 2"]
        HB3["🔴 Bot 3"]
        HB4["🔴 Bot 4"]
        HB5["🔴 Bot 5"]
        HC -->|"ETH distribute"| HB1
        HC -->|"ETH distribute"| HB2
        HC -->|"ETH distribute"| HB3
        HC -->|"ETH distribute"| HB4
        HC -->|"ETH distribute"| HB5
        HB1 -->|"collect back"| HC
        HB2 -->|"collect back"| HC
        HB3 -->|"collect back"| HC
        HB4 -->|"collect back"| HC
        HB5 -->|"collect back"| HC
    end

    subgraph WASH["Pattern 2 — Wash-Trading Ring"]
        WA["🟠 Wallet A"] -->|"ETH"| WB["🟠 Wallet B"]
        WB -->|"ETH"| WC["🟠 Wallet C"]
        WC -->|"ETH"| WD["🟠 Wallet D"]
        WD -->|"ETH"| WA
        note1["High reciprocity\nHigh clustering coeff\nSmall ring 3-8 nodes"]
    end

    subgraph LAYER["Pattern 3 — Layered Cluster"]
        LR1["🟡 Root"] --> LM1["🟡 Mid 1"]
        LR1 --> LM2["🟡 Mid 2"]
        LM1 --> LL1["🟡 Leaf 1"]
        LM1 --> LL2["🟡 Leaf 2"]
        LM2 --> LL3["🟡 Leaf 3"]
        LM2 --> LL4["🟡 Leaf 4"]
        note2["High betweenness\non mid-layer nodes\nHierarchical fan-out"]
    end

    subgraph HONEST["Pattern 4 — Honest Human Wallets"]
        HH1["🟢 Human A"] -->|"pay"| HH2["🟢 Human B"]
        HH3["🟢 Human C"] -->|"pay"| HH1
        HH2 -->|"pay"| HH4["🟢 Human D"]
        note3["Low reciprocity\nOrganic interactions\nDiverse counterparties"]
    end

    style HUB fill:#fff0f0,stroke:#e64c4c
    style WASH fill:#fff5e6,stroke:#e6924c
    style LAYER fill:#fffae6,stroke:#e6d44c
    style HONEST fill:#f0fff0,stroke:#4ce64c
```

---

## D5 — Smart Contract Credential State Machine

```mermaid
stateDiagram-v2
    [*] --> None : Wallet has no credential

    None --> Active : mintCredential()\nstake 0.01 ETH\nemits CredentialMinted

    Active --> Suspended : oracle calls updateSybilScore()\nGNN score 70 or above\nemits SybilWarning

    Active --> Revoked : withdrawStake()\nvoluntary exit\nemits StakeWithdrawn

    Suspended --> Active : liftSuspension()\nfalse positive cleared\nby ORACLE ROLE

    Suspended --> Revoked : slash()\nstake burned\n365-day ban\nemits WalletSlashed

    Revoked --> None : after 365 days\nban window expires

    note right of Active
        isVerifiedHuman equals true
        Can access Marketplace
        Can withdraw stake
    end note

    note right of Suspended
        isVerifiedHuman equals false
        Cannot withdraw
        Oracle reviewing
    end note

    note right of Revoked
        isVerifiedHuman equals false
        Banned 365 days
        Stake is gone
    end note
```

---

## D6 — Smart Contract Role Permissions

```mermaid
flowchart LR
    subgraph ROLES["Access Control Roles"]
        ADMIN["🔑 DEFAULT_ADMIN_ROLE\nProtocol multisig\nGnosis Safe"]
        ORACLE["🤖 ORACLE_ROLE\nGNN backend wallet\noracle_bridge.py"]
        GUARDIAN["🛡️ GUARDIAN_ROLE\nEmergency responder"]
        USER["👤 User\nAny wallet"]
    end

    subgraph FUNCTIONS["Contract Functions"]
        MINT["mintCredential()\nStake ETH, get credential"]
        WITHDRAW["withdrawStake()\nReclaim ETH voluntarily"]
        UPDATE["updateSybilScore()\nPush GNN score on-chain"]
        SLASH["slash()\nBurn stake · revoke credential"]
        BSLASH["batchSlash()\nSlash entire bot ring"]
        LIFT["liftSuspension()\nClear false positive"]
        SETSTAKE["setMinStake()\nUpdate minimum stake"]
        SETTREASURY["setTreasury()\nUpdate treasury address"]
        PAUSE["pause and unpause\nEmergency circuit breaker"]
    end

    USER --> MINT
    USER --> WITHDRAW
    ORACLE --> UPDATE
    ORACLE --> SLASH
    ORACLE --> BSLASH
    ORACLE --> LIFT
    ADMIN --> SETSTAKE
    ADMIN --> SETTREASURY
    GUARDIAN --> PAUSE

    style ADMIN fill:#1a2a4a,color:#fff
    style ORACLE fill:#1a3a1a,color:#fff
    style GUARDIAN fill:#3a1a1a,color:#fff
    style USER fill:#2a2a2a,color:#fff
```

---

## D7 — Oracle Bridge Sequence

```mermaid
sequenceDiagram
    participant GNN as GNN Model
    participant CSV as node_scores.csv
    participant BRIDGE as oracle_bridge.py
    participant CONTRACT as SybilNet.sol
    participant TREASURY as Treasury Wallet
    participant REPORTER as Reporter Wallet

    GNN ->> CSV: Write Sybil probability per wallet 0 to 1
    BRIDGE ->> CSV: Read all wallet scores

    loop For each wallet in node_scores.csv
        alt score 85 percent or above SLASH threshold
            BRIDGE ->> CONTRACT: slash(wallet, reporter)
            CONTRACT ->> REPORTER: Transfer 10% of stake reporter fee
            CONTRACT ->> TREASURY: Transfer 90% of stake
            CONTRACT -->> BRIDGE: emit WalletSlashed event
        else score 60 to 85 percent WARN zone
            BRIDGE ->> CONTRACT: updateSybilScore(wallet, score x 100)
            alt score 70 or above on contract
                CONTRACT -->> BRIDGE: emit SybilWarning + auto-suspend
            else score below 70
                CONTRACT -->> BRIDGE: emit OracleScoreUpdated
            end
        else score below 60 percent clean
            BRIDGE ->> BRIDGE: No action wallet is clean
        end
    end

    BRIDGE -->> BRIDGE: Print summary wallets slashed and ETH recovered
```

---

## D8 — Mempool Monitor Pipeline

```mermaid
flowchart TD
    subgraph WEBSOCKET["WebSocket Connection"]
        WS1["Alchemy WebSocket\nalchemy_pendingTransactions\nEthereum Mainnet"]
        WS2["Demo Mode\nSynthetic pending tx stream\n2s intervals no API key needed"]
    end

    subgraph PROCESS["Live Processing per batch of 10 txns"]
        P1["Receive pending\ntransaction hashes"]
        P2["Fetch tx details\nfrom, to, value, gas"]
        P3["Merge with baseline\ngraph 4601 nodes"]
        P4["Compute 12 node features\nfast approximation\nfor new wallets"]
        P5["GraphSAGE\nforward pass\n10 ms on CPU"]
        P6["Generate Sybil\nprobability score\n0.0 to 1.0"]
    end

    subgraph ALERT["Alert Classification"]
        A1{"Score threshold"}
        A2["🟢 clean\nless than 60%\nLogged only"]
        A3["🟡 warning\n60 to 85%\nAmber badge in UI"]
        A4["🔴 critical\n85% or above\nRed badge\nOracle can pre-slash"]
    end

    subgraph OUTPUT["Output"]
        O1["mempool_alerts.json\nring-buffer\ncapped at 200 entries"]
        O2["Next.js /api/mempool\npolled every 2 seconds"]
        O3["Live Feed UI\nauto-refreshing table\npending tx · probability · level"]
    end

    WS1 --> P1
    WS2 -.->|"fallback"| P1
    P1 --> P2 --> P3 --> P4 --> P5 --> P6
    P6 --> A1
    A1 -->|"less than 60%"| A2
    A1 -->|"60 to 85%"| A3
    A1 -->|"85% or above"| A4
    A2 --> O1
    A3 --> O1
    A4 --> O1
    O1 --> O2 --> O3

    style WEBSOCKET fill:#1a2a4a,color:#fff,stroke:#5c8ae6
    style PROCESS fill:#1a3a1a,color:#fff,stroke:#4caf7d
    style ALERT fill:#3a1a1a,color:#fff,stroke:#e64c4c
    style OUTPUT fill:#2a1a3a,color:#fff,stroke:#b44ce6
```

---

## D9 — zk-SNARK Proof Flow

```mermaid
sequenceDiagram
    participant USER as User Browser
    participant SCORES as node_scores.csv
    participant CIRCUIT as HumanityProof.circom Circom Circuit
    participant PROVER as snarkjs Groth16 Prover
    participant DAPP as dApp Frontend
    participant CONTRACT as ZKVerifier.sol

    USER ->> SCORES: Look up my wallet Sybil score
    SCORES -->> USER: sybilScore = 42 below threshold 70

    Note over USER, PROVER: Proof Generation runs locally in browser

    USER ->> CIRCUIT: Private inputs walletAddress secret salt sybilScore 42
    USER ->> CIRCUIT: Public inputs threshold 70 commitment Poseidon hash

    CIRCUIT ->> CIRCUIT: Constraint 1 sybilScore less than threshold
    CIRCUIT ->> CIRCUIT: Constraint 2 Poseidon wallet secret equals commitment
    CIRCUIT ->> PROVER: Satisfied witness
    PROVER -->> USER: Groth16 Proof pi_a pi_b pi_c about 300 bytes

    Note over USER, CONTRACT: Anonymous On-Chain Submission

    USER ->> DAPP: Submit proof and public signals no wallet address revealed
    DAPP ->> CONTRACT: verifyProof(proof, publicSignals)
    CONTRACT ->> CONTRACT: Check nullifier replay protection
    CONTRACT ->> CONTRACT: Verify Groth16 pairing
    CONTRACT -->> DAPP: emit AnonymousCredentialVerified
    DAPP -->> USER: Access granted identity never revealed
```

---

## D10 — Cross-Chain Bridge Topology

```mermaid
flowchart TD
    subgraph ETH["Ethereum Mainnet"]
        E1["ETH Transaction Graph\n50000 txns\n4601 wallets"]
        E2["ETH Node Features\n12 base features per wallet"]
    end

    subgraph L2["Layer 2 Polygon or Arbitrum"]
        L2TXN["L2 Transaction Graph\ncross-chain activity"]
        L2FEAT["L2 Node Features\n12 base features per wallet"]
    end

    subgraph BRIDGEADDR["Known Bridge Contracts"]
        B1["Bridge Addresses\nPolygon PoS Bridge\nArbitrum Bridge"]
    end

    subgraph CROSSGNN["Cross-Chain GNN Layer"]
        C1["Unified Multi-Chain Graph\nETH nodes + L2 nodes\nBridge edges connect chains"]
        C2["17 Cross-Chain Features\nbridge frequency, chain hop count\ninter-chain timing, value discrepancy"]
        C3["GraphSAGE Extended\ntrained on unified graph\ndetects cross-chain Sybil rings"]
        C4["Cross-Chain Sybil Scores\ncombined probability\nfrom multi-chain topology"]
    end

    subgraph ENFORCEMENT["On-Chain Enforcement"]
        SC1["SybilNetBridge.sol\nL2 bridge contract\nreplicates slashing cross-chain"]
        SC2["SybilNet.sol\nETH mainnet enforcement\ncore credential management"]
    end

    E1 --> E2
    L2TXN --> L2FEAT
    E2 --> C1
    L2FEAT --> C1
    B1 -->|"bridge edges"| C1
    C1 --> C2 --> C3 --> C4
    C4 --> SC1
    C4 --> SC2

    style ETH fill:#eef2ff,stroke:#5c8ae6
    style L2 fill:#f0fff0,stroke:#4caf7d
    style BRIDGEADDR fill:#fff8ee,stroke:#e6a34c
    style CROSSGNN fill:#ffeef2,stroke:#e64c7d
    style ENFORCEMENT fill:#f2eeff,stroke:#7d4ce6
```

---

## D11 — Governance & DAO Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending : createProposal()\nRequires Active Humanity Credential

    Pending --> Active : Voting period begins\n3-day window opens

    Active --> Succeeded : Voting closes\nquorum 10 percent met\nmajority voted FOR

    Active --> Defeated : Voting closes\nquorum not met OR\nmajority voted AGAINST

    Active --> Cancelled : Proposer withdraws\nOR admin cancels

    Succeeded --> Queued : Execution delay begins\n1-day timelock for safety

    Queued --> Executed : execute() called after timelock\ntarget function called on SybilNet.sol

    Queued --> Expired : Execution window passed\nwithout execute() call

    note right of Executed
        SLASH_APPEAL calls liftSuspension
        PARAMETER_CHANGE calls setMinStake etc
        ROLE_CHANGE calls grantRole or revokeRole
    end note

    note right of Active
        One-Human-One-Vote
        Only Active credential holders
        can vote FOR AGAINST or ABSTAIN
    end note
```

---

## D12 — Trust-Verified Marketplace Ecosystem

```mermaid
flowchart TD
    subgraph GNN_LAYER["🧠 GNN Trust Score"]
        G1["GraphSAGE Model\nSybil probability 0-100 per wallet"]
    end

    subgraph CONTRACT_LAYER["⛓️ SybilNet.sol"]
        CRED["✅ Humanity Credential\nActive ERC-721\nstake locked"]
        SLASH["🚨 Slashed\nBanned 365 days"]
        GATE{"isVerifiedHuman()"}
        G1 -->|"score less than 70"| CRED
        G1 -->|"score 70 or above"| SLASH
        CRED --> GATE
    end

    subgraph PILLAR1["🔄 Pillar 1 — Zero Wash-Trade Exchange"]
        P1A["NFT Marketplace\nOnly verified humans can list and trade"]
        P1B["Airdrop Distribution\nTokens go to real people not bot fleets"]
    end

    subgraph PILLAR2["💳 Pillar 2 — Undercollateralised Credit Hub"]
        P2A["DeFi Lending\nTrust score = collateral\nhigh score means bigger loan"]
        P2B["Automatic Recall\nAnomaly detected\nloan auto-recalled by GNN"]
    end

    subgraph PILLAR3["🌾 Pillar 3 — Sybil-Resistant Yield Hub"]
        P3A["Liquidity Mining\nRewards only to verified humans"]
        P3B["Scaled Rewards\nHigher trust score = higher yield share"]
    end

    subgraph ZK_LAYER["🔐 Optional — Anonymous Access via zk-SNARK"]
        ZK["Groth16 Proof\nProve humanity without\nrevealing wallet address"]
    end

    GATE -->|"true — access granted"| PILLAR1
    GATE -->|"true — access granted"| PILLAR2
    GATE -->|"true — access granted"| PILLAR3
    GATE -->|"false — access denied"| BLOCKED["❌ Blocked\nShown Sybil probability"]
    ZK -.->|"anonymous access path"| PILLAR1
    ZK -.->|"anonymous access path"| PILLAR2
    ZK -.->|"anonymous access path"| PILLAR3

    style GNN_LAYER fill:#1a3a1a,color:#fff,stroke:#4caf7d
    style CONTRACT_LAYER fill:#3a1a1a,color:#fff,stroke:#e64c4c
    style PILLAR1 fill:#1a2a4a,color:#fff,stroke:#5c8ae6
    style PILLAR2 fill:#1a2a4a,color:#fff,stroke:#5c8ae6
    style PILLAR3 fill:#1a2a4a,color:#fff,stroke:#5c8ae6
    style ZK_LAYER fill:#2a1a3a,color:#fff,stroke:#b44ce6
```

---

## D13 — 8-Week Project Roadmap (Gantt)

```mermaid
gantt
    title Sybil-Net — 8-Week Development Roadmap
    dateFormat  YYYY-MM-DD
    axisFormat  Week %W

    section Week 1 — Data Pipeline
    Blockchain data ingestion Alchemy API       :done, w1a, 2026-09-01, 2d
    NetworkX graph builder                       :done, w1b, after w1a, 2d
    12-feature extractor                         :done, w1c, after w1b, 2d
    PyVis visualiser and CSV exports             :done, w1d, after w1c, 1d

    section Week 2 — GNN Model
    GraphSAGE architecture SybilSAGE             :done, w2a, 2026-09-08, 2d
    Training loop and hyperparameter tuning      :done, w2b, after w2a, 3d
    node_scores.csv generation                   :done, w2c, after w2b, 2d

    section Week 3 — Smart Contract
    SybilNet.sol core contract                   :done, w3a, 2026-09-15, 3d
    Hardhat test suite 22 tests                  :done, w3b, after w3a, 2d
    oracle_bridge.py                             :done, w3c, after w3b, 2d

    section Week 4 — Marketplace UI
    Next.js 16 dashboard scaffold                :done, w4a, 2026-09-22, 2d
    RainbowKit wallet connect                    :done, w4b, after w4a, 1d
    3-pillar marketplace and API routes          :done, w4c, after w4b, 4d

    section Week 5 — Mempool Monitor
    Alchemy WebSocket listener                   :done, w5a, 2026-09-29, 2d
    Live GNN inference pipeline                  :done, w5b, after w5a, 2d
    Frontend live feed 2s poll                   :done, w5c, after w5b, 3d

    section Week 6 — zk-SNARK Layer
    Circom HumanityProof circuit                 :done, w6a, 2026-10-06, 3d
    Groth16 prover and ZKVerifier.sol            :done, w6b, after w6a, 2d
    ZKProofPanel frontend                        :done, w6c, after w6b, 2d

    section Week 7 — Cross-Chain Bridge
    17 cross-chain GNN features                  :done, w7a, 2026-10-13, 3d
    SybilNetBridge.sol and test suite            :done, w7b, after w7a, 2d
    CrossChainPanel frontend analytics           :done, w7c, after w7b, 2d

    section Week 8 — Governance and DAO
    SybilNetGovernance.sol                       :done, w8a, 2026-10-20, 3d
    Slash appeal voting mechanism                :done, w8b, after w8a, 2d
    GovernancePanel frontend                     :done, w8c, after w8b, 2d
```

---

## D14 — Slash Fund Distribution

```mermaid
flowchart TD
    SYBIL["🚨 Sybil Wallet\nDetected by GNN\nscore 85% or above"]
    ORACLE["🤖 Oracle Wallet\noracle_bridge.py\ncalls slash()"]

    SYBIL -->|"staked 0.01 ETH"| CONTRACT["⛓️ SybilNet.sol\nslash() function"]
    ORACLE --> CONTRACT

    CONTRACT --> BURN["🔥 Credential Burned\nStatus set to Revoked\n365-day ban applied"]
    CONTRACT -->|"slashReporterFeeBps 1000\n10% reporter fee"| REPORTER["📢 Reporter Wallet\noracle or whistleblower\nreceives 0.001 ETH"]
    CONTRACT -->|"remaining 90%"| TREASURY["🏦 Protocol Treasury\nGnosis Safe multisig\nreceives 0.009 ETH"]

    TREASURY --> DAO["🏛️ DAO Governance\nfunds community treasury\nused for protocol operations"]

    NOTE["Fee cap enforced\nslashReporterFeeBps max 3000 = 30%\nprotects against oracle self-dealing"]

    style SYBIL fill:#ffeaea,stroke:#e64c4c
    style CONTRACT fill:#f0eaff,stroke:#7d4ce6
    style REPORTER fill:#eaffea,stroke:#4caf7d
    style TREASURY fill:#eaeaff,stroke:#4c7de6
    style DAO fill:#fff8ea,stroke:#e6c34c
    style NOTE fill:#f5f5f5,stroke:#aaa,color:#555
```

---

## D15 — Feature Extraction Pipeline

```mermaid
flowchart LR
    subgraph INPUT["Input — NetworkX DiGraph"]
        G["Directed Weighted Graph\nNodes = wallet addresses\nEdges = transactions"]
    end

    subgraph STRUCTURAL["Structural Features"]
        F1["1. in_degree\nInbound edges count"]
        F2["2. out_degree\nOutbound edges count"]
        F3["3. total_tx\nWeighted tx count"]
        F4["4. unique_interactions\nDistinct neighbours"]
    end

    subgraph ECONOMIC["Economic Features"]
        F5["5. avg_value_sent\nMean ETH per outbound tx"]
        F6["6. avg_gas\nMean gas per tx"]
    end

    subgraph TEMPORAL["Temporal Features"]
        F7["7. tx_frequency\nTxns per active day"]
        F8["8. node_age_days\nDays since first tx"]
    end

    subgraph TOPOLOGICAL["Topological Features"]
        F9["9. reciprocity\nFraction of mutual edges"]
        F10["10. clustering_coeff\nLocal clustering coefficient"]
        F11["11. betweenness_centrality\nBridge score in graph"]
        F12["12. pagerank\nGlobal influence score"]
    end

    subgraph SCALER["Preprocessing"]
        SCALE["RobustScaler\nnormalise extreme outliers\ndegree variance"]
    end

    subgraph OUTPUT_MAT["Output — GNN Input"]
        MAT["Feature Matrix X\nN x 12 matrix\n4601 wallets\nReady for GraphSAGE"]
    end

    G --> F1
    G --> F2
    G --> F3
    G --> F4
    G --> F5
    G --> F6
    G --> F7
    G --> F8
    G --> F9
    G --> F10
    G --> F11
    G --> F12

    F1 --> SCALE
    F2 --> SCALE
    F3 --> SCALE
    F4 --> SCALE
    F5 --> SCALE
    F6 --> SCALE
    F7 --> SCALE
    F8 --> SCALE
    F9 --> SCALE
    F10 --> SCALE
    F11 --> SCALE
    F12 --> SCALE

    SCALE --> MAT

    style INPUT fill:#1a2a4a,color:#fff
    style STRUCTURAL fill:#1a3a1a,color:#fff
    style ECONOMIC fill:#2a2a1a,color:#fff
    style TEMPORAL fill:#3a1a1a,color:#fff
    style TOPOLOGICAL fill:#1a1a3a,color:#fff
    style SCALER fill:#2a1a3a,color:#fff
    style OUTPUT_MAT fill:#1a2a3a,color:#fff
```

---

> **Tips for draw.io:**
> - Go to `Extras` → `Edit Diagram` → paste the full mermaid block (including ` ```mermaid ` fences)
> - After importing, select all → `Format` → `Auto-layout` for best spacing
> - Use `Edit Style` on any node to change colours, fonts, and borders
> - Export as **SVG** for crisp vector output in your report PDF
> - Export as **PNG 300 DPI** for Word or PowerPoint embedding
> - For the Gantt chart (D13), draw.io will render it as a timeline bar chart — use `View` → `Fit Page` after import
