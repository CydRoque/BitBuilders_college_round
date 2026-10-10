# Fairwork: Get Paid for What You Deliver

> **Decentralized Milestone-Based Agreement & Verifiable Delivery Platform**

Fairwork connects companies with qualified freelancers using smart contract escrows, cryptographic milestone verification, an Amazon-style deliverable pipeline tracker, dynamic late penalty buffer calculations, and automated task relinquishment for complete fairness.

---

## 🌟 Key Features

1. **PostgreSQL Database Storage Layer**
   - Connected directly to local PostgreSQL on port `5432` (`fairwork_db`).
   - Tables created and persisted long-term:
     * `blockchain_blocks`: Immutable SHA-256 blocks, Merkle roots, nonces, timestamps.
     * `blockchain_transactions`: On-chain escrow locks, milestone payouts, late penalty refunds, task relinquishments.
     * `wallets`: Protocol treasury, company wallets, and freelancer token balances.
     * `contracts`: Project scopes, budgets, escrow balances, and Amazon tracker states.
     * `chat_messages`: WhatsApp-style real-time chats, timestamps, and image attachments.
   - Built-in automatic fallback to local SQLite (`sqlite:///fairwork.db`) if deployed to an environment without PostgreSQL.

2. **Flask Sessions & Multi-Device Isolation**
   - **Isolated Sessions**: Each browser window, incognito tab, or remote device receives its own cryptographically signed Flask session cookie (`fairwork_session`).
   - Multiple users from different devices can log in simultaneously (e.g., Company on one device, Freelancers on another) and interact side-by-side in real time!
   - Dedicated access-controlled routes:
     * `/company`: Accessible strictly to logged-in Companies.
     * `/freelancer`: Accessible strictly to logged-in Freelancers.
     * `/login`: Monochrome portal with 1-click demo profiles or new registration.

2. **Minimalist Black & White (Monochrome) UI**
   - High-contrast aesthetic with deep obsidian blacks (`#000000`, `#09090b`), pure whites (`#ffffff`), and subtle zinc accents.
   - Clean monochrome typography, borders, and progress indicators.

3. **Dual Marketplace for Companies & Freelancers**
   - Companies can post milestone-based job agreements with escrow deposits and view qualified talent.
   - Freelancers can browse open jobs, check required skills, and apply with verifiable credentials.

2. **Multi-Factor Qualification Matching Engine**
   - Algorithmic matching based on:
     - Verified technical skills (50% weight)
     - Client rating & review history (25% weight)
     - Dispute-free reputation score (25% weight)

3. **Amazon-Style Product Delivery Tracker**
   - Visual 6-stage delivery pipeline:
     1. **Escrow Locked** (Smart Contract vault initialized on-chain)
     2. **Freelancer Allotted** (Profile verified & contract signed)
     3. **Milestone In Execution** (Work in progress with active timer)
     4. **Deliverable Submitted** (Cryptographic SHA-256 deliverable proof generated)
     5. **Milestone Funds Released** (Smart contract conditional payout)
     6. **Contract Completed** (Reputation rewarded and badges updated)

4. **Deadline Buffer & Late Penalty Engine**
   - Strict deadline tracking with configurable grace buffer periods.
   - On-time delivery guarantees 100% payout from escrow.
   - Delayed submissions within the buffer incur a transparent hourly penalty deduction refunded back to the company.

5. **Fair Relinquishment & Reassignment Protocol**
   - If a freelancer exceeds the deadline buffer or cannot complete the task:
     - **Past Completed Work Protection**: All previously approved milestones remain **100% paid** to the original freelancer.
     - **Seamless Handoff**: The incomplete milestone and remaining project budget are securely transferred to a backup qualified freelancer (e.g. Priya Sharma).
     - **Immutable On-Chain Record**: State transition and remaining payout allotments are verified on the blockchain.

6. **Full-Featured Python Blockchain Engine**
   - **SHA-256 Hashing**: Block hashing, transaction hashing, and deliverable content proofs.
   - **Merkle Tree Roots**: Cryptographic tree hashing of all transactions in every block.
   - **Proof-of-Work (PoW)**: Consensus engine with configurable difficulty and mining rewards.
   - **Live Blockchain Explorer**: Inspect mined blocks, hashes, nonces, and the mempool.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.9+
- Flask (`pip install flask`)

### 2. Launch the Application
Simply run:
```bash
python run_app.py
```
This automatically starts the server and opens the interactive dashboard at:
[http://127.0.0.1:5000](http://127.0.0.1:5000)

### 3. Running Unit & Integration Tests
```bash
python -m unittest tests/test_fairwork.py
```

---

## 🎮 How to Demo & Test in the Web UI

1. **Switch Personas in the Top Bar**:
   - **🏢 NovaTech (Company)**: Review submissions, approve milestones, or trigger reassignments.
   - **👨‍💻 Alex Rivera (Freelancer 1)**: Submit deliverables for active milestones.
   - **👩‍💻 Priya Sharma (Freelancer 2 - Backup)**: Receive relinquished tasks and complete remaining work.

2. **Use the Virtual Simulation Clock**:
   - Click `+6h` or `+12h` to advance time smoothly.
   - Click `+24h (Pass Deadline)` to observe the **late penalty deduction** in action.
   - Click `+48h (Exceed Buffer)` to test the **automated relinquishment failover** to Freelancer 2!

3. **Check the Live Blockchain Explorer**:
   - Click the **Blockchain Explorer** tab to see SHA-256 block hashes, Merkle roots, and transaction signatures recorded for every action!
