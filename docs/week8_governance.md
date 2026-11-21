# Week 8 — Governance & DAO

> *On-chain dispute mechanism. Credential holders vote on slash appeals. Protocol parameter governance.*

## Overview

Week 8 introduces a fully on-chain governance layer where **verified humans**
(holders of an Active Humanity Credential) can propose, vote on, and execute
protocol changes — including **slash appeal disputes**.

This completes the Sybil-Net protocol loop: the GNN detects bots and the
oracle slashes them automatically, but legitimate users who are wrongly
flagged now have a decentralised recourse mechanism.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Governance Lifecycle                            │
│                                                                        │
│   1. User flagged → credential suspended/slashed                       │
│   2. Any credential holder creates a SLASH_APPEAL proposal             │
│   3. Voting period (3 days) — one-human-one-vote                       │
│   4. If quorum (10%) met + majority FOR → proposal succeeds            │
│   5. Execution delay (1 day) — timelock for safety                     │
│   6. execute() → calls liftSuspension() on SybilNet                   │
│   7. Appealed wallet's credential is reinstated                        │
│                                                                        │
│   Proposal Types:                                                      │
│   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│   │  SLASH_APPEAL     │  │ PARAMETER_CHANGE │  │   ROLE_CHANGE    │    │
│   │  Dispute a slash  │  │ Update minStake, │  │ Grant/revoke     │    │
│   │  Reinstate cred   │  │ fees, thresholds │  │ oracle/guardian  │    │
│   └──────────────────┘  └──────────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Smart Contract: SybilNetGovernance.sol

### Roles

| Role | Description |
|------|-------------|
| `DEFAULT_ADMIN_ROLE` | Protocol admin — can update governance params |
| All credential holders | Can create proposals and vote |

### Proposal States

```
Pending → Active → Succeeded → Queued → Executed
                  └→ Defeated
                  └→ Expired (execution delay passed without execution)
             └→ Cancelled (by proposer or admin)
```

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `votingPeriod` | 3 days | Duration of the voting window |
| `executionDelay` | 1 day | Timelock after a proposal succeeds |
| `quorumBps` | 1000 (10%) | % of credential holders that must vote |

### Gas Costs

| Operation | Estimated Gas |
|-----------|---------------|
| `createProposal()` | ~130,000 |
| `castVote()` | ~65,000 |
| `executeProposal()` | ~100,000+ |

---

## Frontend: GovernancePanel

The governance dashboard integrates into the main marketplace UI and shows:

1. **Stats bar** — total proposals, active proposals, participation rate, executed count
2. **Active proposals** — live vote progress bars, time remaining, quorum indicator
3. **Create proposal form** — type selector, description, target address
4. **Recent activity feed** — latest votes, proposals, and executions

---

## How to Run

### Deploy the Governance Contract

```bash
cd contracts
npx hardhat node                                        # Start local node
npx hardhat run scripts/deploy.js --network localhost   # Deploy all contracts
```

### Run the Full Test Suite

```bash
cd contracts
npx hardhat test
# Includes SybilNet (22), Bridge (20), Governance (~25), ZK tests
```

### Launch the Frontend

```bash
cd frontend
npm run dev
# Governance panel visible at http://localhost:3000
```
