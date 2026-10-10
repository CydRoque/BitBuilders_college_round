"""
Persistent WhatsApp-Style Chat Store for Fairwork
Handles real-time message storage, image attachments, read receipts, and disk persistence.
"""

import time
import uuid
import json
import os
from typing import List, Dict, Any, Optional

CHAT_DB_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")

class ChatStore:
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.load_messages()
        if not self.messages:
            self._init_seed_messages()

    def load_messages(self):
        try:
            from backend.db import DatabaseService
            db_msgs = DatabaseService.load_chat_messages()
            if db_msgs:
                self.messages = db_msgs
                print(f"[PostgreSQL] Loaded {len(self.messages)} chat messages from database.")
                return
        except Exception as e:
            print(f"[Warning] Could not load messages from PostgreSQL: {e}")

        if os.path.exists(CHAT_DB_FILE):
            try:
                with open(CHAT_DB_FILE, "r", encoding="utf-8") as f:
                    self.messages = json.load(f)
            except Exception as e:
                print(f"Error loading chat history from file: {e}")
                self.messages = []

    def save_messages(self):
        try:
            with open(CHAT_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving chat history: {e}")

    def _init_seed_messages(self):
        now = time.time()
        # Seed realistic contract conversation between NovaTech and Alex Rivera
        seed = [
            {
                "id": str(uuid.uuid4()),
                "contract_id": "FWK-CONTRACT-101",
                "sender_id": "company_novatech",
                "sender_name": "NovaTech Systems",
                "sender_role": "company",
                "text": "Hello Alex! Welcome to the Fairwork Escrow project. We have locked 6,000 FWK into the smart contract vault.",
                "image_data": None,
                "timestamp": now - 3600,
                "read_by": ["company_novatech", "freelancer_alex"]
            },
            {
                "id": str(uuid.uuid4()),
                "contract_id": "FWK-CONTRACT-101",
                "sender_id": "freelancer_alex",
                "sender_name": "Alex Rivera",
                "sender_role": "freelancer",
                "text": "Thanks! I've started Milestone 1 (Escrow architecture). Here is a diagram of the multi-sig vault logic I'm implementing.",
                "image_data": "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=600&auto=format&fit=crop&q=80",
                "timestamp": now - 3000,
                "read_by": ["company_novatech", "freelancer_alex"]
            },
            {
                "id": str(uuid.uuid4()),
                "contract_id": "FWK-CONTRACT-101",
                "sender_id": "company_novatech",
                "sender_name": "NovaTech Systems",
                "sender_role": "company",
                "text": "Looks solid. Keep the deadline buffer in mind (24h deadline + 12h grace buffer). Looking forward to the deliverable submission!",
                "image_data": None,
                "timestamp": now - 1800,
                "read_by": ["company_novatech", "freelancer_alex"]
            }
        ]
        self.messages = seed
        self.save_messages()
        try:
            from backend.db import DatabaseService
            for m in seed:
                DatabaseService.save_chat_message(m)
        except Exception:
            pass

    def get_messages_for_contract(self, contract_id: str, mark_read_by: Optional[str] = None) -> List[Dict[str, Any]]:
        results = [m for m in self.messages if m.get("contract_id") == contract_id]
        if mark_read_by:
            modified = False
            for m in results:
                if mark_read_by not in m.setdefault("read_by", []):
                    m["read_by"].append(mark_read_by)
                    modified = True
                    try:
                        from backend.db import DatabaseService
                        DatabaseService.save_chat_message(m)
                    except Exception:
                        pass
            if modified:
                self.save_messages()
        return results

    def add_message(self, contract_id: str, sender_id: str, sender_name: str,
                    sender_role: str, text: str, image_data: Optional[str] = None) -> Dict[str, Any]:
        msg = {
            "id": str(uuid.uuid4()),
            "contract_id": contract_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_role": sender_role,
            "text": text or "",
            "image_data": image_data,
            "timestamp": time.time(),
            "read_by": [sender_id]
        }
        self.messages.append(msg)
        self.save_messages()
        try:
            from backend.db import DatabaseService
            DatabaseService.save_chat_message(msg)
        except Exception as e:
            print(f"[Warning] Failed to persist chat message to PostgreSQL: {e}")
        return msg

    def get_conversations_for_user(self, user_id: str, user_role: str, contracts_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        conversations = []
        for contract_id, contract in contracts_dict.items():
            # Check if user is part of contract
            is_participant = False
            counterpart_name = "Counterpart"
            counterpart_role = "counterpart"
            
            if user_role == "company" and contract.company_id == user_id:
                is_participant = True
                counterpart_name = contract.current_freelancer_id or "Unassigned Freelancer"
                counterpart_role = "freelancer"
            elif user_role == "freelancer" and (contract.current_freelancer_id == user_id or any(app.get("freelancer_id") == user_id for app in getattr(contract, "applications", []))):
                is_participant = True
                counterpart_name = contract.company_id
                counterpart_role = "company"

            if is_participant:
                msgs = self.get_messages_for_contract(contract_id)
                last_msg = msgs[-1] if msgs else None
                unread_count = sum(1 for m in msgs if user_id not in m.get("read_by", []))
                conversations.append({
                    "contract_id": contract_id,
                    "contract_title": contract.title,
                    "counterpart_name": counterpart_name,
                    "counterpart_role": counterpart_role,
                    "last_message": last_msg.get("text") if last_msg else "No messages yet",
                    "last_timestamp": last_msg.get("timestamp") if last_msg else contract.created_at,
                    "unread_count": unread_count
                })
        return conversations
