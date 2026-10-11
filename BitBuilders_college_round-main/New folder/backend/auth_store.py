"""Persistent local credential storage for Fairwork accounts."""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from werkzeug.security import check_password_hash, generate_password_hash


class AuthStore:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or os.environ.get(
            "FAIRWORK_AUTH_STORE",
            str(Path(__file__).with_name("auth_accounts.json"))
        ))
        self._lock = threading.RLock()
        self._accounts = self._read_accounts()

    def _read_accounts(self) -> Dict[str, Dict[str, Any]]:
        try:
            with self.path.open("r", encoding="utf-8") as accounts_file:
                accounts = json.load(accounts_file)
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not load account credentials from {self.path}") from exc
        if not isinstance(accounts, dict):
            raise RuntimeError(f"Invalid account credential data in {self.path}")
        return accounts

    def _save_accounts(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                delete=False
            ) as accounts_file:
                json.dump(self._accounts, accounts_file, indent=2)
                temp_path = accounts_file.name
            os.replace(temp_path, self.path)
        except OSError as exc:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            raise RuntimeError(f"Could not save account credentials to {self.path}") from exc

    @staticmethod
    def normalize_username(username: str) -> str:
        return username.strip().casefold()

    def create_account(
        self,
        username: str,
        password: str,
        account: Dict[str, Any]
    ) -> Dict[str, Any]:
        normalized_username = self.normalize_username(username)
        with self._lock:
            if normalized_username in self._accounts:
                raise ValueError("That username is already in use.")
            record = {
                **account,
                "username": normalized_username,
                "password_hash": generate_password_hash(password)
            }
            self._accounts[normalized_username] = record
            try:
                self._save_accounts()
            except RuntimeError:
                del self._accounts[normalized_username]
                raise
            return dict(record)

    def ensure_account(
        self,
        username: str,
        password: str,
        account: Dict[str, Any]
    ) -> None:
        normalized_username = self.normalize_username(username)
        with self._lock:
            if normalized_username in self._accounts:
                return
            self._accounts[normalized_username] = {
                **account,
                "username": normalized_username,
                "password_hash": generate_password_hash(password)
            }
            self._save_accounts()

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            record = self._accounts.get(self.normalize_username(username))
            if not record or not check_password_hash(record["password_hash"], password):
                return None
            return dict(record)

    def get_accounts(self) -> list[Dict[str, Any]]:
        with self._lock:
            return [dict(account) for account in self._accounts.values()]
