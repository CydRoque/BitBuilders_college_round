"""
Fairwork Engine:
Smart Contract Orchestrator for Milestone Escrows,
Amazon-style Deliverable Tracking, Deadline Buffers & Penalty Engine,
Relinquishment & Work Allotment Logic, and Profile Matching.
"""

import time
import hashlib
from typing import Dict, List, Any, Optional
from backend.blockchain import Blockchain, Transaction, sha256_hash
from backend.models import FreelancerProfile, CompanyProfile, JobContract, Milestone

class FairworkEngine:
    def __init__(self):
        self.blockchain = Blockchain(difficulty=2)
        # Virtual simulation time (starts at real time or designated baseline)
        self.virtual_time = time.time()
        
        self.freelancers: Dict[str, FreelancerProfile] = {}
        self.companies: Dict[str, CompanyProfile] = {}
        self.contracts: Dict[str, JobContract] = {}
        
        self._init_seed_data()

    def get_virtual_time(self) -> float:
        return self.virtual_time

    def advance_virtual_time(self, hours: float) -> float:
        self.virtual_time += (hours * 3600.0)
        return self.virtual_time

    def reset_virtual_time(self):
        self.virtual_time = time.time()

    def _init_seed_data(self):
        # 1. Seed Companies
        c1 = CompanyProfile(
            id="company_novatech",
            name="NovaTech Decentralized Systems",
            industry="Fintech & Web3 Infrastructure",
            wallet_address="0xNOVATECH_CORP_019A8B",
            rating=4.95,
            jobs_posted=18,
            total_spent=145000.0,
            avatar="https://images.unsplash.com/photo-1549923746-c502d488b3ea?w=150&auto=format&fit=crop&q=80"
        )
        c2 = CompanyProfile(
            id="company_aurora",
            name="Aurora AI & Robotics",
            industry="Machine Learning & Edge IoT",
            wallet_address="0xAURORA_LABS_77C1D2",
            rating=4.82,
            jobs_posted=9,
            total_spent=68000.0,
            avatar="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=150&auto=format&fit=crop&q=80"
        )
        self.companies[c1.id] = c1
        self.companies[c2.id] = c2

        # 2. Seed Freelancers
        f1 = FreelancerProfile(
            id="freelancer_alex",
            name="Alex Rivera",
            title="Senior Smart Contract & Rust Engineer",
            wallet_address="0xALEX_RIVERA_ETH_WALLET_88A1",
            skills=["Solidity", "Rust", "Smart Contracts", "Cryptography", "DeFi Architecture"],
            hourly_rate=95.0,
            rating=4.98,
            completed_jobs=34,
            reputation_score=960,
            bio="Blockchain architect with 7+ years developing audited EVM smart contracts, zero-knowledge proofs, and escrow protocols.",
            avatar="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
            badges=["Auditor Certified", "Top 1% Solidity", "Zero Disputes"]
        )
        f2 = FreelancerProfile(
            id="freelancer_priya",
            name="Priya Sharma",
            title="Full-Stack Web3 & Security Specialist",
            wallet_address="0xPRIYA_SHARMA_DEV_WALLET_33C4",
            skills=["Solidity", "Python", "React", "Smart Contracts", "REST APIs", "TypeScript"],
            hourly_rate=80.0,
            rating=4.92,
            completed_jobs=27,
            reputation_score=925,
            bio="Versatile blockchain and backend engineer known for rapid turnaround, rock-solid security, and rescue/reassignment task delivery.",
            avatar="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&auto=format&fit=crop&q=80",
            badges=["Rapid Delivery Champion", "Full-Stack Verified", "Rescue Specialist"]
        )
        f3 = FreelancerProfile(
            id="freelancer_marcus",
            name="Marcus Vance",
            title="DeFi Protocol & Tokenomics Engineer",
            wallet_address="0xMARCUS_VANCE_DEV_WALLET_55E9",
            skills=["Python", "Solidity", "Financial Modeling", "Data Analysis", "Security Auditing"],
            hourly_rate=85.0,
            rating=4.85,
            completed_jobs=19,
            reputation_score=890,
            bio="Ex-Quant dev focused on algorithmic liquidity protocols, verifiable milestone contracts, and dynamic fee settlement.",
            avatar="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80",
            badges=["DeFi Master", "Code Quality Gold"]
        )
        self.freelancers[f1.id] = f1
        self.freelancers[f2.id] = f2
        self.freelancers[f3.id] = f3

        # 3. Fund Wallets with FWK tokens on blockchain
        self.blockchain.set_wallet_balance(c1.wallet_address, 25000.0)
        self.blockchain.set_wallet_balance(c2.wallet_address, 15000.0)
        self.blockchain.set_wallet_balance(f1.wallet_address, 1200.0)
        self.blockchain.set_wallet_balance(f2.wallet_address, 850.0)
        self.blockchain.set_wallet_balance(f3.wallet_address, 600.0)

        # 4. Seed a Realistic Interactive Job Contract
        m1 = Milestone(
            index=0,
            title="Milestone 1: Smart Contract Architecture & Escrow Logic",
            description="Design and test the immutable smart contract escrow vault with multi-sig authorization and event hooks.",
            amount=2000.0,
            deadline_hours=24.0,       # 24 hours deadline
            buffer_hours=12.0,         # 12 hours grace buffer
            penalty_rate_per_hour=4.0, # 4% penalty per late hour
            max_penalty_percent=30.0   # Max 30% deduction
        )
        m2 = Milestone(
            index=1,
            title="Milestone 2: Amazon-Style Real-time Tracking & Subgraph Integration",
            description="Implement verifiable deliverable submission endpoints and Amazon-style delivery progress tracker pipeline.",
            amount=2500.0,
            deadline_hours=36.0,
            buffer_hours=18.0,
            penalty_rate_per_hour=3.5,
            max_penalty_percent=35.0
        )
        m3 = Milestone(
            index=2,
            title="Milestone 3: Security Audit, Relinquishment Engine & Final Deployment",
            description="Run static analyzers, test automated relinquishment failover mechanism, and deploy to live subnet.",
            amount=1500.0,
            deadline_hours=20.0,
            buffer_hours=10.0,
            penalty_rate_per_hour=5.0,
            max_penalty_percent=30.0
        )

        job1 = JobContract(
            id="FWK-CONTRACT-101",
            company_id=c1.id,
            title="Decentralized Milestone Escrow & Verifiable Delivery Tracker",
            category="Blockchain Architecture",
            description="Build an automated milestone-based agreement platform that locks company funds in smart contract escrow, tracks deliverables visually like Amazon's package tracker, and executes penalty deductions or relinquishment upon delayed deadlines.",
            required_skills=["Solidity", "Smart Contracts", "Cryptography", "Python"],
            total_budget=6000.0,
            milestones=[m1, m2, m3],
            created_at=self.virtual_time - 7200 # created 2 hours ago
        )

        # Lock company funds into smart contract escrow on-chain
        lock_tx = Transaction(
            sender=c1.wallet_address,
            recipient=job1.smart_contract_address,
            amount=6000.0,
            tx_type="ESCROW_LOCK",
            contract_id=job1.id,
            metadata={"job_title": job1.title, "milestones_count": 3}
        )
        self.blockchain.add_transaction(lock_tx)
        job1.escrow_locked = 6000.0

        # Simulate Freelancer Application with match calculation
        qual1 = f1.calculate_qualification_score(job1.required_skills)
        job1.applications.append({
            "freelancer_id": f1.id,
            "freelancer_name": f1.name,
            "proposal_text": "I have deployed over 30 EVM contracts with milestone escrow security. Ready to start immediately.",
            "qualification_score": qual1,
            "applied_at": self.virtual_time - 3600
        })

        qual2 = f2.calculate_qualification_score(job1.required_skills)
        job1.applications.append({
            "freelancer_id": f2.id,
            "freelancer_name": f2.name,
            "proposal_text": "Extensive experience in smart contracts, full-stack tracking UI, and emergency reassignment contracts.",
            "qualification_score": qual2,
            "applied_at": self.virtual_time - 2400
        })

        # Allot to Alex initially
        job1.status = "ALLOTTED"
        job1.current_freelancer_id = f1.id
        job1.tracker_stage = 3
        job1.tracker_stage_label = "Milestone Execution in Progress"
        job1.milestones[0].start_milestone(f1.id, self.virtual_time - 1800)
        
        job1.log_audit("JOB_ALLOTTED", c1.id, {
            "allotted_to": f1.id,
            "match_pct": qual1["match_percentage"],
            "escrow_locked": 6000.0
        }, self.virtual_time - 1800)

        # Mine genesis & setup blocks
        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")
        self.contracts[job1.id] = job1

    # --- Platform Operations ---

    def post_job(self, company_id: str, title: str, category: str, description: str,
                 required_skills: List[str], milestones_data: List[Dict[str, Any]]) -> JobContract:
        company = self.companies.get(company_id)
        if not company:
            raise ValueError(f"Company '{company_id}' not found.")

        total_budget = sum(float(m["amount"]) for m in milestones_data)
        company_balance = self.blockchain.get_wallet_balance(company.wallet_address)
        if company_balance < total_budget:
            raise ValueError(f"Insufficient funds: Company wallet balance is {company_balance} FWK, requires {total_budget} FWK.")

        milestones: List[Milestone] = []
        for idx, m_dict in enumerate(milestones_data):
            milestone = Milestone(
                index=idx,
                title=m_dict.get("title", f"Milestone #{idx + 1}"),
                description=m_dict.get("description", ""),
                amount=float(m_dict["amount"]),
                deadline_hours=float(m_dict.get("deadline_hours", 24.0)),
                buffer_hours=float(m_dict.get("buffer_hours", 12.0)),
                penalty_rate_per_hour=float(m_dict.get("penalty_rate_per_hour", 3.0)),
                max_penalty_percent=float(m_dict.get("max_penalty_percent", 30.0))
            )
            milestones.append(milestone)

        job_id = f"FWK-CONTRACT-{100 + len(self.contracts) + 1}"
        contract = JobContract(
            id=job_id,
            company_id=company.id,
            title=title,
            category=category,
            description=description,
            required_skills=required_skills,
            total_budget=total_budget,
            milestones=milestones,
            created_at=self.virtual_time
        )

        # Lock escrow transaction
        escrow_tx = Transaction(
            sender=company.wallet_address,
            recipient=contract.smart_contract_address,
            amount=total_budget,
            tx_type="ESCROW_LOCK",
            contract_id=contract.id,
            metadata={"title": title, "milestones_count": len(milestones)}
        )
        self.blockchain.add_transaction(escrow_tx)
        contract.escrow_locked = total_budget
        
        contract.log_audit("CONTRACT_CREATED", company.id, {
            "total_budget": total_budget,
            "smart_contract": contract.smart_contract_address
        }, self.virtual_time)

        # Mine block
        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")
        self.contracts[contract.id] = contract
        try:
            from backend.db import DatabaseService
            DatabaseService.save_contract(contract.to_dict())
        except Exception as e:
            print(f"[Warning] Failed to save contract to PostgreSQL: {e}")
        return contract

    def apply_for_job(self, job_id: str, freelancer_id: str, proposal_text: str) -> Dict[str, Any]:
        contract = self.contracts.get(job_id)
        if not contract:
            raise ValueError(f"Contract {job_id} not found")
        freelancer = self.freelancers.get(freelancer_id)
        if not freelancer:
            raise ValueError(f"Freelancer {freelancer_id} not found")

        # Check if already applied
        for app in contract.applications:
            if app["freelancer_id"] == freelancer_id:
                raise ValueError("Freelancer has already applied to this contract.")

        qual_score = freelancer.calculate_qualification_score(contract.required_skills)
        application = {
            "freelancer_id": freelancer.id,
            "freelancer_name": freelancer.name,
            "proposal_text": proposal_text,
            "qualification_score": qual_score,
            "applied_at": self.virtual_time
        }
        contract.applications.append(application)
        contract.log_audit("APPLICATION_SUBMITTED", freelancer.id, {
            "match_percentage": qual_score["match_percentage"]
        }, self.virtual_time)
        return application

    def allot_job(self, job_id: str, freelancer_id: str) -> JobContract:
        contract = self.contracts.get(job_id)
        if not contract:
            raise ValueError(f"Contract {job_id} not found")
        freelancer = self.freelancers.get(freelancer_id)
        if not freelancer:
            raise ValueError(f"Freelancer {freelancer_id} not found")

        qual = freelancer.calculate_qualification_score(contract.required_skills)
        contract.status = "ALLOTTED"
        contract.current_freelancer_id = freelancer.id
        contract.tracker_stage = 3
        contract.tracker_stage_label = "Milestone Execution in Progress"
        
        # Start Milestone 0
        current_m = contract.milestones[0]
        current_m.start_milestone(freelancer.id, self.virtual_time)
        contract.current_milestone_index = 0

        # On-chain allotment record
        allot_tx = Transaction(
            sender=contract.smart_contract_address,
            recipient=freelancer.wallet_address,
            amount=0.0,
            tx_type="FREELANCER_JOB_ALLOTTED",
            contract_id=contract.id,
            metadata={
                "freelancer_id": freelancer.id,
                "qualification_match": qual["match_percentage"],
                "active_milestone": current_m.title
            }
        )
        self.blockchain.add_transaction(allot_tx)
        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")

        contract.log_audit("JOB_ALLOTTED", contract.company_id, {
            "freelancer_id": freelancer.id,
            "milestone_index": 0,
            "match_pct": qual["match_percentage"]
        }, self.virtual_time)
        return contract

    def submit_deliverable(self, job_id: str, milestone_index: int, freelancer_id: str,
                           deliverable_text: str, deliverable_link: Optional[str] = None) -> Dict[str, Any]:
        contract = self.contracts.get(job_id)
        if not contract:
            raise ValueError(f"Contract {job_id} not found")
        if contract.current_freelancer_id != freelancer_id:
            raise ValueError("Only the currently allotted freelancer can submit this deliverable.")
        if milestone_index < 0 or milestone_index >= len(contract.milestones):
            raise ValueError("Invalid milestone index.")

        milestone = contract.milestones[milestone_index]
        if milestone.status not in ["IN_PROGRESS", "SUBMITTED"]:
            raise ValueError(f"Milestone cannot be submitted in state '{milestone.status}'.")

        # Cryptographic deliverable proof (SHA-256)
        content_for_hash = f"{job_id}:{milestone_index}:{deliverable_text}:{deliverable_link or ''}:{self.virtual_time}"
        d_hash = sha256_hash(content_for_hash)

        # Evaluate timing & deadline breach
        time_result = milestone.submit_deliverable(deliverable_text, d_hash, freelancer_id, self.virtual_time)

        # Update Amazon-style tracking stage to Stage 4 (Deliverable Submitted & Verification)
        contract.tracker_stage = 4
        contract.tracker_stage_label = "Deliverable Submitted & Under Verification"

        # Record verifiable submission on blockchain
        submit_tx = Transaction(
            sender=freelancer.wallet_address if (freelancer := self.freelancers.get(freelancer_id)) else "0xFREELANCER",
            recipient=contract.smart_contract_address,
            amount=0.0,
            tx_type="DELIVERABLE_PROOF_SUBMITTED",
            contract_id=contract.id,
            milestone_index=milestone_index,
            metadata={
                "deliverable_hash": d_hash,
                "delay_hours": time_result["delay_hours"],
                "is_late": time_result["is_late"],
                "is_beyond_buffer": time_result["is_beyond_buffer"],
                "virtual_time": self.virtual_time
            }
        )
        self.blockchain.add_transaction(submit_tx)
        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")

        contract.log_audit("DELIVERABLE_SUBMITTED", freelancer_id, {
            "milestone_index": milestone_index,
            "deliverable_hash": d_hash,
            "delay_hours": time_result["delay_hours"],
            "is_late": time_result["is_late"]
        }, self.virtual_time)

        return {
            "deliverable_hash": d_hash,
            "delay_hours": time_result["delay_hours"],
            "is_late": time_result["is_late"],
            "is_beyond_buffer": time_result["is_beyond_buffer"],
            "milestone": milestone.to_dict(),
            "tracker_stage": contract.tracker_stage
        }

    def approve_milestone(self, job_id: str, milestone_index: int, company_id: str) -> Dict[str, Any]:
        contract = self.contracts.get(job_id)
        if not contract:
            raise ValueError(f"Contract {job_id} not found")
        if contract.company_id != company_id:
            raise ValueError("Only the contract owner company can approve milestones.")
        if milestone_index < 0 or milestone_index >= len(contract.milestones):
            raise ValueError("Invalid milestone index.")

        milestone = contract.milestones[milestone_index]
        if milestone.status != "SUBMITTED":
            raise ValueError(f"Cannot approve milestone in '{milestone.status}' state. It must be SUBMITTED first.")

        company = self.companies[contract.company_id]
        freelancer = self.freelancers[contract.current_freelancer_id]

        # Calculate fair settlement with penalties if late
        settlement = milestone.compute_settlement()
        payout = settlement["payout_to_freelancer"]
        refund = settlement["refund_to_company"]
        penalty = settlement["penalty_amount"]

        # Smart Contract payout transaction to Freelancer
        payout_tx = Transaction(
            sender=contract.smart_contract_address,
            recipient=freelancer.wallet_address,
            amount=payout,
            tx_type="MILESTONE_PAYOUT",
            contract_id=contract.id,
            milestone_index=milestone_index,
            metadata={
                "milestone_title": milestone.title,
                "delay_hours": milestone.delay_hours,
                "penalty_deducted": penalty
            }
        )
        self.blockchain.add_transaction(payout_tx)

        # If penalty occurred, refund penalty portion back to company
        if refund > 0:
            refund_tx = Transaction(
                sender=contract.smart_contract_address,
                recipient=company.wallet_address,
                amount=refund,
                tx_type="PENALTY_REFUND",
                contract_id=contract.id,
                milestone_index=milestone_index,
                metadata={
                    "reason": f"Deadline delayed by {milestone.delay_hours} hrs beyond scheduled time",
                    "penalty_rate": f"{milestone.penalty_rate_per_hour}%/hr"
                }
            )
            self.blockchain.add_transaction(refund_tx)

        milestone.status = "APPROVED"
        milestone.settled_at = self.virtual_time
        milestone.tx_id = payout_tx.tx_id
        contract.escrow_released += milestone.amount

        # Check if next milestone exists
        next_idx = milestone_index + 1
        if next_idx < len(contract.milestones):
            contract.current_milestone_index = next_idx
            contract.milestones[next_idx].start_milestone(freelancer.id, self.virtual_time)
            contract.tracker_stage = 5  # Milestone released
            contract.tracker_stage_label = f"Milestone #{milestone_index + 1} Released • Milestone #{next_idx + 1} In Progress"
        else:
            # All milestones finished!
            contract.status = "COMPLETED"
            contract.tracker_stage = 6  # Final delivery complete
            contract.tracker_stage_label = "Contract Completed & Final Payout Finalized"
            freelancer.completed_jobs += 1
            freelancer.reputation_score = min(1000, freelancer.reputation_score + 15)

        # Mine block
        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")

        contract.log_audit("MILESTONE_APPROVED", company_id, {
            "milestone_index": milestone_index,
            "payout": payout,
            "penalty": penalty,
            "refund": refund,
            "next_stage": contract.tracker_stage
        }, self.virtual_time)

        return {
            "payout": payout,
            "penalty": penalty,
            "refund": refund,
            "tracker_stage": contract.tracker_stage,
            "contract_status": contract.status
        }

    def relinquish_and_reassign(self, job_id: str, milestone_index: int, reason: str,
                                new_freelancer_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fairwork Relinquish Engine:
        When a freelancer passes the deadline buffer or cannot complete the task:
        1. Keeps previously approved milestones locked and fully paid to original freelancer (fairness).
        2. Relinquishes incomplete milestone from previous freelancer.
        3. Automatically selects or assigns the replacement qualified freelancer.
        4. Calculates remaining fair payment allocation.
        5. Smart contract records state transition and handoff on-chain.
        """
        contract = self.contracts.get(job_id)
        if not contract:
            raise ValueError(f"Contract {job_id} not found")
        if milestone_index < 0 or milestone_index >= len(contract.milestones):
            raise ValueError("Invalid milestone index.")

        milestone = contract.milestones[milestone_index]
        if milestone.status == "APPROVED":
            raise ValueError("Cannot relinquish an already completed and approved milestone.")

        prev_freelancer_id = contract.current_freelancer_id
        prev_freelancer = self.freelancers.get(prev_freelancer_id)

        # If replacement freelancer not specified, find best match among other registered freelancers
        if not new_freelancer_id:
            candidates = [f for f_id, f in self.freelancers.items() if f_id != prev_freelancer_id]
            if not candidates:
                raise ValueError("No alternate qualified freelancers available for reassignment.")
            # Rank candidates by qualification score for this contract
            candidates.sort(key=lambda f: f.calculate_qualification_score(contract.required_skills)["match_percentage"], reverse=True)
            new_freelancer = candidates[0]
            new_freelancer_id = new_freelancer.id
        else:
            new_freelancer = self.freelancers.get(new_freelancer_id)
            if not new_freelancer:
                raise ValueError(f"Replacement freelancer '{new_freelancer_id}' not found.")

        # Compute remaining unpaid budget for contract
        remaining_budget = sum(m.amount for m in contract.milestones if m.status != "APPROVED")
        
        # Relinquish incomplete milestone
        milestone.status = "RELINQUISHED"
        milestone.description += f" [Relinquished from {prev_freelancer.name if prev_freelancer else prev_freelancer_id}. Reassigned to {new_freelancer.name}]"

        # Record relinquish event
        relinquish_record = {
            "milestone_index": milestone_index,
            "previous_freelancer_id": prev_freelancer_id,
            "previous_freelancer_name": prev_freelancer.name if prev_freelancer else "Unknown",
            "new_freelancer_id": new_freelancer.id,
            "new_freelancer_name": new_freelancer.name,
            "remaining_budget": remaining_budget,
            "reason": reason,
            "timestamp": self.virtual_time
        }
        contract.relinquish_history.append(relinquish_record)

        # Reassign contract
        contract.current_freelancer_id = new_freelancer.id
        contract.tracker_stage = 3
        contract.tracker_stage_label = f"Task Relinquished & Reassigned to {new_freelancer.name}"

        # Restart milestone under new freelancer
        milestone.start_milestone(new_freelancer.id, self.virtual_time)
        milestone.status = "IN_PROGRESS"

        # On-chain Relinquish Settlement & Reassignment Transaction
        reassign_tx = Transaction(
            sender=contract.smart_contract_address,
            recipient=new_freelancer.wallet_address,
            amount=0.0,
            tx_type="TASK_RELINQUISHED_AND_REASSIGNED",
            contract_id=contract.id,
            milestone_index=milestone_index,
            metadata={
                "relinquished_from": prev_freelancer_id,
                "reassigned_to": new_freelancer_id,
                "remaining_budget": remaining_budget,
                "reason": reason,
                "protocol_guarantee": "Fair compensation preserved for all completed work"
            }
        )
        self.blockchain.add_transaction(reassign_tx)
        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")

        contract.log_audit("TASK_RELINQUISHED_REASSIGNED", "PROTOCOL_ENGINE", relinquish_record, self.virtual_time)

        return {
            "success": True,
            "previous_freelancer": prev_freelancer.name if prev_freelancer else prev_freelancer_id,
            "new_freelancer": new_freelancer.name,
            "milestone_index": milestone_index,
            "remaining_budget": remaining_budget,
            "contract": contract.to_dict()
        }

    def raise_dispute(self, job_id: str, milestone_index: int, raised_by: str, reason: str) -> Dict[str, Any]:
        contract = self.contracts.get(job_id)
        if not contract:
            raise ValueError(f"Contract {job_id} not found")
        milestone = contract.milestones[milestone_index]
        
        milestone.status = "DISPUTED"
        contract.status = "DISPUTED"
        contract.tracker_stage = 4
        contract.tracker_stage_label = "Under Arbitration & Verifiable Audit"

        contract.dispute_info = {
            "milestone_index": milestone_index,
            "raised_by": raised_by,
            "reason": reason,
            "status": "ARBITRATION_PENDING",
            "timestamp": self.virtual_time
        }

        # On-chain dispute lock
        dispute_tx = Transaction(
            sender=contract.smart_contract_address,
            recipient="0xFAIRWORK_ARBITRATION_DAO",
            amount=0.0,
            tx_type="CONTRACT_DISPUTE_FILED",
            contract_id=contract.id,
            milestone_index=milestone_index,
            metadata={"reason": reason, "raised_by": raised_by}
        )
        self.blockchain.add_transaction(dispute_tx)
        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")

        contract.log_audit("DISPUTE_RAISED", raised_by, {"milestone_index": milestone_index, "reason": reason}, self.virtual_time)
        return contract.dispute_info

    def resolve_dispute(self, job_id: str, milestone_index: int, freelancer_split_pct: float, resolution_notes: str) -> Dict[str, Any]:
        contract = self.contracts.get(job_id)
        if not contract or not contract.dispute_info:
            raise ValueError("No active dispute found for contract.")
        milestone = contract.milestones[milestone_index]

        freelancer = self.freelancers[contract.current_freelancer_id]
        company = self.companies[contract.company_id]

        total_amount = milestone.amount
        freelancer_amt = round((freelancer_split_pct / 100.0) * total_amount, 2)
        company_amt = round(total_amount - freelancer_amt, 2)

        if freelancer_amt > 0:
            tx1 = Transaction(
                sender=contract.smart_contract_address,
                recipient=freelancer.wallet_address,
                amount=freelancer_amt,
                tx_type="DISPUTE_ARBITRATION_PAYOUT",
                contract_id=contract.id,
                milestone_index=milestone_index,
                metadata={"split": f"{freelancer_split_pct}%", "notes": resolution_notes}
            )
            self.blockchain.add_transaction(tx1)

        if company_amt > 0:
            tx2 = Transaction(
                sender=contract.smart_contract_address,
                recipient=company.wallet_address,
                amount=company_amt,
                tx_type="DISPUTE_ARBITRATION_REFUND",
                contract_id=contract.id,
                milestone_index=milestone_index,
                metadata={"split": f"{100.0 - freelancer_split_pct}%", "notes": resolution_notes}
            )
            self.blockchain.add_transaction(tx2)

        milestone.status = "APPROVED"
        contract.status = "ALLOTTED"
        contract.tracker_stage = 5
        contract.tracker_stage_label = f"Dispute Arbitrated: {freelancer_split_pct}% Paid / {100.0 - freelancer_split_pct}% Refunded"
        contract.dispute_info["status"] = "RESOLVED"
        contract.dispute_info["resolution_notes"] = resolution_notes
        contract.dispute_info["freelancer_payout"] = freelancer_amt
        contract.dispute_info["company_refund"] = company_amt

        self.blockchain.mine_pending_transactions(miner_address="0xVALIDATOR_NODE_PRIMARY")
        contract.log_audit("DISPUTE_RESOLVED", "ARBITRATION_DAO", {
            "freelancer_payout": freelancer_amt,
            "company_refund": company_amt,
            "notes": resolution_notes
        }, self.virtual_time)

        return contract.dispute_info

    def register_company(self, company_id: str, name: str, industry: str, initial_balance: float = 25000.0) -> CompanyProfile:
        clean_id = company_id.strip().lower().replace(" ", "_")
        if not clean_id.startswith("company_"):
            clean_id = f"company_{clean_id}"
        
        wallet = f"0xCOMP_{clean_id.upper()[:12]}_{hashlib.sha256(clean_id.encode()).hexdigest()[:6].upper()}"
        company = CompanyProfile(
            id=clean_id,
            name=name,
            industry=industry,
            wallet_address=wallet,
            rating=5.0,
            jobs_posted=0,
            total_spent=0.0,
            avatar="https://images.unsplash.com/photo-1549923746-c502d488b3ea?w=150&auto=format&fit=crop&q=80"
        )
        self.companies[clean_id] = company
        self.blockchain.set_wallet_balance(wallet, initial_balance)
        return company

    def register_freelancer(self, freelancer_id: str, name: str, title: str, skills: List[str],
                            hourly_rate: float = 75.0, bio: str = "", initial_balance: float = 1000.0) -> FreelancerProfile:
        clean_id = freelancer_id.strip().lower().replace(" ", "_")
        if not clean_id.startswith("freelancer_"):
            clean_id = f"freelancer_{clean_id}"
        
        wallet = f"0xFREE_{clean_id.upper()[:12]}_{hashlib.sha256(clean_id.encode()).hexdigest()[:6].upper()}"
        fl = FreelancerProfile(
            id=clean_id,
            name=name,
            title=title,
            wallet_address=wallet,
            skills=skills,
            hourly_rate=hourly_rate,
            rating=5.0,
            completed_jobs=0,
            reputation_score=850,
            bio=bio or f"Independent blockchain & software engineer specializing in {', '.join(skills[:3])}.",
            avatar="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
            badges=["Verified Identity", "New Talent"]
        )
        self.freelancers[clean_id] = fl
        self.blockchain.set_wallet_balance(wallet, initial_balance)
        return fl

    def get_user_by_id(self, user_id: str):
        if user_id in self.companies:
            return self.companies[user_id], "company"
        if user_id in self.freelancers:
            return self.freelancers[user_id], "freelancer"
        return None, None

