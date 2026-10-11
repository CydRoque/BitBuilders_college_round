"""
Data models for Fairwork platform:
Users, Freelancer qualifications, Job contracts, Milestones, and Tracker states.
"""

import time
import uuid
from typing import List, Dict, Any, Optional

class FreelancerProfile:
    def __init__(self, id: str, name: str, title: str, wallet_address: str, skills: List[str],
                 hourly_rate: float, rating: float, completed_jobs: int, reputation_score: int,
                 bio: str, avatar: str, badges: Optional[List[str]] = None, verification_status: str = "VERIFIED"):
        self.id = id
        self.name = name
        self.title = title
        self.wallet_address = wallet_address
        self.skills = skills
        self.hourly_rate = hourly_rate
        self.rating = rating
        self.completed_jobs = completed_jobs
        self.reputation_score = reputation_score  # out of 1000
        self.bio = bio
        self.avatar = avatar
        self.badges = badges or ["Identity Verified", "Skill Tested"]
        self.verification_status = verification_status

    def calculate_qualification_score(self, required_skills: List[str]) -> Dict[str, Any]:
        """Calculates a multi-factor qualification match score (0-100%)."""
        if not required_skills:
            return {"match_percentage": 95, "breakdown": "Default match"}
        
        user_skills_lower = [s.lower().strip() for s in self.skills]
        matched = [req for req in required_skills if req.lower().strip() in user_skills_lower]
        skill_score = (len(matched) / len(required_skills)) * 50  # 50% weight for skills
        
        rating_score = (min(self.rating, 5.0) / 5.0) * 25         # 25% weight for rating
        rep_score = (min(self.reputation_score, 1000) / 1000.0) * 25 # 25% weight for reputation
        
        final_pct = round(skill_score + rating_score + rep_score, 1)
        return {
            "match_percentage": min(final_pct, 100.0),
            "matched_skills": matched,
            "missing_skills": [req for req in required_skills if req.lower().strip() not in user_skills_lower],
            "rating_weight": round(rating_score, 1),
            "reputation_weight": round(rep_score, 1),
            "skill_match_weight": round(skill_score, 1)
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "wallet_address": self.wallet_address,
            "skills": self.skills,
            "hourly_rate": self.hourly_rate,
            "rating": self.rating,
            "completed_jobs": self.completed_jobs,
            "reputation_score": self.reputation_score,
            "bio": self.bio,
            "avatar": self.avatar,
            "badges": self.badges,
            "verification_status": self.verification_status
        }

class CompanyProfile:
    def __init__(self, id: str, name: str, industry: str, wallet_address: str,
                 rating: float, jobs_posted: int, total_spent: float, avatar: str,
                 verified: bool = True):
        self.id = id
        self.name = name
        self.industry = industry
        self.wallet_address = wallet_address
        self.rating = rating
        self.jobs_posted = jobs_posted
        self.total_spent = total_spent
        self.avatar = avatar
        self.verified = verified

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "industry": self.industry,
            "wallet_address": self.wallet_address,
            "rating": self.rating,
            "jobs_posted": self.jobs_posted,
            "total_spent": self.total_spent,
            "avatar": self.avatar,
            "verified": self.verified
        }

class Milestone:
    def __init__(self, index: int, title: str, description: str, amount: float,
                 deadline_hours: float, buffer_hours: float = 24.0, penalty_rate_per_hour: float = 3.0,
                 max_penalty_percent: float = 30.0):
        self.index = index
        self.title = title
        self.description = description
        self.amount = float(amount)
        self.deadline_hours = float(deadline_hours)
        self.buffer_hours = float(buffer_hours)
        self.penalty_rate_per_hour = float(penalty_rate_per_hour) # % of milestone amount per hour late
        self.max_penalty_percent = float(max_penalty_percent)   # cap on penalty deduction
        
        # State tracking
        self.status = "PENDING"  # PENDING, IN_PROGRESS, SUBMITTED, APPROVED, DISPUTED, RELINQUISHED
        self.start_timestamp: Optional[float] = None
        self.deadline_timestamp: Optional[float] = None
        self.buffer_expiry_timestamp: Optional[float] = None
        
        # Deliverable submission
        self.submission_text: Optional[str] = None
        self.deliverable_hash: Optional[str] = None
        self.submitted_at: Optional[float] = None
        self.submitted_by: Optional[str] = None
        
        # Financial settlement
        self.delay_hours: float = 0.0
        self.penalty_amount: float = 0.0
        self.payout_amount: float = 0.0
        self.refund_amount: float = 0.0
        self.settled_at: Optional[float] = None
        self.tx_id: Optional[str] = None
        self.assigned_freelancer_id: Optional[str] = None

    def start_milestone(self, freelancer_id: str, current_virtual_time: float):
        self.status = "IN_PROGRESS"
        self.assigned_freelancer_id = freelancer_id
        self.start_timestamp = current_virtual_time
        self.deadline_timestamp = current_virtual_time + (self.deadline_hours * 3600)
        self.buffer_expiry_timestamp = self.deadline_timestamp + (self.buffer_hours * 3600)

    def submit_deliverable(self, deliverable_text: str, deliverable_hash: str, freelancer_id: str, submission_time: float) -> Dict[str, Any]:
        self.status = "SUBMITTED"
        self.submission_text = deliverable_text
        self.deliverable_hash = deliverable_hash
        self.submitted_by = freelancer_id
        self.submitted_at = submission_time
        
        # Check deadline breach
        delay_seconds = max(0.0, submission_time - (self.deadline_timestamp or submission_time))
        self.delay_hours = round(delay_seconds / 3600.0, 2)
        
        is_late = self.delay_hours > 0.0
        is_beyond_buffer = False
        
        if self.buffer_expiry_timestamp and submission_time > self.buffer_expiry_timestamp:
            is_beyond_buffer = True

        return {
            "is_late": is_late,
            "delay_hours": self.delay_hours,
            "is_beyond_buffer": is_beyond_buffer
        }

    def compute_settlement(self) -> Dict[str, float]:
        """Calculates fair payout, penalty deduction, and company refund."""
        if self.delay_hours <= 0:
            penalty = 0.0
        else:
            raw_penalty_pct = self.delay_hours * self.penalty_rate_per_hour
            capped_penalty_pct = min(raw_penalty_pct, self.max_penalty_percent)
            penalty = round((capped_penalty_pct / 100.0) * self.amount, 2)

        payout = round(self.amount - penalty, 2)
        refund = penalty
        self.penalty_amount = penalty
        self.payout_amount = payout
        self.refund_amount = refund
        return {
            "payout_to_freelancer": payout,
            "refund_to_company": refund,
            "penalty_amount": penalty
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "description": self.description,
            "amount": self.amount,
            "deadline_hours": self.deadline_hours,
            "buffer_hours": self.buffer_hours,
            "penalty_rate_per_hour": self.penalty_rate_per_hour,
            "max_penalty_percent": self.max_penalty_percent,
            "status": self.status,
            "start_timestamp": self.start_timestamp,
            "deadline_timestamp": self.deadline_timestamp,
            "buffer_expiry_timestamp": self.buffer_expiry_timestamp,
            "submission_text": self.submission_text,
            "deliverable_hash": self.deliverable_hash,
            "submitted_at": self.submitted_at,
            "submitted_by": self.submitted_by,
            "delay_hours": self.delay_hours,
            "penalty_amount": self.penalty_amount,
            "payout_amount": self.payout_amount,
            "refund_amount": self.refund_amount,
            "settled_at": self.settled_at,
            "tx_id": self.tx_id,
            "assigned_freelancer_id": self.assigned_freelancer_id
        }

class JobContract:
    def __init__(self, id: str, company_id: str, title: str, category: str, description: str,
                 required_skills: List[str], total_budget: float, milestones: List[Milestone],
                 created_at: float):
        self.id = id
        self.company_id = company_id
        self.title = title
        self.category = category
        self.description = description
        self.required_skills = required_skills
        self.total_budget = total_budget
        self.milestones = milestones
        self.created_at = created_at
        
        self.status = "OPEN" # OPEN, ALLOTTED, COMPLETED, DISPUTED
        self.current_freelancer_id: Optional[str] = None
        self.current_milestone_index: int = 0
        self.smart_contract_address = f"0xSC_{uuid.uuid4().hex[:12].upper()}"
        self.escrow_locked = 0.0
        self.escrow_released = 0.0
        
        # Amazon-style progress tracker stages
        # 1: Contract Created & Escrow Locked
        # 2: Freelancer Selected & Verified
        # 3: Active Milestone Execution
        # 4: Deliverable Submitted & Cryptographically Verified
        # 5: Milestone Funds Released to Freelancer
        # 6: Final Job Delivery Completed
        self.tracker_stage = 1
        self.tracker_stage_label = "Contract Created & Escrow Deposited"
        
        self.applications: List[Dict[str, Any]] = []
        self.relinquish_history: List[Dict[str, Any]] = []
        self.dispute_info: Optional[Dict[str, Any]] = None
        self.audit_log: List[Dict[str, Any]] = []

    def log_audit(self, event: str, actor: str, details: Dict[str, Any], timestamp: float):
        self.audit_log.append({
            "event": event,
            "actor": actor,
            "details": details,
            "timestamp": timestamp,
            "stage": self.tracker_stage
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "required_skills": self.required_skills,
            "total_budget": self.total_budget,
            "escrow_locked": self.escrow_locked,
            "escrow_released": self.escrow_released,
            "status": self.status,
            "current_freelancer_id": self.current_freelancer_id,
            "current_milestone_index": self.current_milestone_index,
            "smart_contract_address": self.smart_contract_address,
            "tracker_stage": self.tracker_stage,
            "tracker_stage_label": self.tracker_stage_label,
            "milestones": [m.to_dict() for m in self.milestones],
            "applications_count": len(self.applications),
            "applications": self.applications,
            "relinquish_history": self.relinquish_history,
            "dispute_info": self.dispute_info,
            "audit_log": self.audit_log,
            "created_at": self.created_at
        }
