"""
PostgreSQL Database Layer for Fairwork
Provides long-term persistence for Users, Contracts, Milestones,
Mined Blockchain Blocks & Transactions, and WhatsApp Chat Messages.
"""

import os
import json
import time
from typing import List, Dict, Any, Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, Boolean, BigInteger
)
from sqlalchemy.orm import declarative_base, sessionmaker

PG_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:0310@localhost:5432/fairwork_db"
)

try:
    engine = create_engine(PG_URL, pool_pre_ping=True, echo=False)
    # Test connection
    with engine.connect() as conn:
        pass
    print("[PostgreSQL] Connected successfully to fairwork_db on localhost:5432")
except Exception as e:
    print(f"[Warning] PostgreSQL connection failed ({e}). Falling back to sqlite:///fairwork.db")
    engine = create_engine("sqlite:///fairwork.db", echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Table Definitions ---

class UserDB(Base):
    __tablename__ = "users"
    id = Column(String(100), primary_key=True)
    role = Column(String(20), nullable=False) # 'company' or 'freelancer'
    name = Column(String(255), nullable=False)
    title_or_industry = Column(String(255), nullable=True)
    wallet_address = Column(String(100), unique=True, nullable=False)
    skills_json = Column(Text, default="[]")
    hourly_rate = Column(Float, default=75.0)
    rating = Column(Float, default=5.0)
    completed_jobs = Column(Integer, default=0)
    reputation_score = Column(Integer, default=900)
    bio = Column(Text, default="")
    avatar = Column(Text, default="")
    badges_json = Column(Text, default="[]")

class ContractDB(Base):
    __tablename__ = "contracts"
    id = Column(String(100), primary_key=True)
    company_id = Column(String(100), nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(100), default="Development")
    description = Column(Text, default="")
    required_skills_json = Column(Text, default="[]")
    total_budget = Column(Float, default=0.0)
    escrow_locked = Column(Float, default=0.0)
    escrow_released = Column(Float, default=0.0)
    status = Column(String(50), default="OPEN")
    current_freelancer_id = Column(String(100), nullable=True)
    current_milestone_index = Column(Integer, default=0)
    smart_contract_address = Column(String(100), nullable=False)
    tracker_stage = Column(Integer, default=1)
    tracker_stage_label = Column(String(255), default="Created & Escrow Locked")
    milestones_json = Column(Text, default="[]")
    applications_json = Column(Text, default="[]")
    relinquish_history_json = Column(Text, default="[]")
    created_at = Column(Float, default=time.time)

class BlockDB(Base):
    __tablename__ = "blockchain_blocks"
    index = Column(Integer, primary_key=True)
    hash = Column(String(64), nullable=False, unique=True)
    previous_hash = Column(String(64), nullable=False)
    merkle_root = Column(String(64), nullable=False)
    timestamp = Column(Float, nullable=False)
    nonce = Column(BigInteger, default=0)
    tx_count = Column(Integer, default=0)
    transactions_json = Column(Text, default="[]")

class TransactionDB(Base):
    __tablename__ = "blockchain_transactions"
    tx_id = Column(String(64), primary_key=True)
    block_index = Column(Integer, nullable=True)
    sender = Column(String(100), nullable=False)
    recipient = Column(String(100), nullable=False)
    amount = Column(Float, default=0.0)
    tx_type = Column(String(50), nullable=False)
    contract_id = Column(String(100), nullable=True)
    milestone_index = Column(Integer, nullable=True)
    signature = Column(String(100), nullable=True)
    timestamp = Column(Float, nullable=False)
    metadata_json = Column(Text, default="{}")

class WalletDB(Base):
    __tablename__ = "wallets"
    address = Column(String(100), primary_key=True)
    balance = Column(Float, default=0.0)

class ChatMessageDB(Base):
    __tablename__ = "chat_messages"
    id = Column(String(100), primary_key=True)
    contract_id = Column(String(100), nullable=False, index=True)
    sender_id = Column(String(100), nullable=False)
    sender_name = Column(String(255), nullable=False)
    sender_role = Column(String(50), nullable=False)
    text = Column(Text, default="")
    image_data = Column(Text, nullable=True)
    timestamp = Column(Float, nullable=False)
    read_by_json = Column(Text, default="[]")

# Create tables
Base.metadata.create_all(bind=engine)

# --- Database Helper Service ---

class DatabaseService:
    @staticmethod
    def save_block_and_transactions(block_dict: Dict[str, Any]):
        db = SessionLocal()
        try:
            # Check if block exists
            existing = db.query(BlockDB).filter(BlockDB.index == block_dict["index"]).first()
            if not existing:
                b = BlockDB(
                    index=block_dict["index"],
                    hash=block_dict["hash"],
                    previous_hash=block_dict["previous_hash"],
                    merkle_root=block_dict["merkle_root"],
                    timestamp=block_dict["timestamp"],
                    nonce=block_dict["nonce"],
                    tx_count=block_dict["tx_count"],
                    transactions_json=json.dumps(block_dict["transactions"])
                )
                db.add(b)

            # Insert transactions
            for tx in block_dict.get("transactions", []):
                tx_id = tx.get("tx_id")
                if tx_id:
                    tx_existing = db.query(TransactionDB).filter(TransactionDB.tx_id == tx_id).first()
                    if not tx_existing:
                        t = TransactionDB(
                            tx_id=tx_id,
                            block_index=block_dict["index"],
                            sender=tx.get("sender", ""),
                            recipient=tx.get("recipient", ""),
                            amount=tx.get("amount", 0.0),
                            tx_type=tx.get("tx_type", ""),
                            contract_id=tx.get("contract_id"),
                            milestone_index=tx.get("milestone_index"),
                            signature=tx.get("signature"),
                            timestamp=tx.get("timestamp", time.time()),
                            metadata_json=json.dumps(tx.get("metadata", {}))
                        )
                        db.add(t)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[DB Error] save_block: {e}")
        finally:
            db.close()

    @staticmethod
    def load_all_blocks() -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            records = db.query(BlockDB).order_by(BlockDB.index.asc()).all()
            blocks = []
            for r in records:
                blocks.append({
                    "index": r.index,
                    "hash": r.hash,
                    "previous_hash": r.previous_hash,
                    "merkle_root": r.merkle_root,
                    "timestamp": r.timestamp,
                    "nonce": r.nonce,
                    "tx_count": r.tx_count,
                    "transactions": json.loads(r.transactions_json or "[]")
                })
            return blocks
        finally:
            db.close()

    @staticmethod
    def save_wallet_balance(address: str, balance: float):
        db = SessionLocal()
        try:
            w = db.query(WalletDB).filter(WalletDB.address == address).first()
            if not w:
                w = WalletDB(address=address, balance=balance)
                db.add(w)
            else:
                w.balance = balance
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[DB Error] save_wallet: {e}")
        finally:
            db.close()

    @staticmethod
    def load_all_wallets() -> Dict[str, float]:
        db = SessionLocal()
        try:
            records = db.query(WalletDB).all()
            return {r.address: r.balance for r in records}
        finally:
            db.close()

    @staticmethod
    def save_contract(contract_dict: Dict[str, Any]):
        db = SessionLocal()
        try:
            c = db.query(ContractDB).filter(ContractDB.id == contract_dict["id"]).first()
            if not c:
                c = ContractDB(id=contract_dict["id"])
                db.add(c)
            c.company_id = contract_dict["company_id"]
            c.title = contract_dict["title"]
            c.category = contract_dict.get("category", "Development")
            c.description = contract_dict.get("description", "")
            c.required_skills_json = json.dumps(contract_dict.get("required_skills", []))
            c.total_budget = contract_dict.get("total_budget", 0.0)
            c.escrow_locked = contract_dict.get("escrow_locked", 0.0)
            c.escrow_released = contract_dict.get("escrow_released", 0.0)
            c.status = contract_dict.get("status", "OPEN")
            c.current_freelancer_id = contract_dict.get("current_freelancer_id")
            c.current_milestone_index = contract_dict.get("current_milestone_index", 0)
            c.smart_contract_address = contract_dict["smart_contract_address"]
            c.tracker_stage = contract_dict.get("tracker_stage", 1)
            c.tracker_stage_label = contract_dict.get("tracker_stage_label", "")
            c.milestones_json = json.dumps(contract_dict.get("milestones", []))
            c.applications_json = json.dumps(contract_dict.get("applications", []))
            c.relinquish_history_json = json.dumps(contract_dict.get("relinquish_history", []))
            c.created_at = contract_dict.get("created_at", time.time())
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[DB Error] save_contract: {e}")
        finally:
            db.close()

    @staticmethod
    def load_all_contracts() -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            records = db.query(ContractDB).all()
            contracts = []
            for r in records:
                contracts.append({
                    "id": r.id,
                    "company_id": r.company_id,
                    "title": r.title,
                    "category": r.category,
                    "description": r.description,
                    "required_skills": json.loads(r.required_skills_json or "[]"),
                    "total_budget": r.total_budget,
                    "escrow_locked": r.escrow_locked,
                    "escrow_released": r.escrow_released,
                    "status": r.status,
                    "current_freelancer_id": r.current_freelancer_id,
                    "current_milestone_index": r.current_milestone_index,
                    "smart_contract_address": r.smart_contract_address,
                    "tracker_stage": r.tracker_stage,
                    "tracker_stage_label": r.tracker_stage_label,
                    "milestones": json.loads(r.milestones_json or "[]"),
                    "applications": json.loads(r.applications_json or "[]"),
                    "relinquish_history": json.loads(r.relinquish_history_json or "[]"),
                    "created_at": r.created_at
                })
            return contracts
        finally:
            db.close()

    @staticmethod
    def save_chat_message(msg_dict: Dict[str, Any]):
        db = SessionLocal()
        try:
            m = db.query(ChatMessageDB).filter(ChatMessageDB.id == msg_dict["id"]).first()
            if not m:
                m = ChatMessageDB(
                    id=msg_dict["id"],
                    contract_id=msg_dict["contract_id"],
                    sender_id=msg_dict["sender_id"],
                    sender_name=msg_dict["sender_name"],
                    sender_role=msg_dict["sender_role"],
                    text=msg_dict.get("text", ""),
                    image_data=msg_dict.get("image_data"),
                    timestamp=msg_dict.get("timestamp", time.time()),
                    read_by_json=json.dumps(msg_dict.get("read_by", []))
                )
                db.add(m)
            else:
                m.read_by_json = json.dumps(msg_dict.get("read_by", []))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[DB Error] save_chat_message: {e}")
        finally:
            db.close()

    @staticmethod
    def load_chat_messages(contract_id: Optional[str] = None) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            query = db.query(ChatMessageDB)
            if contract_id:
                query = query.filter(ChatMessageDB.contract_id == contract_id)
            records = query.order_by(ChatMessageDB.timestamp.asc()).all()
            messages = []
            for r in records:
                messages.append({
                    "id": r.id,
                    "contract_id": r.contract_id,
                    "sender_id": r.sender_id,
                    "sender_name": r.sender_name,
                    "sender_role": r.sender_role,
                    "text": r.text,
                    "image_data": r.image_data,
                    "timestamp": r.timestamp,
                    "read_by": json.loads(r.read_by_json or "[]")
                })
            return messages
        finally:
            db.close()
