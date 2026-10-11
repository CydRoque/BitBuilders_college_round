# Fairwork: Phase 2 PRD (Advanced Features Add-On)

**Companion to:** `prd.md` (base build)
**Purpose:** Each feature below was cut from the base build to fit 10-15h. This document specifies how to add each one on top of the base without rewriting it. Every feature is independently shippable and can be done in any order that respects the dependency notes in section 3.

---

> **Status update (base `prd.md` is now v2).** Parts of this document moved into the base build:
>
> | Feature | What moved into the base | What remains here |
> |---|---|---|
> | F: Factory per project | `FairworkFactory.sol` deploying `FreelanceAgreement.sol` via `new` | Optional switch to EIP-1167 clones if contract size or gas becomes a problem |
> | C: 2-of-3 multi-sig | Propose/approve settlement with client, freelancer, and admin | `settleByTimeout` (stretch in the base) and the arbiter-registry ideas |
> | E: ERC-4337 | Privy login with embedded/smart wallets; the frontend sends transactions; backend faucet as fallback | Sponsorship policy hardening. The custodial relayer no longer exists, so the `WALLET_MODE` hook in section 2 is obsolete |
> | G: Chainlink Functions | A backend-key `resolveByOracle` stretch with the same interface | Replace the backend oracle key with a Chainlink Functions consumer |
>
> Time estimates for C, E, and F in sections 1 and 4 are now smaller than listed. Features A (SBT), B (scope-creep tax), and D (ZK identity) are unchanged.

## 1. Reality Check on Time

| # | Feature | Est. | Risk | Demo visibility |
|---|---|---|---|---|
| A | Soulbound reputation token (SBT) | 1.5-2h | Low | High (profile page) |
| B | Scope-creep tax (addendum flow) | 2h | Low | Medium |
| C | 2-of-3 multi-sig arbitration | 3h | Low-Med | High (dispute screen) |
| D | ZK identity (EAS attestations, then zkPass proofs) | 4-6h | Med-High | High (verified badges) |
| E | ERC-4337 smart accounts + Paymaster | 4-6h | Med-High | Very high (login + gasless) |
| F | Factory-deployed contract per project | 3-4h | Med | Low (architecture credit) |
| G | Chainlink Functions AI oracle | 5-7h | High | Medium (hard to show live) |
| | **All seven** | **~25h** | | |

The base build is ~13.5h of a 24h window, leaving roughly 10h. **All seven will not fit.** Section 4 gives bundles that do.

## 2. Design Hooks to Add to the Base Build NOW (about 1h total, saves hours later)

These are small decisions that make every feature below additive instead of a refactor. Do them while writing the base.

| Hook | Where | Why it helps |
|---|---|---|
| Internal `_settle(id, idx, freelancerBps)` that does the payout split; `resolveDispute` only checks the caller and calls it | Contract | Multi-sig (C) and the Chainlink flow (G) just become new callers of `_settle` |
| Optional hook addresses `reputation` and `verifier`, both default to `address(0)` = disabled | Contract | SBT (A) and verification gating (D) turn on with one setter call, no redeploy logic changes |
| All logic keyed by `projectId`, `Project storage p = projects[id]` everywhere | Contract | Moving to per-project clones (F) becomes mechanical |
| Reserve extra enum values: `Milestone.AwaitingArbitration`, `Milestone.AddendumPending` | Contract | Indexer and DB enums stay stable |
| Wallet access behind one interface: `WalletProvider { addressFor(user); send(user, call) }` | Backend | Custodial relayer and ERC-4337 (E) become two implementations behind a `WALLET_MODE` flag |
| Split "upload to IPFS" from "send transaction" into two internal functions | Backend | In AA mode the frontend sends the transaction, backend only returns the CID |
| Indexer takes a **list** of contract addresses from config, not one constant | Backend | Factory (F) needs this; SBT (A) needs it too |
| Dispute pipeline as three steps: `evaluate() -> publish() -> settle()`, with `settle` swappable | Backend | Swap admin resolve for multi-sig proposal (C) or oracle (G) |
| Nullable DB columns: `Project.contractAddress`, `User.attestationUid`, `Dispute.oracleRequestId`, `User.sbtCount` | DB | No migration pain mid-hackathon |

## 3. Dependency Notes

```
A (SBT)  -- independent. If F is later added, factory must register each clone as an allowed minter.
B (Scope tax) -- independent.
C (Multi-sig) -- independent. G feeds into C's proposal if both exist.
D (ZK/EAS) -- independent. Uses verifier hook.
E (4337) -- changes WHO sends transactions. Touches auth, wallet service, and the frontend. Coordinate with UI teammate.
F (Factory) -- changes WHERE state lives. Touches deploy, indexer, and every contract address the API returns.
G (Chainlink) -- needs a publicly reachable backend URL and LINK on testnet. Best done after C.
```

**Do not do E and F in the same stretch.** Both change the plumbing that everything else rides on, and a bug in either is hard to isolate.

## 4. Recommended Bundles

| Bundle | Contents | Est. | Why |
|---|---|---|---|
| **1: Contract-only wins** | A + B + C | ~6.5-7h | No new wallet SDKs, no frontend risk. Directly hits "participant protection" and "dispute resolution" in the problem statement. |
| **2: Trust and UX layer** | D (EAS first, zkPass if time) + E | ~8-12h | The two flashiest features for judges, but both depend on frontend SDKs. Plan with your teammate before starting. |
| **3: Architecture depth** | F + G | ~8-11h | Only if you finish 1 and 2 early. Mostly invisible in a live demo, so pitch them as roadmap with the hooks already in place. |

If you can only pick one thing beyond Bundle 1, pick **E**: a gasless Google login is the first thing a judge sees.

---

## 5. Feature Specs

### A. Soulbound Reputation Token (SBT)

**Goal:** Every completed project mints a non-transferable credential to the freelancer, forming verifiable on-chain reputation.

**Contract: `FairworkSBT.sol`**
- ERC-721 with transfers blocked. Override `_update` (OpenZeppelin v5) so it reverts unless `from == address(0)` (mint only). Implement ERC-5192 `locked(tokenId) -> true`.
- `mintCompletion(address to, uint256 projectId, uint256 totalPaid, uint8 onTimeMilestones, uint8 totalMilestones)`, callable only by addresses with `MINTER_ROLE`.
- Store a `Credential` struct per token; `tokenURI` returns on-chain base64 JSON (project id, totals, on-time ratio) so no extra IPFS work.
- `Fairwork.sol` calls `reputation.mintCompletion(...)` inside `ProjectCompleted` when the hook address is non-zero.

**Backend**
- Indexer handles the `Transfer` (mint) event.
- `GET /users/:id/reputation` returns `{ completedProjects, onTimeRate, totalEarned, disputesLost, credentials[] }`.
- Optional negative signal for clients: count of `AutoReleased` events as a "slow reviewer" stat (backend only, not on-chain).

**Acceptance**
- [ ] Completing a project mints exactly one token to the freelancer.
- [ ] `transferFrom` and `safeTransferFrom` revert.
- [ ] `/reputation` matches on-chain data.

---

### B. Scope-Creep Tax (Addendum Flow)

**Goal:** A client cannot quietly change requirements mid-project. Any scope change requires the freelancer's acceptance plus a fee paid into escrow.

**Rules**
| Change | Needs freelancer acceptance | Fee |
|---|---|---|
| Edit spec / acceptance criteria (`specCid`) | Yes | `SCOPE_FEE_BPS` (10-15%) of the original milestone amount |
| Increase milestone amount | Yes | Extra amount deposited, plus the fee above |
| Shorten deadline | Yes | Same fee |
| Extend deadline | Yes | No fee |
| Any change after `Submitted` | Not allowed | n/a |

The fee is deposited into the milestone's escrow and paid to the freelancer on approval, compensating the rework.

**Contract**
```solidity
struct Addendum { uint256 newAmount; uint64 newDeadline; string newSpecCid; uint256 deposit; bool exists; }

function proposeAddendum(id, idx, newAmount, newDeadline, newSpecCid) external; // client; pulls extra amount + fee
function acceptAddendum(id, idx) external;   // freelancer; applies new terms
function rejectAddendum(id, idx) external;   // freelancer; refunds client's deposit
function withdrawAddendum(id, idx) external; // client; only while not yet accepted
```
- Milestone status `AddendumPending` blocks submission until resolved (this is the reserved enum value).
- Events: `AddendumProposed, AddendumAccepted, AddendumRejected`.

**Backend and API**
- `POST /milestones/:id/addendum` (client), `POST /milestones/:id/addendum/accept|reject` (freelancer), `GET /milestones/:id/addendum`.
- Pin the new spec JSON to IPFS before calling `proposeAddendum`. Keep old spec CIDs in the audit trail so the history of scope changes is visible.

**Acceptance**
- [ ] Spec change without the fee reverts.
- [ ] Freelancer rejection fully refunds the client.
- [ ] Accepted addendum updates amount, deadline, and spec, and the fee is paid out with that milestone.

---

### C. 2-of-3 Multi-Sig Arbitration

**Goal:** No single party (including our backend) can settle a dispute alone.

**Recommendation:** implement the 2-of-3 logic **inside the contract**, not with Safe. It is faster, easier to test, and easier to demo. Safe can be mentioned as a production option.

**Flow**
1. Dispute opens. Backend generates the AI report (base PRD section 5.5) and the arbiter posts a proposal that includes the report CID and the AI's recommended split.
2. Client or freelancer **approves** the proposal (2 of 3 reached, so it executes via `_settle`), or **counter-proposes** a different split.
3. Any party can approve any open proposal. The first proposal to reach 2 approvals executes.
4. Timeout: if nothing reaches 2 approvals within `ARBITRATION_TIMEOUT` (e.g. 14 days), anyone may call `settleByTimeout`, which applies a default 50/50 split (configurable).

**Contract**
```solidity
struct Proposal { uint16 freelancerBps; string reportCid; address proposer; uint8 approvals; mapping(address=>bool) approved; bool executed; }

function proposeSettlement(id, idx, freelancerBps, reportCid) external; // client, freelancer, or arbiter
function approveSettlement(id, idx, proposalId) external;               // any of the three; proposer counts as approval 1
function settleByTimeout(id, idx) external;
```
- Replace the base `resolveDispute` with the above; keep `_settle` unchanged.
- Events: `SettlementProposed, SettlementApproved, DisputeResolved`.

**Backend and API**
- `settle()` step in the dispute pipeline becomes "arbiter proposes with the AI report attached".
- `GET /disputes/:id/proposals`, `POST /disputes/:id/proposals` (propose), `POST /disputes/:id/proposals/:pid/approve`.
- The admin resolve endpoint is retained only as a dev override behind a feature flag.

**Acceptance**
- [ ] Arbiter alone cannot execute.
- [ ] Freelancer plus arbiter executes; client plus arbiter executes; client plus freelancer (agreeing on a split) executes.
- [ ] Timeout path works with a shortened `DAY`.

---

### D. ZK Identity Verification (EAS + zkPass)

**Goal:** Users prove claims about themselves without Fairwork storing raw documents; the proof becomes a reusable on-chain attestation.

**Build in two layers so there is always a working demo:**

**Layer 1 (about 2-3h): EAS attestations with a pluggable proof source**
- Register an EAS schema, for example `address subject, string claimType, bool verified`. On OP-stack chains such as Base, EAS is a predeploy (verify the address in the EAS docs for your chain).
- Attach a **schema resolver** contract, `VerifiedRegistry`. Its `onAttest` only accepts the Fairwork backend key as attester and sets `isVerified[recipient][claimType] = true`; `onRevoke` clears it.
- Backend `POST /verify/:provider` runs a provider adapter, and on success issues the attestation. Ship with a **non-ZK adapter first** (for example GitHub OAuth or the mocked flow from the base build) so the end-to-end path is real.
- Fairwork's `verifier` hook calls `VerifiedRegistry.isVerified(...)`. Optional gating flags: `requireVerifiedClient` on `createProject`, `requireVerifiedFreelancer` on acceptance.

**Layer 2 (about 2-3h): zkPass adapter**
- Frontend uses the zkPass TransGate SDK to generate a proof for a chosen schema. Backend `POST /verify/zkpass` receives the result and verifies the validator signature as described in zkPass docs, then issues the same EAS attestation.
- **Check the zkPass schema marketplace before promising anything.** Available schemas are mostly social/professional accounts and exchange KYC. Passport-specific or degree-specific claims may not exist. Pitch what you actually build (for example "proof of verified exchange KYC without sharing documents"), not the passport/degree example from the original prompt.
- Company verification: use a `business` claim type. Unless a suitable schema exists, keep this one mocked and say so.
- You will need a zkPass developer app id and schema id; request these early since provisioning can take time.

**API**
- `GET /verify/providers`, `POST /verify/:provider`, `GET /users/:id/attestations`.
- Include `verifiedClaims[]` on `/me` and `/users/:id` so the frontend can show badges.

**Acceptance**
- [ ] A verified user's attestation is visible on an EAS explorer and returned by the API.
- [ ] With gating on, an unverified client cannot create a project.
- [ ] Revoking the attestation removes the badge and re-blocks gated actions.

---

### E. ERC-4337 Smart Accounts + Paymaster

**Goal:** Replace the custodial relayer with real smart accounts. Users still log in with Google, but they own the account, and a paymaster sponsors gas.

**Stack options (pick ONE; choose by who gives free Base Sepolia sponsorship and the best docs when you start)**
| Option | Notes |
|---|---|
| Privy (social login, embedded signer) + permissionless.js + Pimlico (bundler and paymaster) | Modular, well documented, wide chain support |
| ZeroDev (Kernel accounts, bundler, paymaster) | Single vendor, social login via integrations |
| Alchemy Account Kit | Single vendor with a gas manager |

Confirm current SDK versions and testnet support in each vendor's docs before choosing.

**Architecture change**
- Frontend: social login yields an owner signer, which yields a smart account. The frontend sends UserOperations for contract calls (`createProject`, `fundProject`, `approveMilestone`, etc.).
- Backend becomes **auth + IPFS + indexing + sponsorship policy**, no longer the transaction sender.
  - `WALLET_MODE=aa` flag. `custodial` mode stays as the fallback you can demo if the vendor has an outage.
  - Auth: verify the vendor's JWT instead of the Google ID token; store the smart account address (counterfactual addresses work, so a freelancer can be assigned before their account is deployed).
  - New: `GET /contracts/config` returns contract addresses and ABIs for the frontend.
  - Changed: `POST /uploads` returns `{cid}`; the frontend then sends `submitMilestone` itself.
  - Sponsorship policy (webhook or dashboard rules): only sponsor calls to Fairwork, USDC, and SBT contracts; per-user rate limit; reject anything else.
- **Contracts need no change.** They only see `msg.sender`, which is now the smart account.
- Demo USDC: the faucet mints to the smart account address.

**Frontend impact (coordinate early):** wallet SDK setup, UserOp sending, transaction status UI. Plan roughly 2h on the UI teammate's side in addition to your 4-6h.

**Acceptance**
- [ ] New Google user gets a smart account with no ETH and completes a full project lifecycle.
- [ ] Non-Fairwork calls are rejected by the sponsorship policy.
- [ ] Flipping `WALLET_MODE=custodial` still works end to end.

---

### F. Factory-Deployed Contract Per Project

**Goal:** Each project gets its own isolated contract holding only its own funds.

**Contract**
- `ProjectEscrow.sol`: the base logic moved into an `initialize(client, freelancer, arbiter, token, milestones, bonusBps, hooks...)` pattern (no constructor args, since clones use it).
- `FairworkFactory.sol`: `createProject(...)` deploys an **EIP-1167 minimal proxy clone** of the implementation (OpenZeppelin `Clones`), initializes it, registers it as an SBT minter if A is installed, and emits `ProjectDeployed(projectId, escrowAddress, client, freelancer)`.
- Funds live in the clone. Each clone emits the same events as the base contract.

**Backend**
- Indexer watches the factory for `ProjectDeployed`, then adds the new clone address to the watched list (persist the list in the DB so restarts keep it). This is why the indexer-takes-a-list hook matters.
- Store `Project.contractAddress`. All write calls target that address. API responses include it.

**Migration plan from the base build**
1. Move state and functions into `ProjectEscrow`, replacing `projects[id]` with local state.
2. Update Foundry tests through a deploy helper so test bodies barely change.
3. Update the indexer and the relayer's target address resolution.
4. Redeploy and reseed. Existing testnet projects are abandoned (acceptable for a hackathon).

**Acceptance**
- [ ] Two projects have different escrow addresses; funds do not mix.
- [ ] Indexer picks up a clone created after backend startup.
- [ ] All base-build tests still pass.

---

### G. Chainlink Functions AI Oracle

**Goal:** The AI evaluation is delivered on-chain through a decentralized oracle network, making the report verifiable and not solely backend-asserted.

**Design: keep the LLM work in the backend, use Functions only to deliver the result.** Functions has tight limits (execution time and response size are small; verify the current numbers in Chainlink docs), so do not run the LLM inside the DON.

**Flow**
1. `MilestoneDisputed` fires. The backend already runs `evaluate()` and caches the result (base PRD 5.5), including `score`, `recommendedBps`, and `reportCid`.
2. Contract `requestAIEvaluation(id, idx)` sends a Functions request. The JS source calls `GET {BACKEND_URL}/oracle/disputes/:id` with a secret header and returns a compact encoded payload: `uint16 score, uint16 recommendedBps, bytes32 reportHash`.
3. `fulfillRequest` stores the values, emits `AIEvaluationReady`, and moves the milestone to `AwaitingArbitration`. If C is installed, the proposal is pre-filled from `recommendedBps`.
4. The report hash is stored on-chain, so the backend cannot alter the report afterwards.

**Setup checklist (do this in the first hour, since subscriptions and faucets cause delays)**
- [ ] Chainlink Functions subscription created on your testnet and funded with testnet LINK
- [ ] Contract added as a consumer; router address and DON id taken from the Chainlink docs for your chain
- [ ] **Backend reachable from the public internet** (deployed host or tunnel). The DON calls it, so `localhost` will not work.
- [ ] Secret header stored via Functions secrets

**Fallback (build this too):** `submitEvaluationFallback(id, idx, score, bps, hash)`, callable by the owner when `ORACLE_FALLBACK_ENABLED` is set. If the oracle is slow or down during the demo, you can still show the flow and say so openly.

**Acceptance**
- [ ] A dispute triggers a request and the callback stores the score and report hash on-chain.
- [ ] Hash on-chain equals the hash of the IPFS report.
- [ ] Fallback path works with the flag on and is rejected with the flag off.

---

## 6. API Additions Summary

| Feature | New or changed endpoints |
|---|---|
| A | `GET /users/:id/reputation` |
| B | `POST /milestones/:id/addendum`, `.../accept`, `.../reject`, `GET /milestones/:id/addendum` |
| C | `GET/POST /disputes/:id/proposals`, `POST /disputes/:id/proposals/:pid/approve` |
| D | `GET /verify/providers`, `POST /verify/:provider`, `GET /users/:id/attestations` |
| E | `GET /contracts/config`, `POST /uploads`, auth now accepts the vendor JWT |
| F | Responses include `contractAddress` |
| G | `GET /oracle/disputes/:id` (secret-header protected) |

Update `openapi.yaml` as each feature lands so the UI teammate's generated client stays in sync.

## 7. Added Data Model Fields

| Table | Fields |
|---|---|
| `User` | attestationUid, verifiedClaimsJson, sbtCount, smartAccountAddress |
| `Project` | contractAddress |
| `Milestone` | addendumJson, addendumStatus |
| `Dispute` | oracleRequestId, aiScore, aiRecommendedBps, reportHash |
| `Proposal` (new) | id, disputeId, proposer, freelancerBps, reportCid, approvals, executed |
| `Credential` (new) | tokenId, userId, projectId, totalPaid, onTimeMilestones, totalMilestones |

## 8. Pitch Guidance

- Demo what is built; label what is roadmap. Judges tend to probe the "magic" features (ZK, oracle), and a clear statement of what is real and what is mocked is more credible than overclaiming.
- If features D, E, F, or G are not finished, show the hooks from section 2 and one slide of the architecture with those pieces highlighted as the next milestone.
- Priority of what to show live: gasless login (E) > dispute with arbitration (C plus AI) > reputation token (A) > verified badges (D) > scope addendum (B).

## 9. Additional Environment Variables

```
# D
EAS_ADDRESS=
EAS_SCHEMA_UID=
VERIFIED_REGISTRY_ADDRESS=
ZKPASS_APP_ID=
ZKPASS_SCHEMA_ID=
# E
WALLET_MODE=custodial        # or aa
AA_BUNDLER_URL=
AA_PAYMASTER_URL=
AUTH_PROVIDER_APP_ID=
AUTH_PROVIDER_SECRET=
# F
FACTORY_ADDRESS=
ESCROW_IMPL_ADDRESS=
# G
CHAINLINK_ROUTER=
CHAINLINK_DON_ID=
CHAINLINK_SUBSCRIPTION_ID=
ORACLE_SECRET=
ORACLE_FALLBACK_ENABLED=false
BACKEND_PUBLIC_URL=
# A
SBT_ADDRESS=
# B
SCOPE_FEE_BPS=1000
# C
ARBITRATION_TIMEOUT_SECONDS=
```
