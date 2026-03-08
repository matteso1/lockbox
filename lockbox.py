#!/usr/bin/env python3
"""LockBox - Local Password Manager"""

import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui import LockBoxApp


def _icon_path() -> str:
    """Resolve the icon path whether running from source or bundled exe."""
    if getattr(sys, "_MEIPASS", None):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return str(base / "lockbox.ico")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LockBox")
    app.setStyle("Fusion")
    icon = QIcon(_icon_path())
    app.setWindowIcon(icon)
    window = LockBoxApp()
    window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
