# Smart Contract Documentation
# SybilNet.sol

## Overview

`SybilNet.sol` is the on-chain enforcement layer of the Sybil-Net protocol. It allows users to stake ETH and receive a **Humanity Credential** that proves they are a verified human on the blockchain. A trusted GNN oracle continuously monitors the transaction graph and can slash (destroy) the stake of any wallet identified as a Sybil attacker.

---

## Contract Details

| Property | Value |
|---|---|
| Solidity version | 0.8.24 |
| License | MIT |
| OpenZeppelin modules | AccessControl, ReentrancyGuard, Pausable |
| Network | Ethereum Mainnet / Sepolia testnet / Local Hardhat |
| Default min stake | 0.01 ETH |
| Ban duration | 365 days |
| Default slash reporter fee | 10% (1000 bps) |

---

## Roles

### `DEFAULT_ADMIN_ROLE`
The protocol administrator. In production this should be a multisig wallet (e.g. Gnosis Safe).

**Can:**
- Update `minStake`
- Update `treasury` address
- Update `slashReporterFeeBps`
- Grant / revoke all roles

### `ORACLE_ROLE`
The GNN backend service wallet. This account reads `node_scores.csv` via `oracle_bridge.py` and submits on-chain calls.

**Can:**
- `updateSybilScore()` — push new GNN score
- `slash()` — destroy a wallet's stake
- `batchSlash()` — slash multiple wallets in one tx
- `liftSuspension()` — clear a false positive

### `GUARDIAN_ROLE`
Emergency responder. Can pause and unpause the entire protocol.

**Can:**
- `pause()` / `unpause()`

---

## Functions

### User Functions

#### `mintCredential()`
```solidity
function mintCredential() external payable
```
Stakes ETH and issues a Humanity Credential to the caller.

| Parameter | Description |
|---|---|
| `msg.value` | Must be >= `minStake` (default 0.01 ETH) |

**Reverts if:**
- Stake below minimum → `InsufficientStake`
- Already has active credential → `CredentialAlreadyActive`
- Wallet is banned within 365-day window → `WalletBanned`
- Contract is paused → `EnforcedPause`

**Emits:** `CredentialMinted(address wallet, uint256 stakedAmount, uint256 timestamp)`

---

#### `withdrawStake()`
```solidity
function withdrawStake() external
```
Voluntarily surrender the Humanity Credential and retrieve staked ETH.

**Reverts if:**
- No active credential → `NoActiveCredential`
- Credential is Suspended (oracle review pending) → `NoActiveCredential`

**Emits:** `StakeWithdrawn`, `CredentialRevoked`

---

### Oracle Functions

#### `updateSybilScore(address wallet, uint256 newScore)`
```solidity
function updateSybilScore(address wallet, uint256 newScore) external onlyRole(ORACLE_ROLE)
```
Push a new Sybil risk score from the GNN. Score range: 0–100.

| Score Range | Meaning | Action |
|---|---|---|
| 0 – 29 | Clean | No action |
| 30 – 69 | Warning zone | Score recorded, emits event |
| 70 – 100 | High risk | Auto-suspends credential |

**Reverts if:** `newScore > 100` → `ScoreOutOfRange`

**Emits:** `OracleScoreUpdated`, optionally `SybilWarning`

---

#### `slash(address wallet, address payable reporter)`
```solidity
function slash(address wallet, address payable reporter) external onlyRole(ORACLE_ROLE)
```
Slash a Sybil attacker. Destroys their staked ETH and bans them for 365 days.

**Fund distribution:**
```
slashedAmount × slashReporterFeeBps / 10000  →  reporter
slashedAmount − reporterFee                   →  treasury
```

**Emits:** `WalletSlashed`, `CredentialRevoked`

---

#### `batchSlash(address[] calldata wallets, address payable reporter)`
```solidity
function batchSlash(address[] calldata wallets, address payable reporter) external onlyRole(ORACLE_ROLE)
```
Gas-efficient batch slash for entire bot rings identified by the GNN in a single transaction. Silently skips wallets that are not slashable.

---

#### `liftSuspension(address wallet)`
```solidity
function liftSuspension(address wallet) external onlyRole(ORACLE_ROLE)
```
Clears a Suspended credential and resets its Sybil score to 0. Used when the oracle re-evaluates a wallet and determines it was a false positive.

---

### View Functions

#### `isVerifiedHuman(address wallet) → bool`
Returns `true` only if the wallet holds a currently **Active** Humanity Credential. This is the primary gate function used by the Marketplace contracts.

```solidity
// Marketplace integration example:
require(sybilNet.isVerifiedHuman(msg.sender), "Humanity Credential required");
```

#### `getSybilScore(address wallet) → uint256`
Returns the current GNN Sybil score (0–100) for a wallet.

#### `getCredential(address wallet) → Credential`
Returns the full credential struct:
```solidity
struct Credential {
    CredentialStatus status;      // None | Active | Suspended | Revoked
    uint256 stakedAmount;         // ETH currently locked
    uint256 issuedAt;             // Unix timestamp of minting
    uint256 sybilScore;           // 0–100, updated by oracle
    uint256 slashedAt;            // Unix timestamp of slash (0 if not slashed)
    uint256 warnCount;            // number of oracle warnings received
}
```

---

## Events

| Event | Parameters | When |
|---|---|---|
| `CredentialMinted` | `wallet, stakedAmount, timestamp` | Successful stake + mint |
| `CredentialRevoked` | `wallet, reason` | Slash or voluntary withdrawal |
| `SybilWarning` | `wallet, newScore, warnCount` | Score crosses 70 threshold |
| `WalletSlashed` | `wallet, slashedAmount, reporterFee, reporter` | Oracle slash |
| `StakeWithdrawn` | `wallet, amount` | Voluntary exit |
| `OracleScoreUpdated` | `wallet, oldScore, newScore` | Any score update |
| `MinStakeUpdated` | `oldMin, newMin` | Admin changes minimum |
| `TreasuryUpdated` | `oldTreasury, newTreasury` | Admin changes treasury |

---

## Custom Errors

| Error | Parameters | Cause |
|---|---|---|
| `InsufficientStake` | `sent, required` | msg.value < minStake |
| `CredentialAlreadyActive` | — | Wallet already verified |
| `NoActiveCredential` | — | Wallet has no Active credential |
| `WalletBanned` | `wallet, bannedUntil` | Within 365-day post-slash ban |
| `ScoreOutOfRange` | `score` | Oracle submitted score > 100 |
| `NothingToWithdraw` | — | Stake already zero |
| `TransferFailed` | — | ETH transfer rejected |
| `InvalidAddress` | — | Zero address passed |
| `InvalidBps` | `bps` | Reporter fee > 30% (3000 bps) |

---

## Deployment

### Local (Hardhat)
```bash
cd contracts
npx hardhat node                                      # start local chain
npx hardhat run scripts/deploy.js --network localhost # deploy
```

### Sepolia Testnet
Add to `../.env`:
```
DEPLOYER_PRIVATE_KEY=0x...your_private_key...
```
Then:
```bash
npx hardhat run scripts/deploy.js --network sepolia
```

---

## Testing

```bash
cd contracts
npx hardhat test          # run all 22 tests
npx hardhat coverage      # generate coverage report
```

### Test Coverage

| Suite | Tests | Coverage |
|---|---|---|
| Deployment | 3 | Treasury, minStake, admin role |
| mintCredential() | 4 | Happy path, insufficient stake, duplicate, totalStaked |
| updateSybilScore() | 4 | Score update, auto-suspend, range validation, access control |
| slash() | 3 | Fund distribution, totalSlashed, no-credential revert |
| batchSlash() | 1 | Multi-wallet slash |
| withdrawStake() | 1 | Balance return, credential revocation |
| Ban mechanism | 1 | Re-mint blocked within 365 days |
| Emergency pause | 2 | Pause blocks mint, unpause resumes |
| Admin controls | 3 | setMinStake, setSlashReporterFee, fee cap |
| **Total** | **22** | **All passing** |

---

## Oracle Bridge Integration

The Python bridge (`contracts/oracle_bridge.py`) connects the trained GNN to the contract:

```bash
# 1. Set environment variables in ../.env:
SYBILNET_ADDRESS=0x...deployed_contract...
ORACLE_PRIVATE_KEY=0x...oracle_wallet_key...
RPC_URL=http://127.0.0.1:8545
SLASH_THRESHOLD=85   # score >= 85 → slash
WARN_THRESHOLD=60    # score 60-84 → score update only

# 2. Run GNN pipeline first to generate node_scores.csv
python models/gnn.py

# 3. Run oracle bridge
python contracts/oracle_bridge.py
```

The bridge:
1. Reads `node_scores.csv` (GNN output)
2. Converts probabilities to 0–100 scores
3. Calls `updateSybilScore()` for warn-level wallets
4. Calls `slash()` for high-confidence Sybil wallets
5. Reports total ETH slashed on-chain
