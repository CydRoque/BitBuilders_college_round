"""
Persistent WhatsApp-Style Chat Store for Fairwork
Handles real-time message storage, image attachments, read receipts, and disk persistence.

Chats are PRIVATE rooms: one room per (contract, freelancer) pair, id "<contract_id>::<freelancer_id>".
Only the contract's company and that one freelancer may read or write a room.
"""

import time
import uuid
import json
import os
from typing import List, Dict, Any, Optional

CHAT_DB_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")
ROOM_SEP = "::"


def make_room_id(contract_id: str, freelancer_id: str) -> str:
    return f"{contract_id}{ROOM_SEP}{freelancer_id}"


def parse_room_id(room_id: str):
    """Return (contract_id, freelancer_id) or (None, None) if malformed."""
    if not isinstance(room_id, str) or ROOM_SEP not in room_id:
        return None, None
    contract_id, freelancer_id = room_id.split(ROOM_SEP, 1)
    if not contract_id or not freelancer_id:
        return None, None
    return contract_id, freelancer_id

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
                "room_id": make_room_id("FWK-CONTRACT-101", "freelancer_alex"),
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
                "room_id": make_room_id("FWK-CONTRACT-101", "freelancer_alex"),
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
                "room_id": make_room_id("FWK-CONTRACT-101", "freelancer_alex"),
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

    # ---------- access control ----------

    @staticmethod
    def can_access_room(user_id: Optional[str], user_role: Optional[str], room_id: str,
                        contracts_dict: Dict[str, Any]) -> bool:
        """True only for the contract's company, or the room's freelancer (assigned or applicant)."""
        if not user_id:
            return False
        contract_id, freelancer_id = parse_room_id(room_id)
        contract = contracts_dict.get(contract_id) if contract_id else None
        if not contract:
            return False
        if user_role == "company":
            return contract.company_id == user_id
        if user_role == "freelancer":
            if freelancer_id != user_id:
                return False
            return contract.current_freelancer_id == user_id or any(
                a.get("freelancer_id") == user_id for a in getattr(contract, "applications", []))
        return False

    @staticmethod
    def participants_of_room(room_id: str, contracts_dict: Dict[str, Any]) -> List[str]:
        contract_id, freelancer_id = parse_room_id(room_id)
        contract = contracts_dict.get(contract_id) if contract_id else None
        return [contract.company_id, freelancer_id] if contract else []

    def migrate_legacy(self, contracts_dict: Dict[str, Any]):
        """Assign room_id to messages saved before private rooms existed."""
        changed = False
        for m in self.messages:
            if m.get("room_id"):
                continue
            contract = contracts_dict.get(m.get("contract_id"))
            if m.get("sender_role") == "freelancer":
                fid = m.get("sender_id")
            else:
                fid = contract.current_freelancer_id if contract else None
                if not fid:
                    fid = next((x.get("sender_id") for x in self.messages
                                if x.get("contract_id") == m.get("contract_id")
                                and x.get("sender_role") == "freelancer"), None)
            if fid:
                m["room_id"] = make_room_id(m["contract_id"], fid)
                changed = True
                try:
                    from backend.db import DatabaseService
                    DatabaseService.set_chat_room(m["id"], m["room_id"])
                except Exception:
                    pass
        if changed:
            self.save_messages()

    # ---------- messages ----------

    def get_messages_for_room(self, room_id: str, mark_read_by: Optional[str] = None) -> List[Dict[str, Any]]:
        results = [m for m in self.messages if m.get("room_id") == room_id]
        if mark_read_by:
            self.mark_room_read(room_id, mark_read_by)
        return results

    def mark_room_read(self, room_id: str, user_id: str) -> List[str]:
        """Mark every message in the room as read by user_id. Returns ids that changed."""
        changed_ids = []
        for m in self.messages:
            if m.get("room_id") == room_id and user_id not in m.setdefault("read_by", []):
                m["read_by"].append(user_id)
                changed_ids.append(m["id"])
                try:
                    from backend.db import DatabaseService
                    DatabaseService.save_chat_message(m)
                except Exception:
                    pass
        if changed_ids:
            self.save_messages()
        return changed_ids

    def add_message(self, room_id: str, sender_id: str, sender_name: str,
                    sender_role: str, text: str, image_data: Optional[str] = None) -> Dict[str, Any]:
        contract_id, _ = parse_room_id(room_id)
        msg = {
            "id": str(uuid.uuid4()),
            "contract_id": contract_id,
            "room_id": room_id,
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

    def get_conversations_for_user(self, user_id: str, user_role: str, contracts_dict: Dict[str, Any],
                                   companies: Optional[Dict[str, Any]] = None,
                                   freelancers: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        companies = companies or {}
        freelancers = freelancers or {}
        conversations = []

        def build(contract, freelancer_id):
            room_id = make_room_id(contract.id, freelancer_id)
            msgs = self.get_messages_for_room(room_id)
            last_msg = msgs[-1] if msgs else None
            if user_role == "company":
                other = freelancers.get(freelancer_id)
                other_name, other_role = (other.name if other else freelancer_id), "freelancer"
            else:
                other = companies.get(contract.company_id)
                other_name, other_role = (other.name if other else contract.company_id), "company"
            conversations.append({
                "room_id": room_id,
                "contract_id": contract.id,
                "contract_title": contract.title,
                "counterpart_id": freelancer_id if user_role == "company" else contract.company_id,
                "counterpart_name": other_name,
                "counterpart_role": other_role,
                "is_assigned": contract.current_freelancer_id == freelancer_id,
                "last_message": (last_msg.get("text") or "📷 Image") if last_msg else "No messages yet",
                "last_timestamp": last_msg.get("timestamp") if last_msg else contract.created_at,
                "unread_count": sum(1 for m in msgs if user_id not in m.get("read_by", []))
            })

        for contract in contracts_dict.values():
            if user_role == "company" and contract.company_id == user_id:
                fids = []
                if contract.current_freelancer_id:
                    fids.append(contract.current_freelancer_id)
                fids += [a.get("freelancer_id") for a in getattr(contract, "applications", [])
                         if a.get("freelancer_id") and a.get("freelancer_id") not in fids]
                for fid in fids:
                    build(contract, fid)
            elif user_role == "freelancer" and (
                    contract.current_freelancer_id == user_id or
                    any(a.get("freelancer_id") == user_id for a in getattr(contract, "applications", []))):
                build(contract, user_id)

        conversations.sort(key=lambda c: c["last_timestamp"] or 0, reverse=True)
        return conversations
