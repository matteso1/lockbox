"""Session management for LockBox.

When 2FA is enabled, the master password can be cached locally
so the user only needs to enter their TOTP code to unlock.
The cached password is encrypted with a random session key stored
in a file that's deleted on lock/exit.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional

from crypto_utils import encrypt, decrypt


# Session key is random per-save, stored in the session file
_SESSION_KEY_LEN = 32

# Session expires after 30 days (in seconds)
SESSION_MAX_AGE = 30 * 24 * 60 * 60


def get_session_path(vault_path: str) -> Path:
    """Get the session file path for a vault."""
    return Path(vault_path).with_suffix(".session")


def save_session(vault_path: str, master_password: str) -> None:
    """Save the master password encrypted with a random session key."""
    session_key = os.urandom(_SESSION_KEY_LEN)
    encrypted_pw = encrypt(master_password.encode("utf-8"), session_key)

    data = {
        "key": session_key.hex(),
        "pw": encrypted_pw.hex(),
        "created_at": time.time(),
    }

    session_path = get_session_path(vault_path)
    session_path.write_text(json.dumps(data), encoding="utf-8")


def load_session(vault_path: str) -> Optional[str]:
    """Load a cached master password from the session file.
    Returns None if no session exists, it's expired, or invalid."""
    session_path = get_session_path(vault_path)
    if not session_path.exists():
        return None

    try:
        data = json.loads(session_path.read_text(encoding="utf-8"))

        # Check expiry (30 days)
        created_at = data.get("created_at", 0)
        if time.time() - created_at > SESSION_MAX_AGE:
            clear_session(vault_path)
            return None

        session_key = bytes.fromhex(data["key"])
        encrypted_pw = bytes.fromhex(data["pw"])
        password = decrypt(encrypted_pw, session_key).decode("utf-8")
        return password
    except Exception:
        # Corrupted or tampered session file
        clear_session(vault_path)
        return None


def clear_session(vault_path: str) -> None:
    """Delete the session file."""
    session_path = get_session_path(vault_path)
    if session_path.exists():
        # Overwrite before deleting
        try:
            session_path.write_bytes(os.urandom(256))
            session_path.unlink()
        except OSError:
            pass


def has_session(vault_path: str) -> bool:
    """Check if a session file exists."""
    return get_session_path(vault_path).exists()
