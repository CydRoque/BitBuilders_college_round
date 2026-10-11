# Fairwork: System Design Document

## 1. System Overview
Fairwork is a decentralized freelance marketplace and milestone-based agreement platform. It utilizes blockchain technology to manage job postings, track delivery progress, and execute trustless, automated payments via smart contracts based on predefined project milestones and deadlines.

## 2. System Architecture
* **Frontend UI:** (e.g., React.js, Next.js) for the marketplace interface and Amazon-style delivery tracker.
* **Smart Contracts:** (e.g., Solidity / Ethereum) to handle escrow, milestone logic, penalty deductions, and job reassignment.
* **Off-Chain Storage:** (e.g., IPFS) for storing large deliverables, portfolio items, and encrypted chat logs to keep gas costs low.

## 3. User Roles
* **Clients:** Entities who post jobs, define milestones, deposit funds into escrow, and approve deliverables.
* **Freelancers:** Users who apply for jobs, submit work against milestones, and receive automated payouts.
* **Arbitrators (Optional):** A decentralized jury or specified third party invoked only when a dispute over work quality arises.

## 4. Core Mechanisms
### Milestone Escrow
When a client selects a freelancer, the total project funds (or the first milestone phase) are locked in a smart contract. Funds are automatically released to the freelancer's wallet upon the client's cryptographic approval of the submitted milestone.

### Delivery & Progress Tracking
The frontend will read state changes from the smart contract (e.g., `JobAccepted`, `MilestoneSubmitted`, `PaymentReleased`) to populate a real-time progress tracker. 

### Deadline Penalties & Reassignment
* **Time-Locks:** Smart contracts will track the `deadline_timestamp`.
* **Penalty Logic:** If a submission occurs past the deadline and buffer period, a predefined percentage is deducted from the payout and refunded to the client.
* **Task Relinquishment:** If a freelancer abandons the job or fails completely, the contract allows the client to terminate the agreement. The contract pays the original freelancer only for completed milestones, unlocks the remaining funds, and allows the client to reassign the exact remaining scope to a new freelancer.

## 5. Job Lifecycle Flow
1. **Posting:** Client creates a job with milestones, deadlines, and deposits the crypto payout.
2. **Matching:** Freelancers bid/apply; Client selects a candidate.
3. **Execution:** Freelancer begins work. The tracker status updates to *In Progress*.
4. **Submission:** Freelancer submits deliverables via IPFS link. Status updates to *Awaiting Review*.
5. **Resolution:** 
    * *Path A (Success):* Client approves; smart contract releases funds.
    * *Path B (Delay):* Client approves late work; contract executes partial payment and partial refund based on penalty logic.
    * *Path C (Dispute):* Client rejects work; contract locks funds and initiates the dispute resolution phase.
