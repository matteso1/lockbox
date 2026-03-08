<p align="center">
  <img src="lockbox.png" alt="LockBox" width="128" height="128">
</p>

<h1 align="center">LockBox</h1>

<p align="center">
  <strong>Offline, local-first password manager.</strong><br>
  No cloud. No subscriptions. Just your passwords, encrypted on your machine.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/encryption-AES--256--GCM-blue">
  <img src="https://img.shields.io/badge/key%20derivation-Argon2id-blue">
  <img src="https://img.shields.io/badge/2FA-TOTP-green">
  <img src="https://img.shields.io/badge/platform-Windows-lightgrey">
  <img src="https://img.shields.io/badge/license-MIT-yellow">
</p>

---

## Why LockBox?

- **Fully offline** -- your passwords never leave your machine
- **No accounts, no cloud sync, no telemetry** -- zero trust required
- **AES-256-GCM** encryption with **Argon2id** key derivation (64MB memory cost, 3 iterations)
- **TOTP 2FA** support via Duo Mobile, Google Authenticator, or any TOTP app
- **Compiles to a single `.exe`** -- no install, no dependencies at runtime
- **Free and open source** forever

## Features

- Encrypted vault stored locally (`~/.lockbox/vault.lockbox`)
- Cryptographically secure password and passphrase generator
- TOTP two-factor authentication with QR code setup
- 30-day "remember me" quick unlock (2FA code only)
- CSV / key-value / delimited import from existing password files
- Category-based organization with color coding
- Clipboard auto-clear (30 seconds)
- Auto-lock after 5 minutes of inactivity
- Tokyo Night-inspired dark theme
- 3D spinning ASCII logo on the login screen

## Screenshot

<p align="center">
  <em>(run it to see for yourself)</em>
</p>

## Getting Started

### Run from source

```bash
git clone https://github.com/matteso1/lockbox.git
cd lockbox
pip install -r requirements.txt
python lockbox.py
```

### Build standalone `.exe`

```bash
pip install -r requirements.txt
python build.py
```

The compiled binary will be in `dist/LockBox.exe`. Your vault data is stored separately in `~/.lockbox/` -- the exe contains no passwords.

## Vault Format

```
[LOCKBOX1 magic (8 bytes)]
[version (2 bytes)]
[salt (16 bytes)]
[AES-256-GCM encrypted JSON blob]
```

The JSON blob contains all entries and metadata. The encryption key is derived from your master password using Argon2id with:
- **Memory cost:** 64 MB
- **Time cost:** 3 iterations
- **Parallelism:** 4 threads
- **Salt:** 16 random bytes (unique per vault)

## Security Model

- Passwords are encrypted at rest with AES-256-GCM (authenticated encryption)
- Key derivation uses Argon2id, the winner of the Password Hashing Competition, tuned to resist GPU/ASIC attacks
- TOTP secrets are stored inside the encrypted vault (not in plaintext)
- Session files for quick unlock are encrypted with a random 32-byte key and expire after 30 days
- Session files are overwritten with random bytes before deletion
- Atomic writes (write to `.tmp`, then rename) prevent vault corruption on crash
- No network calls, no analytics, no update checks -- fully air-gapped

## Project Structure

```
lockbox.py        # Entry point
crypto_utils.py   # AES-256-GCM, Argon2id, password generation
vault.py          # Encrypted vault data model
session.py        # Quick unlock session management
ui.py             # PyQt6 GUI
build.py          # PyInstaller build script
gen_icon.py       # Icon generator
```

## Requirements

- Python 3.10+
- PyQt6
- cryptography
- argon2-cffi
- pyotp
- qrcode[pil]

## License

MIT
