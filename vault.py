"""Vault data model and encrypted storage for LockBox.

The vault is stored as a single encrypted file:
  [salt (16 bytes)] [encrypted JSON blob]

The JSON blob contains all entries and metadata.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from crypto_utils import derive_key, encrypt, decrypt, generate_salt


VAULT_MAGIC = b"LOCKBOX1"  # File identifier
VAULT_VERSION = 1


@dataclass
class VaultEntry:
    """A single password/secret entry."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    username: str = ""
    password: str = ""
    url: str = ""
    notes: str = ""
    category: str = "General"
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VaultEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class Vault:
    """Encrypted password vault."""

    def __init__(self):
        self.entries: list[VaultEntry] = []
        self.categories: list[str] = ["General", "Email", "Social", "Finance", "API Keys", "Work", "Other"]
        self.totp_secret: Optional[str] = None  # TOTP secret stored encrypted in vault
        self._key: Optional[bytes] = None
        self._salt: Optional[bytes] = None
        self._file_path: Optional[Path] = None
        self._dirty: bool = False

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def create(self, file_path: str, master_password: str) -> None:
        """Create a new empty vault."""
        self._file_path = Path(file_path)
        self._salt = generate_salt()
        self._key = derive_key(master_password, self._salt)
        self.entries = []
        self._dirty = True
        self.save()

    def open(self, file_path: str, master_password: str) -> None:
        """Open and decrypt an existing vault.

        Raises:
            FileNotFoundError: If vault file doesn't exist.
            ValueError: If the master password is wrong or file is corrupted.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Vault file not found: {file_path}")

        raw = path.read_bytes()

        # Validate magic bytes
        if not raw.startswith(VAULT_MAGIC):
            raise ValueError("Not a valid LockBox vault file.")

        offset = len(VAULT_MAGIC)

        # Read version
        version = int.from_bytes(raw[offset : offset + 2], "big")
        if version != VAULT_VERSION:
            raise ValueError(f"Unsupported vault version: {version}")
        offset += 2

        # Read salt
        salt = raw[offset : offset + 16]
        offset += 16

        # Derive key and decrypt
        key = derive_key(master_password, salt)

        try:
            plaintext = decrypt(raw[offset:], key)
        except Exception:
            raise ValueError("Wrong master password or corrupted vault.")

        # Parse JSON
        data = json.loads(plaintext.decode("utf-8"))

        self._file_path = path
        self._salt = salt
        self._key = key
        self.entries = [VaultEntry.from_dict(e) for e in data.get("entries", [])]
        self.categories = data.get("categories", self.categories)
        self.totp_secret = data.get("totp_secret", None)
        self._dirty = False

    def save(self) -> None:
        """Encrypt and save the vault to disk."""
        if not self.is_unlocked or self._file_path is None:
            raise RuntimeError("Vault is not open.")

        data = {
            "entries": [e.to_dict() for e in self.entries],
            "categories": self.categories,
            "totp_secret": self.totp_secret,
        }

        plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
        ciphertext = encrypt(plaintext, self._key)

        # Build file: magic + version + salt + ciphertext
        blob = VAULT_MAGIC
        blob += VAULT_VERSION.to_bytes(2, "big")
        blob += self._salt
        blob += ciphertext

        # Atomic write: write to temp file, then rename
        tmp_path = self._file_path.with_suffix(".tmp")
        tmp_path.write_bytes(blob)
        tmp_path.replace(self._file_path)

        self._dirty = False

    def lock(self) -> None:
        """Lock the vault, clearing sensitive data from memory."""
        self._key = None
        self.entries = []
        self._dirty = False

    def add_entry(self, entry: VaultEntry) -> None:
        """Add a new entry to the vault."""
        self.entries.append(entry)
        self._dirty = True

    def update_entry(self, entry_id: str, **kwargs) -> Optional[VaultEntry]:
        """Update an existing entry by ID."""
        for entry in self.entries:
            if entry.id == entry_id:
                for key, value in kwargs.items():
                    if hasattr(entry, key):
                        setattr(entry, key, value)
                entry.modified_at = time.time()
                self._dirty = True
                return entry
        return None

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry by ID."""
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                self._dirty = True
                return True
        return False

    def search(self, query: str, category: Optional[str] = None) -> list[VaultEntry]:
        """Search entries by name, username, URL, or notes."""
        query = query.lower()
        results = []
        for entry in self.entries:
            if category and entry.category != category:
                continue
            if (
                query in entry.name.lower()
                or query in entry.username.lower()
                or query in entry.url.lower()
                or query in entry.notes.lower()
            ):
                results.append(entry)
        return results

    def get_entries_by_category(self, category: str) -> list[VaultEntry]:
        """Get all entries in a category."""
        return [e for e in self.entries if e.category == category]

    def add_category(self, category: str) -> None:
        """Add a custom category."""
        if category not in self.categories:
            self.categories.append(category)
            self._dirty = True

    def change_master_password(self, new_password: str) -> None:
        """Change the master password (re-encrypts with new key)."""
        if not self.is_unlocked:
            raise RuntimeError("Vault must be unlocked to change password.")
        self._salt = generate_salt()
        self._key = derive_key(new_password, self._salt)
        self._dirty = True
        self.save()

    @property
    def has_totp(self) -> bool:
        """Check if TOTP 2FA is enabled."""
        return self.totp_secret is not None

    def enable_totp(self) -> str:
        """Enable TOTP 2FA. Returns the secret for QR code generation."""
        import pyotp
        self.totp_secret = pyotp.random_base32()
        self._dirty = True
        self.save()
        return self.totp_secret

    def disable_totp(self) -> None:
        """Disable TOTP 2FA."""
        self.totp_secret = None
        self._dirty = True
        self.save()

    def verify_totp(self, code: str) -> bool:
        """Verify a TOTP code. Returns True if valid."""
        if not self.totp_secret:
            return True  # No 2FA enabled, always pass
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(code, valid_window=1)

    def get_totp_uri(self) -> str:
        """Get the otpauth:// URI for QR code generation."""
        if not self.totp_secret:
            return ""
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        return totp.provisioning_uri(name="LockBox", issuer_name="LockBox Vault")

    def import_entries(self, entries: list[VaultEntry]) -> int:
        """Import a list of entries into the vault. Returns count of imported entries."""
        count = 0
        for entry in entries:
            entry.id = uuid.uuid4().hex[:12]
            entry.created_at = time.time()
            entry.modified_at = time.time()
            self.entries.append(entry)
            count += 1
        self._dirty = True
        return count
