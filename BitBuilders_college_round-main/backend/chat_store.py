"""
Persistent Chat Store for Fairwork
Supports both PUBLIC channels (open to all platform users) and PRIVATE rooms
(contract-based rooms and user-created private/direct rooms), with real-time
message storage, image attachments, read receipts, and disk persistence.
"""

import time
import uuid
import json
import os
from typing import List, Dict, Any, Optional

CHAT_DB_FILE = os.path.join(os.path.dirname(__file__), "chat_history.json")
CHAT_ROOMS_FILE = os.path.join(os.path.dirname(__file__), "chat_rooms.json")
ROOM_SEP = "::"


def make_room_id(contract_id: str, freelancer_id: str) -> str:
    return f"{contract_id}{ROOM_SEP}{freelancer_id}"


def parse_room_id(room_id: str):
    """Return (contract_id, freelancer_id) or (None, None) if malformed or custom room."""
    if not isinstance(room_id, str) or ROOM_SEP not in room_id:
        return None, None
    prefix, rest = room_id.split(ROOM_SEP, 1)
    if prefix in ("public", "private"):
        return None, None
    if not prefix or not rest:
        return None, None
    return prefix, rest


class ChatStore:
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.custom_rooms: Dict[str, Dict[str, Any]] = {}
        self.load_rooms()
        self.load_messages()
        self._ensure_default_rooms()
        if not self.messages:
            self._init_seed_messages()

    def load_rooms(self):
        if os.path.exists(CHAT_ROOMS_FILE):
            try:
                with open(CHAT_ROOMS_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.custom_rooms = loaded
                    elif isinstance(loaded, list):
                        self.custom_rooms = {r["room_id"]: r for r in loaded if "room_id" in r}
            except Exception as e:
                print(f"Error loading custom chat rooms: {e}")
                self.custom_rooms = {}

    def save_rooms(self):
        try:
            with open(CHAT_ROOMS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.custom_rooms, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving custom chat rooms: {e}")

    def _ensure_default_rooms(self):
        now = time.time()
        defaults = [
            {
                "room_id": "public::general",
                "name": "General Platform Lounge",
                "description": "Public discussion channel for all registered companies and freelancers",
                "channel_type": "public",
                "created_by": "system",
                "created_by_name": "Fairwork Official",
                "participants": [],
                "created_at": now - 7200
            },
            {
                "room_id": "public::marketplace",
                "name": "Contract Opportunities & Q&A",
                "description": "Public channel to discuss open contracts, milestone scopes, and skills",
                "channel_type": "public",
                "created_by": "system",
                "created_by_name": "Fairwork Official",
                "participants": [],
                "created_at": now - 7000
            },
            {
                "room_id": "public::disputes_help",
                "name": "Escrow & Verification Support",
                "description": "Public forum for SHA-256 deliverable verification and escrow questions",
                "channel_type": "public",
                "created_by": "system",
                "created_by_name": "Fairwork Official",
                "participants": [],
                "created_at": now - 6800
            }
        ]
        changed = False
        for d in defaults:
            if d["room_id"] not in self.custom_rooms:
                self.custom_rooms[d["room_id"]] = d
                changed = True
        if changed:
            self.save_rooms()

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
        seed = [
            {
                "id": str(uuid.uuid4()),
                "contract_id": "PUBLIC",
                "room_id": "public::general",
                "sender_id": "company_novatech",
                "sender_name": "NovaTech Decentralized Systems",
                "sender_role": "company",
                "text": "Welcome to the Fairwork Public Lounge! We are actively hiring Solidity & Python engineers for milestone-backed escrow contracts.",
                "image_data": None,
                "timestamp": now - 5400,
                "read_by": ["company_novatech", "freelancer_alex", "freelancer_priya"]
            },
            {
                "id": str(uuid.uuid4()),
                "contract_id": "PUBLIC",
                "room_id": "public::general",
                "sender_id": "freelancer_priya",
                "sender_name": "Priya Sharma",
                "sender_role": "freelancer",
                "text": "Glad to be here! Available for full-stack Web3, smart contract audits, and rapid milestone handoffs.",
                "image_data": None,
                "timestamp": now - 4800,
                "read_by": ["company_novatech", "freelancer_alex", "freelancer_priya"]
            },
            {
                "id": str(uuid.uuid4()),
                "contract_id": "PUBLIC",
                "room_id": "public::marketplace",
                "sender_id": "freelancer_alex",
                "sender_name": "Alex Rivera",
                "sender_role": "freelancer",
                "text": "Tip for new contractors: always include your commit hash and test report link when submitting Milestone Proofs.",
                "image_data": None,
                "timestamp": now - 4200,
                "read_by": ["company_novatech", "freelancer_alex"]
            },
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

    # ---------- room creation ----------

    def create_room(self, name: str, channel_type: str, created_by: str, created_by_name: str,
                    participants: Optional[List[str]] = None, description: str = "",
                    contract_id: Optional[str] = None) -> Dict[str, Any]:
        channel_type = "public" if channel_type == "public" else "private"
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Room name is required.")

        slug = "".join(ch if ch.isalnum() else "_" for ch in clean_name.lower()).strip("_")[:24] or "room"
        short_id = uuid.uuid4().hex[:6]
        room_id = f"{channel_type}{ROOM_SEP}{slug}_{short_id}"

        member_set = []
        if channel_type == "private":
            raw_members = [created_by] + (participants or [])
            for uid in raw_members:
                if uid and uid not in member_set:
                    member_set.append(uid)
            if len(member_set) < 1:
                member_set = [created_by]

        room_obj = {
            "room_id": room_id,
            "name": clean_name,
            "description": (description or "").strip() or (
                "Public community room" if channel_type == "public" else "Private encrypted room"
            ),
            "channel_type": channel_type,
            "created_by": created_by,
            "created_by_name": created_by_name,
            "participants": member_set,
            "contract_id": contract_id or ("PUBLIC" if channel_type == "public" else "PRIVATE"),
            "created_at": time.time()
        }
        self.custom_rooms[room_id] = room_obj
        self.save_rooms()
        return room_obj

    # ---------- access control ----------

    def can_access_room(self, user_id: Optional[str], user_role: Optional[str], room_id: str,
                        contracts_dict: Dict[str, Any]) -> bool:
        """Check if user can access a public room, custom private room, or contract private room."""
        if not user_id or not isinstance(room_id, str):
            return False

        # 1. Public rooms are open to all authenticated users
        if room_id.startswith("public::"):
            return True

        # 2. Custom rooms (public or private)
        if room_id in self.custom_rooms:
            room = self.custom_rooms[room_id]
            if room.get("channel_type") == "public":
                return True
            return user_id == room.get("created_by") or user_id in (room.get("participants") or [])

        # 3. Contract-based private room "<contract_id>::<freelancer_id>"
        contract_id, freelancer_id = parse_room_id(room_id)
        contract = contracts_dict.get(contract_id) if contract_id else None
        if not contract:
            return False
        if user_role == "company":
            return contract.company_id == user_id
        if user_role == "freelancer":
            if freelancer_id != user_id:
                return False
            return (
                contract.current_freelancer_id == user_id
                or any(getattr(m, "assigned_freelancer_id", None) == user_id for m in getattr(contract, "milestones", []))
                or any(a.get("freelancer_id") == user_id for a in getattr(contract, "applications", []))
            )
        return False

    def participants_of_room(self, room_id: str, contracts_dict: Dict[str, Any],
                             all_user_ids: Optional[List[str]] = None) -> List[str]:
        if room_id.startswith("public::"):
            return list(all_user_ids or [])
        if room_id in self.custom_rooms:
            room = self.custom_rooms[room_id]
            if room.get("channel_type") == "public":
                return list(all_user_ids or [])
            return list(room.get("participants") or [])
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
        # Ensure seed public messages exist if upgrading from an older chat_history.json
        if not any(str(m.get("room_id", "")).startswith("public::") for m in self.messages):
            now = time.time()
            pub_seed = [
                {
                    "id": str(uuid.uuid4()),
                    "contract_id": "PUBLIC",
                    "room_id": "public::general",
                    "sender_id": "company_novatech",
                    "sender_name": "NovaTech Decentralized Systems",
                    "sender_role": "company",
                    "text": "Welcome to the Fairwork Public Lounge! Feel free to discuss contracts or create new public/private rooms.",
                    "image_data": None,
                    "timestamp": now - 3600,
                    "read_by": ["company_novatech"]
                }
            ]
            self.messages.extend(pub_seed)
            changed = True
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
        if not contract_id:
            if room_id in self.custom_rooms:
                contract_id = self.custom_rooms[room_id].get("contract_id", "CUSTOM")
            elif room_id.startswith("public::"):
                contract_id = "PUBLIC"
            else:
                contract_id = "PRIVATE"

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
        seen_rooms = set()

        def resolve_user_name(uid: str) -> str:
            if uid in companies:
                return companies[uid].name
            if uid in freelancers:
                return freelancers[uid].name
            return uid

        # 1. Public & Custom Rooms
        for room_id, room in self.custom_rooms.items():
            ctype = room.get("channel_type", "public")
            if ctype == "private":
                if user_id != room.get("created_by") and user_id not in (room.get("participants") or []):
                    continue

            msgs = self.get_messages_for_room(room_id)
            last_msg = msgs[-1] if msgs else None
            seen_rooms.add(room_id)

            if ctype == "public":
                subtitle = room.get("description") or "Public Channel · All Users"
                counterpart_name = room.get("name", room_id)
                contract_label = "PUBLIC CHANNEL"
            else:
                others = [resolve_user_name(p) for p in (room.get("participants") or []) if p != user_id]
                subtitle = f"Participants: {', '.join(others)}" if others else "Private Room (Only You)"
                counterpart_name = room.get("name") or (", ".join(others) if others else "Private Room")
                contract_label = room.get("contract_id") or "PRIVATE ROOM"

            conversations.append({
                "room_id": room_id,
                "channel_type": ctype,
                "contract_id": contract_label,
                "contract_title": subtitle,
                "counterpart_id": room.get("created_by", "system"),
                "counterpart_name": counterpart_name,
                "counterpart_role": ctype,
                "is_assigned": True,
                "participants_names": [resolve_user_name(p) for p in (room.get("participants") or [])],
                "last_message": (
                    f"{last_msg.get('sender_name', 'User')}: {last_msg.get('text') or '📷 Image'}"
                    if last_msg else room.get("description", "No messages yet")
                ),
                "last_timestamp": last_msg.get("timestamp") if last_msg else room.get("created_at", 0),
                "unread_count": sum(1 for m in msgs if user_id not in m.get("read_by", []))
            })

        # 2. Contract-based Private Rooms
        def build_contract_room(contract, freelancer_id):
            room_id = make_room_id(contract.id, freelancer_id)
            if room_id in seen_rooms:
                return
            seen_rooms.add(room_id)
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
                "channel_type": "private",
                "contract_id": contract.id,
                "contract_title": contract.title,
                "counterpart_id": freelancer_id if user_role == "company" else contract.company_id,
                "counterpart_name": other_name,
                "counterpart_role": other_role,
                "is_assigned": contract.current_freelancer_id == freelancer_id,
                "participants_names": [
                    companies[contract.company_id].name if contract.company_id in companies else contract.company_id,
                    freelancers[freelancer_id].name if freelancer_id in freelancers else freelancer_id
                ],
                "last_message": (last_msg.get("text") or "📷 Image") if last_msg else "No messages yet",
                "last_timestamp": last_msg.get("timestamp") if last_msg else contract.created_at,
                "unread_count": sum(1 for m in msgs if user_id not in m.get("read_by", []))
            })

        for contract in contracts_dict.values():
            if user_role == "company" and contract.company_id == user_id:
                fids = []
                if contract.current_freelancer_id:
                    fids.append(contract.current_freelancer_id)
                for m in getattr(contract, "milestones", []):
                    mfid = getattr(m, "assigned_freelancer_id", None)
                    if mfid and mfid not in fids:
                        fids.append(mfid)
                fids += [a.get("freelancer_id") for a in getattr(contract, "applications", [])
                         if a.get("freelancer_id") and a.get("freelancer_id") not in fids]
                for fid in fids:
                    build_contract_room(contract, fid)
            elif user_role == "freelancer" and (
                    contract.current_freelancer_id == user_id
                    or any(getattr(m, "assigned_freelancer_id", None) == user_id for m in getattr(contract, "milestones", []))
                    or any(a.get("freelancer_id") == user_id for a in getattr(contract, "applications", []))):
                build_contract_room(contract, user_id)

        conversations.sort(key=lambda c: c["last_timestamp"] or 0, reverse=True)
        return conversations
