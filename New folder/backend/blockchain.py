"""
Fairwork Blockchain Engine
Implements SHA-256 block hashing, Merkle root verification, Proof-of-Work mining,
Mempool transaction validation, and Smart Contract ledger balances.
"""

import hashlib
import json
import time
from typing import List, Dict, Any, Optional

def sha256_hash(data: str) -> str:
    return hashlib.sha256(data.encode('utf-8')).hexdigest()

def compute_merkle_root(transactions: List[Dict[str, Any]]) -> str:
    if not transactions:
        return sha256_hash("EMPTY_BLOCK")
    
    current_level = [tx.get("tx_id", sha256_hash(json.dumps(tx, sort_keys=True))) for tx in transactions]
    
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else current_level[i]
            combined = sha256_hash(left + right)
            next_level.append(combined)
        current_level = next_level
    
    return current_level[0]

class Transaction:
    def __init__(self, sender: str, recipient: str, amount: float, tx_type: str, 
                 contract_id: Optional[str] = None, milestone_index: Optional[int] = None,
                 metadata: Optional[Dict[str, Any]] = None, timestamp: Optional[float] = None):
        self.sender = sender
        self.recipient = recipient
        self.amount = round(float(amount), 2)
        self.tx_type = tx_type  # 'ESCROW_LOCK', 'MILESTONE_PAYOUT', 'PENALTY_REFUND', 'RELINQUISH_SETTLEMENT', 'GENESIS_CREDIT'
        self.contract_id = contract_id
        self.milestone_index = milestone_index
        self.metadata = metadata or {}
        self.timestamp = timestamp or time.time()
        self.tx_id = self.calculate_hash()
        self.signature = f"SIG_{sha256_hash(f'{self.sender}_{self.tx_id}')[:16]}"

    def calculate_hash(self) -> str:
        payload = f"{self.sender}:{self.recipient}:{self.amount}:{self.tx_type}:{self.contract_id}:{self.milestone_index}:{self.timestamp}:{json.dumps(self.metadata, sort_keys=True)}"
        return sha256_hash(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "tx_type": self.tx_type,
            "contract_id": self.contract_id,
            "milestone_index": self.milestone_index,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "signature": self.signature
        }

class Block:
    def __init__(self, index: int, previous_hash: str, transactions: List[Dict[str, Any]], 
                 timestamp: Optional[float] = None, nonce: int = 0, hash_val: Optional[str] = None):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or time.time()
        self.nonce = nonce
        self.merkle_root = compute_merkle_root(transactions)
        self.hash = hash_val or self.calculate_hash()

    def calculate_hash(self) -> str:
        block_string = f"{self.index}:{self.previous_hash}:{self.merkle_root}:{self.timestamp}:{self.nonce}"
        return sha256_hash(block_string)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "tx_count": len(self.transactions),
            "transactions": self.transactions
        }

class Blockchain:
    def __init__(self, difficulty: int = 2, load_persisted: bool = True):
        self.chain: List[Block] = []
        self.pending_transactions: List[Transaction] = []
        self.difficulty = difficulty
        self.target_prefix = "0" * difficulty
        self.wallets: Dict[str, float] = {}
        if load_persisted:
            self.load_from_db()
        else:
            self.create_genesis_block(persist=False)

    def load_from_db(self):
        try:
            from backend.db import DatabaseService
            saved_blocks = DatabaseService.load_all_blocks()
            if saved_blocks:
                self.chain = [
                    Block(
                        index=b["index"],
                        previous_hash=b["previous_hash"],
                        transactions=b["transactions"],
                        timestamp=b["timestamp"],
                        nonce=b["nonce"],
                        hash_val=b["hash"]
                    )
                    for b in saved_blocks
                ]
                self.wallets = DatabaseService.load_all_wallets()
                print(f"[PostgreSQL] Loaded {len(self.chain)} blocks and {len(self.wallets)} wallet balances from database.")
                return
        except Exception as e:
            print(f"[Warning] Could not load blockchain from PostgreSQL: {e}")
        
        self.create_genesis_block()

    def create_genesis_block(self, persist: bool = True):
        genesis_tx = Transaction(
            sender="0x0000000000000000000000000000000000000000",
            recipient="0xFAIRWORK_PROTOCOL_TREASURY",
            amount=1000000.0,
            tx_type="GENESIS_SUPPLY",
            metadata={"network": "Fairwork Verifiable Subnet v2.4", "genesis_note": "Fair compensation for verified milestones"}
        )
        genesis_block = Block(
            index=0,
            previous_hash="0" * 64,
            transactions=[genesis_tx.to_dict()],
            timestamp=1700000000.0,
            nonce=1337
        )
        genesis_block.hash = genesis_block.calculate_hash()
        self.chain.append(genesis_block)
        self.wallets["0xFAIRWORK_PROTOCOL_TREASURY"] = 1000000.0
        if persist:
            try:
                from backend.db import DatabaseService
                DatabaseService.save_block_and_transactions(genesis_block.to_dict())
                DatabaseService.save_wallet_balance("0xFAIRWORK_PROTOCOL_TREASURY", 1000000.0)
            except Exception:
                pass

    @property
    def latest_block(self) -> Block:
        return self.chain[-1]

    def get_wallet_balance(self, address: str) -> float:
        return round(self.wallets.get(address, 0.0), 2)

    def set_wallet_balance(self, address: str, amount: float):
        self.wallets[address] = round(amount, 2)
        try:
            from backend.db import DatabaseService
            DatabaseService.save_wallet_balance(address, self.wallets[address])
        except Exception:
            pass

    def add_transaction(self, tx: Transaction) -> bool:
        # Check sender balance if not protocol minting
        if tx.sender != "0x0000000000000000000000000000000000000000" and not tx.sender.startswith("0xFAIRWORK_PROTOCOL"):
            sender_bal = self.get_wallet_balance(tx.sender)
            if sender_bal < tx.amount:
                raise ValueError(f"Insufficient funds in wallet {tx.sender}: balance is {sender_bal} USDC, requested {tx.amount} USDC")
            # Deduct immediately to prevent double spending in mempool
            self.set_wallet_balance(tx.sender, sender_bal - tx.amount)

        self.pending_transactions.append(tx)
        return True

    def mine_pending_transactions(self, miner_address: str = "0xFAIRWORK_VALIDATOR_NODE") -> Block:
        if not self.pending_transactions:
            # Create a heartbeat transaction so every block has proof
            heartbeat = Transaction(
                sender="0xFAIRWORK_PROTOCOL_VALIDATOR",
                recipient=miner_address,
                amount=5.0,
                tx_type="VALIDATOR_BLOCK_REWARD",
                metadata={"state": "heartbeat_consensus"}
            )
            txs_to_mine = [heartbeat.to_dict()]
        else:
            # Reward transaction
            reward_tx = Transaction(
                sender="0x0000000000000000000000000000000000000000",
                recipient=miner_address,
                amount=10.0,
                tx_type="MINING_REWARD",
                metadata={"note": f"Block #{len(self.chain)} Proof-of-Work verified reward"}
            )
            txs_to_mine = [tx.to_dict() for tx in self.pending_transactions] + [reward_tx.to_dict()]

        # Apply state changes to recipients upon block inclusion
        for tx_dict in txs_to_mine:
            recipient = tx_dict["recipient"]
            amt = tx_dict["amount"]
            self.set_wallet_balance(recipient, self.wallets.get(recipient, 0.0) + amt)

        new_block = Block(
            index=len(self.chain),
            previous_hash=self.latest_block.hash,
            transactions=txs_to_mine,
            timestamp=time.time()
        )

        # Proof of Work
        while not new_block.hash.startswith(self.target_prefix):
            new_block.nonce += 1
            new_block.hash = new_block.calculate_hash()

        self.chain.append(new_block)
        self.pending_transactions = []

        # Persist block and transactions to PostgreSQL
        try:
            from backend.db import DatabaseService
            DatabaseService.save_block_and_transactions(new_block.to_dict())
        except Exception as e:
            print(f"[Warning] Failed to persist block #{new_block.index} to database: {e}")

        return new_block

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.hash != current.calculate_hash():
                return False
            if current.previous_hash != previous.hash:
                return False
            if not current.hash.startswith(self.target_prefix):
                return False
            if current.merkle_root != compute_merkle_root(current.transactions):
                return False
        return True

    def get_transactions_for_contract(self, contract_id: str) -> List[Dict[str, Any]]:
        results = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("contract_id") == contract_id:
                    tx_copy = dict(tx)
                    tx_copy["block_index"] = block.index
                    tx_copy["block_hash"] = block.hash
                    results.append(tx_copy)
        for tx in self.pending_transactions:
            if tx.contract_id == contract_id:
                tx_copy = tx.to_dict()
                tx_copy["block_index"] = "Pending (Mempool)"
                tx_copy["block_hash"] = "N/A"
                results.append(tx_copy)
        return results
