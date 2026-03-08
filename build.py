"""Build LockBox into a standalone .exe using PyInstaller."""

import subprocess
import sys


def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "LockBox",
        "--icon", "lockbox.ico",
        "--add-data", "crypto_utils.py;.",
        "--add-data", "vault.py;.",
        "--add-data", "session.py;.",
        "--add-data", "ui.py;.",
        "--add-data", "lockbox.ico;.",
        "lockbox.py",
    ]

    print("Building LockBox...")
    print(f"Command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print("\nBuild complete! Find LockBox.exe in the dist/ folder.")


if __name__ == "__main__":
    main()
