"""Session management for LockBox.

When 2FA is enabled, the master password can be cached locally
so the user only needs to enter their TOTP code to unlock.

On Windows, the session key is protected with DPAPI (bound to the
current Windows user account). On other platforms, the session key
is stored alongside the encrypted password (weaker -- documented
as a known limitation).
"""

import os
import json
import sys
import time
from pathlib import Path
from typing import Optional

from crypto_utils import encrypt, decrypt


# Session key is random per-save
_SESSION_KEY_LEN = 32

# Session expires after 30 days (in seconds)
SESSION_MAX_AGE = 30 * 24 * 60 * 60


def _dpapi_protect(data: bytes) -> bytes:
    """Encrypt data using Windows DPAPI (current user scope)."""
    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    input_blob = DATA_BLOB(len(data), ctypes.create_string_buffer(data, len(data)))
    output_blob = DATA_BLOB()

    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        None,   # description
        None,   # optional entropy
        None,   # reserved
        None,   # prompt struct
        0,      # flags
        ctypes.byref(output_blob),
    ):
        raise OSError("DPAPI CryptProtectData failed")

    protected = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    ctypes.windll.kernel32.LocalFree(output_blob.pbData)
    return protected


def _dpapi_unprotect(data: bytes) -> bytes:
    """Decrypt data using Windows DPAPI (current user scope)."""
    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    input_blob = DATA_BLOB(len(data), ctypes.create_string_buffer(data, len(data)))
    output_blob = DATA_BLOB()

    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,   # description out
        None,   # optional entropy
        None,   # reserved
        None,   # prompt struct
        0,      # flags
        ctypes.byref(output_blob),
    ):
        raise OSError("DPAPI CryptUnprotectData failed")

    plaintext = ctypes.string_at(output_blob.pbData, output_blob.cbData)
    ctypes.windll.kernel32.LocalFree(output_blob.pbData)
    return plaintext


_HAS_DPAPI = sys.platform == "win32"


def get_session_path(vault_path: str) -> Path:
    """Get the session file path for a vault."""
    return Path(vault_path).with_suffix(".session")


def save_session(vault_path: str, master_password: str) -> None:
    """Save the master password encrypted with a random session key.
    On Windows, the session key is further protected with DPAPI."""
    session_key = os.urandom(_SESSION_KEY_LEN)
    encrypted_pw = encrypt(master_password.encode("utf-8"), session_key)

    # Protect the session key with DPAPI if available
    if _HAS_DPAPI:
        try:
            protected_key = _dpapi_protect(session_key).hex()
            key_method = "dpapi"
        except OSError:
            protected_key = session_key.hex()
            key_method = "raw"
    else:
        protected_key = session_key.hex()
        key_method = "raw"

    data = {
        "key": protected_key,
        "pw": encrypted_pw.hex(),
        "method": key_method,
        "created_at": time.time(),
    }

    session_path = get_session_path(vault_path)
    session_path.write_text(json.dumps(data), encoding="utf-8")

    # Set restrictive file permissions
    try:
        os.chmod(session_path, 0o600)
    except OSError:
        pass


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

        # Recover session key
        key_method = data.get("method", "raw")
        raw_key_bytes = bytes.fromhex(data["key"])

        if key_method == "dpapi" and _HAS_DPAPI:
            session_key = _dpapi_unprotect(raw_key_bytes)
        elif key_method == "dpapi" and not _HAS_DPAPI:
            # DPAPI session on non-Windows -- can't decrypt
            clear_session(vault_path)
            return None
        else:
            session_key = raw_key_bytes

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
        try:
            session_path.write_bytes(os.urandom(256))
            session_path.unlink()
        except OSError:
            pass


def has_session(vault_path: str) -> bool:
    """Check if a session file exists."""
    return get_session_path(vault_path).exists()
