# Fairwork: Product Requirements Document (Backend-Focused) v2

**Hackathon build window:** 24h total | **Backend + contracts budget:** ~14.5h | **Frontend:** handled by teammate (Next.js) against the contracts and API in this doc

### Revision note (v2)
This version folds in the 4-step build plan (contracts, frontend/wallet, IPFS, dispute resolution). What changed from v1:
- **Factory pattern is now in scope:** `FairworkFactory.sol` deploys one `FreelanceAgreement.sol` per project.
- **2-of-3 multi-sig dispute settlement is now in scope** (client, freelancer, platform admin), implemented inside the agreement contract.
- **The custodial relayer is gone.** Users log in with Privy (external wallet or email/social, with embedded/smart wallets). The **frontend sends transactions**; the backend handles auth, IPFS, indexing, AI evaluation, and the admin signer.
- **Backend write endpoints for projects were removed** (the chain is the source of truth); replaced by IPFS-pinning endpoints and indexed read endpoints.
- Milestone struct, function names, and `raiseDispute(uint index)` follow your spec exactly (details in 5.1).
- Work plan grew from 13.5h to 14.5h.

---

## 1. Summary

Fairwork is a milestone-based freelance platform where client funds are locked in a per-project smart contract and released only when milestones are delivered and approved. Deliverables and requirements live on IPFS (only CIDs go on-chain), SLA rules (late penalty, early bonus, anti-ghosting) are enforced by code, and disputes are settled by a 2-of-3 multi-sig with an AI-generated evaluation report attached.

**Elevator pitch:** A gasless, milestone-driven freelance platform that uses per-project smart contract escrow and AI-assisted multi-sig dispute resolution so freelancers get paid fairly and clients get the work they specified, with no middleman fees.

## 2. Goals and Non-Goals

### Goals (must demo)
1. Client creates a project through the factory with milestones (deliverable spec, deadline, payout) and funds the escrow.
2. Freelancer submits work; the file is pinned to IPFS and the CID + timestamp is stored in the contract.
3. Client approves; payment releases with SLA math applied (late penalty / early bonus).
4. If the client ghosts for the review window, freelancer claims auto-release.
5. Either party can raise a dispute, which locks that milestone's funds; the backend generates an AI report; the funds move only when 2 of 3 (client, freelancer, platform admin) agree on a split.
6. If a freelancer drops out, client reassigns to a new freelancer; completed milestones stay paid and remaining funds stay in escrow.
7. Dashboard shows pending, in-review, disputed, and completed milestones, fed by the chain via the indexer.
8. Full audit trail (every state change, tx hash, CID) via API.
9. Login with a traditional wallet **or** email/Google, without users ever handling gas.

### Decision log: what is in, what is stretch, what is out
| Feature | Status in v2 |
|---|---|
| Factory-deployed contract per project | **In base** (`new FreelanceAgreement(...)` from the factory) |
| 2-of-3 multi-sig dispute settlement | **In base** (propose/approve in the agreement; admin is the third signer) |
| Wallet login + email/social via Account Abstraction | **In base via Privy** (frontend task; backend verifies tokens). Fallback: backend faucet drips test ETH |
| AI evaluation of disputes | **In base** as an advisory report attached to the admin's proposal |
| AI oracle auto-resolve (boolean) | **Stretch**: backend oracle key first, Chainlink Functions later (see `prd-phase2-advanced.md`, section G) |
| Settlement timeout (anti-deadlock) | **Stretch** (~0.5h) |
| AI milestone generator | **Stretch** (~1h) |
| ZK identity (zkPass/EAS), SBT, scope-creep tax | **Out of base** (see `prd-phase2-advanced.md`). Show a mocked "Verified" badge in the DB if needed |

## 3. Users and Roles

| Role | Capabilities |
|---|---|
| **Client** | Create project (via factory), fund escrow, approve milestone, raise dispute, propose/approve settlement, reassign freelancer, cancel (rules in 5.1) |
| **Freelancer** | Submit milestone, claim auto-release, raise dispute, propose/approve settlement, resign |
| **Platform admin** | Third signer on disputes: propose/approve settlements using the AI report. Backend holds the admin key |

## 4. System Architecture

```
 Frontend (Next.js + wagmi/viem + Privy)           <- teammate
   |  sends all transactions from the user's wallet
   |  calls backend for auth-gated reads + IPFS pinning
   v
 Backend API (Node + TypeScript + Fastify)         <- you
   |- Auth: verify Privy token         |- IPFS service (Pinata)
   |- Event Indexer (factory + agreements)  |- AI Dispute service (LLM)
   |- Admin signer (viem)              |- Faucet (test ETH + MockUSDC)
   |- DB (SQLite via Prisma)
        |  viem
        v
 FairworkFactory.sol --deploys--> FreelanceAgreement.sol (one per project)  +  MockUSDC.sol
   (Base Sepolia or Polygon Amoy)
        ^
        |  CIDs only
     IPFS (Pinata)
```

**Principle:** the contracts are the source of truth for money and state. The DB is a read-cache plus off-chain metadata (titles, descriptions, user profiles, evidence notes, AI reports). The indexer keeps them in sync. Large data (briefs, specs, deliverables, reports) lives on IPFS; **only CIDs and hashes go on-chain. Chat logs are not stored on-chain or in this build.**

### Recommended stack
- **Contracts:** Solidity 0.8.x, Foundry, OpenZeppelin (optimizer on, custom errors)
- **Backend:** Node 20, TypeScript, Fastify, Prisma + SQLite, viem, zod
- **Wallet/auth:** Privy (supports external wallets and email/social login with embedded or smart wallets in one SDK; confirm current smart wallet and gas sponsorship setup in the Privy docs)
- **Storage:** Pinata (IPFS)
- **AI:** Anthropic or OpenAI API with JSON-schema output
- **Chain:** Base Sepolia (or Polygon Amoy); MockUSDC (6 decimals) with a public `faucet()`

### Who does what (important for integration)
| Action | Transaction sent by | Backend's role |
|---|---|---|
| Create agreement | Frontend (user wallet) -> factory | Pins brief + milestone specs, returns CIDs/hashes first; indexes the result |
| Fund | Frontend: USDC `approve`, then `fundProject()` (can be batched with a smart wallet) | Faucet for demo USDC; indexes |
| Submit milestone | Frontend | Pins the deliverable file, returns the CID first |
| Approve / dispute / resign / reassign / cancel | Frontend | Indexes; AI evaluation starts on `DisputeRaised` |
| Admin proposal/approval | **Backend admin key** | Exposes admin endpoints |
| Reads | Frontend may read the chain directly (wagmi) for the freshest detail view, or use backend index for lists/dashboard | Serves indexed reads |

## 5. Functional Requirements

### 5.1 Smart Contracts

Three contracts: `MockUSDC.sol` (ERC-20 with open `faucet()`), `FairworkFactory.sol`, `FreelanceAgreement.sol`.

#### 5.1.1 `FairworkFactory.sol`
- Constructor: `(address usdc, address platformAdmin, uint64 dayLength)`. `dayLength` is the demo time-compression knob (86400 in production; e.g. 60 for the demo).
- `createAgreement(address freelancer, uint16 bonusBps, string briefCid, MilestoneInput[] milestones) returns (address)`: deploys `new FreelanceAgreement(...)` with `msg.sender` as client, stores it in the registry, emits `AgreementCreated(agreement, client, freelancer, briefCid)`.
- Registry views for the dashboard: `agreementsOf(address user) -> address[]` (client or freelancer), `agreementsCount()`, `agreementAt(i)`.
- Limits: 1-10 milestones; `freelancer != msg.sender`; every `payoutAmount > 0`.
- **Size gotcha:** the factory's bytecode embeds the agreement's creation code, so the agreement must stay small (target under ~18KB with the optimizer on) or the factory exceeds the 24KB limit. If this bites, switch to EIP-1167 clones (OpenZeppelin `Clones`) with an `initialize()` function; the external interface does not change.

#### 5.1.2 `FreelanceAgreement.sol`: state

```solidity
struct MilestoneInput {
  string  description;
  bytes32 requiredDeliverableHash; // keccak256 of the pinned spec JSON bytes
  string  specCid;                 // IPFS CID of milestone spec + acceptance criteria
  uint256 payoutAmount;            // USDC base units
  uint64  deadline;                // unix seconds
  uint64  bonusDeadline;           // 0 = no early bonus for this milestone
}

struct Milestone {
  string  description;
  bytes32 requiredDeliverableHash;
  string  specCid;
  uint256 payoutAmount;
  uint64  deadline;
  uint64  bonusDeadline;
  string  deliveryCid;             // set on submission
  uint64  submittedAt;
  bool    isCompleted;             // freelancer has submitted
  bool    isApproved;              // final payout done (approved, auto-released, or settled)
  bool    isDisputed;
}

struct Proposal {
  uint16  freelancerBps;           // 0-10000: share of this milestone going to the freelancer
  string  reportCid;               // IPFS CID of the AI report (may be empty)
  address proposer;
  uint8   approvalMask;            // bit0 client, bit1 freelancer, bit2 admin
  bool    executed;
}
```

Contract-level variables: `client`, `freelancer`, `platformAdmin`, `token`, `totalProjectValue` (sum of payouts), `bonusBps`, `bonusPool`, `bonusPaid`, `briefCid`, `status` (`Created | Active | Completed | Cancelled`), `freelancerResigned`, `Milestone[] milestones`, `mapping(uint => Proposal[]) proposals`, `reviewWindow = 7 * dayLength`, `gracePeriod = 3 * dayLength`.

**Milestone state is derived from the flags:**

| isCompleted | isApproved | isDisputed | Meaning | Dashboard bucket |
|---|---|---|---|---|
| false | false | false | Not yet submitted | Pending |
| true | false | false | Submitted, awaiting client | In review (Active) |
| true | false | true | Funds locked, arbitration | Disputed |
| true | true | false | Paid via approval or auto-release | Completed |
| true | true | true | Paid via settlement | Completed (resolved) |

Milestones may be submitted in any order; the UI should present them in sequence.

#### 5.1.3 `FreelanceAgreement.sol`: functions

| Function | Caller | Behavior |
|---|---|---|
| `fundProject()` | client | One time. Pulls `totalProjectValue + bonusPool` in USDC (requires prior `approve`). Status -> `Active`. |
| `submitMilestone(uint index, string cid)` | freelancer | Requires `Active` and `!isCompleted`. Stores CID and `block.timestamp`; sets `isCompleted`. |
| `approveMilestone(uint index)` | **client only** | Requires `isCompleted && !isApproved && !isDisputed`. Applies SLA math (5.1.4), pays the freelancer, refunds any penalty to the client, sets `isApproved`. |
| `claimAutoRelease(uint index)` | freelancer | Requires `isCompleted && !isApproved && !isDisputed` and `now >= submittedAt + reviewWindow`. Same payout math as approval. |
| `raiseDispute(uint index)` | client or freelancer | Requires `isCompleted && !isApproved && !isDisputed`. **Locks the milestone's funds** (`isDisputed = true`). The client can only raise it before the review window ends; after that the freelancer may still raise it instead of claiming. Evidence goes off-chain (5.5). |
| `proposeSettlement(uint index, uint16 freelancerBps, string reportCid)` | client, freelancer, or admin | Requires `isDisputed && !isApproved`. Creates a proposal with the proposer's approval already recorded. Max 5 proposals per milestone to prevent spam. |
| `approveSettlement(uint index, uint proposalId)` | client, freelancer, or admin | Records the caller's approval. **When 2 of 3 have approved, the split executes**: freelancer gets `payoutAmount * bps / 10000`, client gets the remainder; sets `isApproved`. |
| `resign()` | freelancer | Sets `freelancerResigned`. Already-paid milestones stay paid. |
| `reassignFreelancer(address newFreelancer)` | client | Requires `Active`, **no milestone currently in review or disputed** (resolve those first), and either `freelancerResigned` or some unsubmitted milestone overdue by more than `gracePeriod`. Replaces the freelancer; funds and completed work are untouched. |
| `cancelProject()` | client | Allowed if `Created` (unfunded), or if `Active` with `freelancerResigned` and no in-flight milestones. Refunds the remaining token balance. |

Views for the frontend and indexer: `summary()` (client, freelancer, token, totalProjectValue, funded, status, paid, milestoneCount), `getMilestones()`, `getMilestone(i)`, `getProposals(i)`.

The platform admin is just an address, so it can later be a Safe multi-sig without contract changes.

**Events:** `Funded, MilestoneSubmitted(index, cid, timestamp), MilestoneApproved(index, paid, penalty, bonus), AutoReleased(index, paid, penalty, bonus), DisputeRaised(index, by), SettlementProposed(index, proposalId, proposer, bps, reportCid), SettlementApproved(index, proposalId, approver), DisputeResolved(index, freelancerAmount, clientAmount), FreelancerResigned, FreelancerReassigned(old, new), ProjectCompleted, ProjectCancelled`.

#### 5.1.4 SLA math
- **Bonus pool:** at funding, `bonusPool = sum(payoutAmount * bonusBps / 10000)` over milestones with `bonusDeadline != 0`.
- **Late penalty:** if `submittedAt > deadline`, `daysLate = ceil((submittedAt - deadline) / dayLength)`, `penaltyBps = min(daysLate * 100, 5000)` (1% per day, capped at 50%). The penalty amount is refunded to the client.
- **Early bonus:** if `bonusDeadline != 0 && submittedAt <= bonusDeadline`, the freelancer also receives `payoutAmount * bonusBps / 10000` from the pool.
- **Disputes:** a settlement split applies to the milestone's `payoutAmount` only; no separate penalty or bonus is applied (the signers account for lateness in the split).
- **Completion:** when every milestone is `isApproved`, status -> `Completed` and any unused bonus (`bonusPool - bonusPaid`) is refunded to the client.
- **Anti-ghosting:** `claimAutoRelease` as specified above.

#### 5.1.5 Contract requirements
- `ReentrancyGuard` on every function that moves funds; `SafeERC20`.
- Strict role and state checks on every function (for example, `approveMilestone` is client only).
- Foundry tests (deploy through the factory in a helper): happy path, funding twice reverts, late penalty at 1 and 60 days, early bonus, auto-release before and after the window, dispute locks approval and auto-release, settlement at 0/50/100% with each pair of signers, a single signer cannot execute, resign then reassign, reassign blocked while a milestone is in review, cancel rules, bonus refund at completion, access control failures.
- **Deadlock risk:** if no proposal reaches 2 approvals, the milestone's funds stay locked. The admin is the tiebreaker by design; the timeout in 5.6 is the safety net.

### 5.2 Auth, Wallets, and Gas (Privy)

- **Login:** the frontend uses Privy, which supports external wallets and email/Google with embedded or smart wallets. This covers "traditional wallet or social login" with a single integration.
- **Backend auth:** the frontend sends the Privy access token as `Authorization: Bearer ...`. The backend verifies it with Privy's server SDK (cache verification results briefly) and upserts a `User` by Privy DID. No custom JWT is issued.
- **Wallet sync:** `POST /me/sync` fetches the user's linked accounts from Privy's server API and stores email, wallet address, and smart-wallet address. The backend never trusts an address sent by the client without checking it against the Privy user record.
- **Admin:** requests to `/admin/*` require the user to be on an `ADMIN_EMAILS` allowlist. The admin on-chain identity is the backend's `ADMIN_PRIVATE_KEY`, which must equal the factory's `platformAdmin`.
- **Gas, option 1 (target):** Privy smart wallets with a paymaster sponsoring gas (dashboard/frontend configuration; confirm the current setup in Privy's docs). The backend is unaffected.
- **Gas, option 2 (fallback, ~15 min of backend work):** `POST /faucet` sends a small amount of test ETH and mints MockUSDC to the user's wallet on first login. External-wallet users also get funded this way on testnet.
- **Freelancer lookup:** `GET /users/lookup?email=` returns the wallet address of a user who has logged in before, so a client can invite by email. Manual address entry is the fallback.

### 5.3 IPFS (Pinata)

Only CIDs and hashes go on-chain.

- `POST /ipfs/project-spec`: body `{ title, description, milestones: [{ title, description, acceptanceCriteria[], ... }] }`. The backend pins one brief JSON and one spec JSON per milestone, caches each JSON in the DB keyed by CID, and returns `{ briefCid, milestones: [{ specCid, requiredDeliverableHash }] }`. `requiredDeliverableHash` is the keccak256 of the exact bytes pinned, so anyone can verify the spec was not swapped.
- `POST /ipfs/deliverable`: multipart file (zip, pdf, image, text; limit 25 MB). Pins and returns `{ cid, gatewayUrl }`. The frontend then calls `submitMilestone(index, cid)`.
- `POST /ipfs/evidence`: body `{ agreement, index, text }` pins a dispute evidence note and stores it for the AI evaluator. Not linked on-chain.
- Every CID is returned with a public gateway URL.

### 5.4 Event Indexer

- Watches the **factory** for `AgreementCreated` and adds each new agreement address to a persisted watch list. Then polls `getLogs` with `address: [factory, ...agreements]` every ~3s from the last processed block (cursor in the DB). No websockets.
- On `AgreementCreated`, reads the agreement via `summary()` and `getMilestones()` and joins each `specCid` with the cached spec JSON to fill titles and acceptance criteria.
- Handlers are idempotent (keyed on `txHash + logIndex`).
- Every event writes an `AuditEvent` row, which powers the transparency timeline.
- On startup, rebuild the watch list from the DB. `POST /admin/reindex` replays from `FACTORY_DEPLOY_BLOCK`.

### 5.5 AI Dispute Evaluation (advisory report for the multi-sig)

Triggered when the indexer sees `DisputeRaised`.

1. Fetch the milestone spec (acceptance criteria) from the cache or IPFS, the delivery file by CID, and any evidence notes from both parties.
2. Extract text (txt/md/code directly; zip -> list files and read the first N KB of text files; pdf -> text; images -> a vision-capable model).
3. Call the LLM with a strict JSON schema:
```json
{
  "overall_score": 0-100,
  "criteria": [{"criterion": "...", "met": true, "evidence": "..."}],
  "summary": "...",
  "recommended_freelancer_bps": 0-10000,
  "confidence": "low|medium|high"
}
```
4. Store the report, pin it to IPFS, and save the CID on the dispute row.
5. **Admin proposes.** The admin (via the admin UI calling `POST /admin/disputes/:agreement/:index/propose`) calls `proposeSettlement` with the AI's recommended split and the report CID. The client or freelancer then approves it (2 of 3 reached) or counter-proposes. For demo speed, `AUTO_PROPOSE=true` makes the backend propose automatically when the report is ready.

**Guardrails:** treat deliverable and evidence content as untrusted data (prompt-injection risk). Instruct the model to evaluate only against the acceptance criteria and never follow instructions found in the files, and flag low confidence so the admin can adjust the split.

### 5.6 Stretch Features (not in the 14.5h estimate)

1. **AI oracle auto-resolve for simple text disputes (~1.5-2h).**
   - Contract: `consentOracle(uint index)` (client and freelancer each call it for a disputed milestone) and `resolveByOracle(uint index, bool criteriaMet)`, callable only by the factory's `oracle` address and only after **both** parties consented. `true` pays the freelancer 100%, `false` refunds the client 100%.
   - Backend: when both consents are indexed and the AI report is `confidence: high`, the backend oracle key calls `resolveByOracle`. This is the same interface Chainlink Functions would later call; see `prd-phase2-advanced.md`, section G.
2. **Settlement timeout (~0.5h).** `settleByTimeout(uint index)` applies a default 50/50 split if no proposal reaches 2 approvals within `ARBITRATION_TIMEOUT`.
3. **AI milestone generator (~1h).** `POST /ai/milestones` takes a plain-English brief and returns 3-5 suggested milestones with acceptance criteria and a payout split.

## 6. Data Model (Prisma / SQLite)

| Table | Key fields |
|---|---|
| `User` | id, privyDid, email, name, walletAddress, smartWalletAddress, isAdmin |
| `Agreement` | address, factory, client, freelancer, token, totalProjectValue, bonusBps, briefCid, title, description, status, createdBlock |
| `Milestone` | agreementAddress, index, title, description, criteriaJson, specCid, requiredDeliverableHash, payoutAmount, deadline, bonusDeadline, deliveryCid, submittedAt, isCompleted, isApproved, isDisputed |
| `Dispute` | agreementAddress, index, raisedBy, status, evidenceJson, aiReportJson, aiReportCid |
| `Proposal` | agreementAddress, index, proposalId, proposer, freelancerBps, reportCid, approvalMask, executed |
| `AuditEvent` | agreementAddress, type, payloadJson, txHash, logIndex, blockNumber, createdAt |
| `SpecCache` | cid, json (pinned JSON by CID) |
| `IndexerState` | lastBlock |

## 7. API Specification

Auth: `Authorization: Bearer <Privy access token>`. Publish `openapi.yaml` in the first ~3 hours so the frontend can start immediately. There are **no project-creation or milestone-action write endpoints**: those are contract calls from the frontend.

| Method | Path | Purpose |
|---|---|---|
| GET | `/config` | Chain id, factory + USDC addresses, ABIs, gateway URL, `dayLength` |
| POST | `/me/sync` | Verify Privy token, sync email + wallet addresses; returns profile |
| GET | `/me` | Profile, wallet address, USDC and ETH balance |
| POST | `/faucet` | Drip test ETH + mint demo USDC to the current user's wallet |
| GET | `/users/lookup?email=` | Find a freelancer's wallet address |
| POST | `/ipfs/project-spec` | Pin brief + milestone specs, return CIDs and hashes |
| POST | `/ipfs/deliverable` | Pin a submission file, return CID |
| POST | `/ipfs/evidence` | Pin and store a dispute evidence note |
| GET | `/agreements?role=&status=` | List my agreements (indexed) |
| GET | `/agreements/:address` | Agreement + milestones + proposals + live status |
| GET | `/agreements/:address/timeline` | Audit events with tx hashes and CIDs |
| GET | `/agreements/:address/payments` | Locked / released / refunded / disputed totals |
| GET | `/dashboard` | My milestones grouped into pending, in review, disputed, completed, plus totals |
| GET | `/disputes/:agreement/:index` | Dispute status, evidence, AI report, proposals |
| POST | `/admin/disputes/:agreement/:index/propose` | Admin signs `proposeSettlement` (default: AI split + report CID) |
| POST | `/admin/disputes/:agreement/:index/proposals/:pid/approve` | Admin signs `approveSettlement` |
| POST | `/admin/reindex` | Replay events from the factory deploy block |
| POST | `/ai/milestones` | (Stretch) brief -> milestone suggestions |

**Error convention:** `{ error: { code, message } }` with stable codes (`UNAUTHENTICATED`, `NOT_ALLOWED`, `NOT_FOUND`, `WRONG_STATE`, `INVALID_INPUT`, `IPFS_FAILED`).

## 8. End-to-End Flows (the integration contract with the frontend)

**Create and fund a project**
1. `GET /config` for addresses and ABIs.
2. `POST /ipfs/project-spec` -> `briefCid`, per-milestone `specCid` + `requiredDeliverableHash`.
3. Wallet: `factory.createAgreement(freelancer, bonusBps, briefCid, milestones[])`; read the agreement address from the `AgreementCreated` event in the receipt.
4. Wallet: `usdc.approve(agreement, total + bonus)`, then `agreement.fundProject()` (batch both if using a smart wallet).
5. The indexer picks it up; `GET /agreements/:address` shows it shortly after.

**Submit work:** `POST /ipfs/deliverable` -> `cid`; wallet: `agreement.submitMilestone(index, cid)`.

**Approve:** wallet: `agreement.approveMilestone(index)`. **Ghosted:** after the review window, freelancer wallet: `claimAutoRelease(index)`.

**Dispute:** a party optionally calls `POST /ipfs/evidence`; wallet: `raiseDispute(index)`; the backend generates and pins the AI report; admin proposes (or auto-proposes); client or freelancer calls `approveSettlement(index, proposalId)` (or `proposeSettlement` with a counter); on the second approval the contract executes the split.

**Dropout:** freelancer `resign()` (or the milestone goes overdue past the grace period); client `reassignFreelancer(newAddr)`; the new freelancer continues from the next unsubmitted milestone without re-funding.

## 9. Mapping to the Original Problem Statement

| Key feature | Where it is satisfied |
|---|---|
| Milestone-based agreements | `MilestoneInput` / `Milestone` structs, factory `createAgreement` |
| Conditional payments | `approveMilestone`, `claimAutoRelease`, 2-of-3 settlement |
| Delivery verification | IPFS CID + timestamp on-chain (5.3), `requiredDeliverableHash` |
| Dispute resolution | `raiseDispute` + AI report + 2-of-3 multi-sig |
| Agreement transparency | Indexer audit trail, `/timeline` |
| Participant protection | Late penalty, anti-ghosting, reassignment, funds locked on dispute |
| Payment tracking | `/payments` and `/dashboard` (pending, released, disputed) |

## 10. Work Plan (14.5h target, ~9.5h buffer in the 24h window)

| # | Task | Est. | Output |
|---|---|---|---|
| 1 | Repo, env, Foundry + Fastify scaffold; Pinata, RPC, and Privy app set up; funded admin key | 1.0h | Running skeleton |
| 2 | Contracts: **write `IFreelanceAgreement` + `IFairworkFactory` interfaces first and share the ABI**; then MockUSDC, agreement (escrow, SLA math, submit/approve/auto-release), 2-of-3 dispute, resign/reassign/cancel, factory, Foundry tests, testnet deploy | 5.5h | Deployed addresses + ABI |
| 3 | Privy token verification, `/me/sync`, `/faucet`, `/config`, `openapi.yaml` + mock server | 1.5h | Login works; spec shared with UI teammate |
| 4 | IPFS endpoints (project-spec, deliverable, evidence) | 1.0h | CIDs and hashes flowing |
| 5 | Indexer with dynamic agreement list, handlers, audit events; read endpoints (`/agreements`, `/dashboard`, `/timeline`, `/payments`) | 2.5h | DB in sync with chain |
| 6 | AI dispute service, admin propose/approve endpoints, `AUTO_PROPOSE` | 1.5h | Report pinned; admin can propose |
| 7 | Seed script, E2E run, README, demo script | 1.5h | Demo-ready |
| | **Total** | **14.5h** | |

**Sync points with the UI teammate:**
- **Hour ~2.5:** interfaces/ABI and `openapi.yaml` + mock server (the frontend can wire wagmi hooks before the logic is done).
- **Hour ~7:** contracts deployed, `/config`, auth, and IPFS endpoints live.
- **Hour ~11:** indexer, dashboard, and dispute endpoints live.
- **Hour ~13:** full end-to-end run together using section 11.

**Cut order if behind schedule:** AI milestone generator -> oracle auto-resolve -> early bonus -> reassignment polish -> `/payments` summary (the dashboard totals cover it). Never cut: factory + escrow, submit with CID, approve, auto-release, dispute with 2-of-3 settlement, AI report.

## 11. Acceptance Criteria (demo checklist)
- [ ] A new user logs in with email/Google (or an external wallet) and has a funded wallet with no manual gas handling.
- [ ] Client creates a 3-milestone project through the factory, funds it, and sees funds locked; the agreement has its own address.
- [ ] Freelancer submits a file; the CID opens in an IPFS gateway; the timeline shows the tx hash.
- [ ] Only the client can approve; the payout reaches the freelancer; a late submission produces a visibly reduced payout and a client refund.
- [ ] Waiting out the (shortened) review window enables `claimAutoRelease`.
- [ ] Raising a dispute locks that milestone; an AI report appears within ~30s; the admin proposes; one party approves; the 70/30 split executes. A single signer alone cannot execute.
- [ ] Freelancer resigns; client reassigns; the new freelancer continues without re-funding.
- [ ] The dashboard shows pending, in-review, disputed, and completed milestones correctly, and the timeline and payments views match the chain.

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Factory exceeds the 24KB contract size limit | Optimizer on, custom errors, keep the agreement lean; fall back to EIP-1167 clones with `initialize()` |
| Funds deadlocked in a dispute | Admin acts as tiebreaker; settlement timeout (5.6) as safety net |
| Privy smart wallet or paymaster setup takes longer than expected | Start it early (frontend teammate); fall back to the backend faucet dripping test ETH |
| Indexer misses agreements or lags | Persisted watch list rebuilt on startup; `/admin/reindex`; the frontend can read the chain directly for the freshest detail view |
| Testnet RPC flakiness | Retry wrapper; paid-tier free RPC (Alchemy/Infura); local Anvil as a demo-recording fallback |
| Frontend and backend drift | Interfaces/ABI by hour ~2.5; `openapi.yaml` generated client; sync points in section 10 |
| AI report quality or prompt injection | Strict JSON schema, criteria-only prompt, advisory only: two humans/parties must still approve |
| Admin key compromise (testnet only) | Dedicated testnet key; note in the pitch that production uses a Safe |
| Scope creep | Decision log (section 2) is final; extra ideas go on a roadmap slide |

## 13. Environment Variables
```
CHAIN_ID=
RPC_URL=
FACTORY_ADDRESS=
FACTORY_DEPLOY_BLOCK=
USDC_ADDRESS=
ADMIN_PRIVATE_KEY=       # equals platformAdmin; also funds the faucet (testnet)
ADMIN_EMAILS=
PRIVY_APP_ID=
PRIVY_APP_SECRET=
PINATA_JWT=
PINATA_GATEWAY=
LLM_API_KEY=
AUTO_PROPOSE=false
DAY_SECONDS=60           # demo time compression, passed to the factory at deploy
ORACLE_PRIVATE_KEY=      # stretch
ARBITRATION_TIMEOUT_SECONDS=   # stretch
```
