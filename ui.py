"""LockBox PyQt6 GUI - Retro terminal password manager interface."""

import os
import sys
import time
import csv
import io
import math
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QAction, QClipboard, QFont, QIcon, QPalette, QColor, QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from vault import Vault, VaultEntry
from crypto_utils import generate_password, generate_passphrase
from session import save_session, load_session, clear_session, has_session

try:
    import pyotp
    import qrcode
    import qrcode.image.pil
    HAS_TOTP = True
except ImportError:
    HAS_TOTP = False


# --- Paths ---

def get_default_vault_path() -> str:
    """Get the default vault file path in user's home directory."""
    lockbox_dir = Path.home() / ".lockbox"
    lockbox_dir.mkdir(exist_ok=True)
    return str(lockbox_dir / "vault.lockbox")


def style_combobox(combo: QComboBox) -> None:
    """Apply highlight palette to a QComboBox popup (stylesheet alone is unreliable on Windows)."""
    view = combo.view()
    palette = view.palette()
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#7aa2f7"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1a1b26"))
    view.setPalette(palette)


# --- 3D Spinning ASCII Logo ---

# The text "LOCKBOX" rendered as a flat 3D block that rotates around the Y axis.
# We pre-compute all frames so each is exactly the same bounding box.

_LOGO_LETTERS = {
    "L": [
        "█░░░░",
        "█░░░░",
        "█░░░░",
        "█░░░░",
        "█████",
    ],
    "O": [
        "░███░",
        "█░░░█",
        "█░░░█",
        "█░░░█",
        "░███░",
    ],
    "C": [
        "░████",
        "█░░░░",
        "█░░░░",
        "█░░░░",
        "░████",
    ],
    "K": [
        "█░░█░",
        "█░█░░",
        "██░░░",
        "█░█░░",
        "█░░█░",
    ],
    "B": [
        "████░",
        "█░░░█",
        "████░",
        "█░░░█",
        "████░",
    ],
    "X": [
        "█░░░█",
        "░█░█░",
        "░░█░░",
        "░█░█░",
        "█░░░█",
    ],
}

# Frame dimensions (fixed)
_FRAME_W = 52
_FRAME_H = 13


def _render_logo_frame(angle_deg: float) -> str:
    """Render one frame of the spinning LOCKBOX logo.

    The logo is treated as a flat plane rotating around the Y axis.
    We simulate perspective by compressing the X axis based on cos(angle).
    The 'depth' shading changes characters based on which face is visible.
    """
    import math

    rad = math.radians(angle_deg % 360)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Build the flat text "LOCKBOX" from letter bitmaps
    word = "LOCKBOX"
    spacing = 1
    flat_rows = [""] * 5
    for i, ch in enumerate(word):
        letter = _LOGO_LETTERS[ch]
        for r in range(5):
            if i > 0:
                flat_rows[r] += "░" * spacing
            flat_rows[r] += letter[r]

    src_width = len(flat_rows[0])

    # Determine if we're seeing the front or back
    front_visible = cos_a >= 0
    # Apparent width scales with |cos(angle)|
    scale = abs(cos_a)

    if scale < 0.05:
        # Edge-on: show a thin line
        lines = []
        lines.append("  " + "║" * 1)
        for _ in range(5):
            lines.append("  " + "║" * 1)
        lines.append("  " + "║" * 1)
    else:
        apparent_w = max(3, int(src_width * scale))

        # Choose characters based on which face
        if front_visible:
            ch_fill = "█"
            ch_empty = " "
        else:
            # Back face -- dimmer characters, reversed
            ch_fill = "▓"
            ch_empty = " "

        # Depth shading: add a slight 3D effect with edge highlight
        thickness = max(1, int(3 * abs(sin_a)))

        lines = []
        # Top edge with 3D thickness
        if sin_a > 0.1:
            offset_3d = "░" * thickness
            top_bar = "▄" * apparent_w
            lines.append(offset_3d + top_bar)
        elif sin_a < -0.1:
            top_bar = "▄" * apparent_w
            lines.append(top_bar)
        else:
            lines.append("▄" * apparent_w)

        for r in range(5):
            row_out = ""
            for col in range(apparent_w):
                # Map back to source column
                src_col = int(col * src_width / apparent_w)
                if not front_visible:
                    src_col = src_width - 1 - src_col
                src_col = min(src_col, src_width - 1)

                if flat_rows[r][src_col] == "█":
                    row_out += ch_fill
                else:
                    row_out += ch_empty

            # Add side edge for 3D effect
            if sin_a > 0.1:
                side = "░" * thickness
                row_out = side + row_out
            elif sin_a < -0.1:
                row_out = row_out + "░" * thickness

            lines.append(row_out)

        # Bottom edge
        if sin_a > 0.1:
            offset_3d = "░" * thickness
            lines.append(offset_3d + "▀" * apparent_w)
        elif sin_a < -0.1:
            lines.append("▀" * apparent_w + "░" * thickness)
        else:
            lines.append("▀" * apparent_w)

    # Pad all lines to fixed width & center them
    padded = []
    for line in lines:
        if len(line) > _FRAME_W - 4:
            line = line[:_FRAME_W - 4]
        total_pad = (_FRAME_W - 4) - len(line)
        left_pad = total_pad // 2
        right_pad = total_pad - left_pad
        padded.append("║ " + " " * left_pad + line + " " * right_pad + " ║")

    # Build fixed-size frame
    border_top = "╔" + "═" * (_FRAME_W - 2) + "╗"
    border_bot = "╚" + "═" * (_FRAME_W - 2) + "╝"
    empty_row = "║" + " " * (_FRAME_W - 2) + "║"

    # Subtitle line
    sub_text = "LOCAL PASSWORD MANAGER"
    sub_pad_l = (_FRAME_W - 2 - len(sub_text)) // 2
    sub_pad_r = (_FRAME_W - 2 - len(sub_text)) - sub_pad_l
    subtitle_row = "║" + " " * sub_pad_l + sub_text + " " * sub_pad_r + "║"

    # Feature line
    feat_text = "AES-256  //  ARGON2ID  //  OFFLINE  //  2FA"
    feat_pad_l = (_FRAME_W - 2 - len(feat_text)) // 2
    feat_pad_r = (_FRAME_W - 2 - len(feat_text)) - feat_pad_l
    feature_row = "║" + " " * feat_pad_l + feat_text + " " * feat_pad_r + "║"

    # Assemble frame to exactly _FRAME_H lines
    frame_lines = [border_top, empty_row]
    frame_lines.extend(padded)

    # Fill to target height minus 4 (top border, bottom border, subtitle, feature)
    while len(frame_lines) < _FRAME_H - 4:
        frame_lines.append(empty_row)

    frame_lines.append(empty_row)
    frame_lines.append(subtitle_row)
    frame_lines.append(feature_row)
    frame_lines.append(border_bot)

    # Trim or pad to exactly _FRAME_H
    while len(frame_lines) < _FRAME_H:
        frame_lines.insert(-1, empty_row)
    frame_lines = frame_lines[:_FRAME_H]

    return "\n".join(frame_lines)


def generate_all_frames(num_frames: int = 60) -> list[str]:
    """Pre-generate all rotation frames."""
    frames = []
    for i in range(num_frames):
        angle = (360.0 / num_frames) * i
        frames.append(_render_logo_frame(angle))
    return frames


# --- Retro Terminal Theme ---

# LazyVim / btop inspired palette
# bg:        #1a1b26 (dark navy)
# bg_dark:   #16161e
# bg_light:  #24283b
# fg:        #c0caf5 (soft blue-white)
# fg_dim:    #565f89
# blue:      #7aa2f7
# cyan:      #7dcfff
# green:     #9ece6a
# magenta:   #bb9af7
# orange:    #ff9e64
# red:       #f7768e
# yellow:    #e0af68
# teal:      #73daca
# border:    #3b4261

# Category colors
CATEGORY_COLORS = {
    "General":  "#c0caf5",  # fg default
    "Email":    "#7dcfff",  # cyan
    "Social":   "#bb9af7",  # magenta
    "Finance":  "#e0af68",  # yellow
    "API Keys": "#ff9e64",  # orange
    "Work":     "#9ece6a",  # green
    "Other":    "#73daca",  # teal
}

TERMINAL_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #1a1b26;
    color: #c0caf5;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
}

QMenuBar {
    background-color: #16161e;
    color: #c0caf5;
    border-bottom: 1px solid #3b4261;
    padding: 2px;
    font-family: 'Consolas', 'Courier New', monospace;
}

QMenuBar::item:selected {
    background-color: #24283b;
}

QMenu {
    background-color: #16161e;
    color: #c0caf5;
    border: 1px solid #3b4261;
}

QMenu::item:selected {
    background-color: #24283b;
}

QToolBar {
    background-color: #16161e;
    border-bottom: 1px solid #3b4261;
    spacing: 4px;
    padding: 6px 4px 8px 4px;
}

QPushButton {
    background-color: #24283b;
    color: #7aa2f7;
    border: 1px solid #3b4261;
    border-radius: 4px;
    padding: 6px 16px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-weight: bold;
    min-height: 24px;
}

QPushButton:hover {
    background-color: #2f3549;
    color: #89b4fa;
    border-color: #7aa2f7;
}

QPushButton:pressed {
    background-color: #1a1b26;
}

QPushButton:disabled {
    background-color: #1a1b26;
    color: #3b4261;
    border-color: #24283b;
}

QPushButton#dangerBtn {
    color: #f7768e;
    border-color: #3b4261;
    background-color: #24283b;
}

QPushButton#dangerBtn:hover {
    background-color: #2d202a;
    border-color: #f7768e;
}

QPushButton#accentBtn {
    color: #9ece6a;
    border-color: #3b4261;
    background-color: #24283b;
}

QPushButton#accentBtn:hover {
    background-color: #252d35;
    border-color: #9ece6a;
}

QPushButton#secondaryBtn {
    color: #bb9af7;
    border-color: #3b4261;
    background-color: #24283b;
}

QPushButton#secondaryBtn:hover {
    background-color: #2a2540;
    border-color: #bb9af7;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {
    background-color: #16161e;
    color: #c0caf5;
    border: 1px solid #3b4261;
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: #283457;
    selection-color: #c0caf5;
    font-family: 'Consolas', 'Courier New', monospace;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {
    border-color: #7aa2f7;
}

QLineEdit[readOnly="true"] {
    background-color: #1a1b26;
    border-color: #3b4261;
    color: #565f89;
}

QComboBox {
    background-color: #16161e;
    color: #c0caf5;
    border: 1px solid #3b4261;
    border-radius: 4px;
    padding: 6px 8px;
    font-family: 'Consolas', 'Courier New', monospace;
}

QComboBox:focus {
    border-color: #7aa2f7;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #16161e;
    color: #c0caf5;
    border: 1px solid #7aa2f7;
    selection-background-color: #7aa2f7;
    selection-color: #1a1b26;
    outline: none;
    padding: 4px 0px;
}

QTableWidget {
    background-color: #1a1b26;
    color: #c0caf5;
    border: 1px solid #3b4261;
    gridline-color: #24283b;
    selection-background-color: #283457;
    selection-color: #c0caf5;
    alternate-background-color: #16161e;
    font-family: 'Consolas', 'Courier New', monospace;
}

QTableWidget::item {
    padding: 6px;
    border-bottom: 1px solid #1e2030;
}

QTableWidget::item:selected {
    background-color: #283457;
}

QHeaderView::section {
    background-color: #16161e;
    color: #565f89;
    border: none;
    border-right: 1px solid #24283b;
    border-bottom: 1px solid #3b4261;
    padding: 6px 8px;
    font-weight: bold;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}

QTabWidget::pane {
    border: 1px solid #3b4261;
    background-color: #1a1b26;
}

QTabBar::tab {
    background-color: #16161e;
    color: #565f89;
    border: 1px solid #3b4261;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-radius: 4px 4px 0 0;
    font-family: 'Consolas', 'Courier New', monospace;
}

QTabBar::tab:selected {
    background-color: #24283b;
    color: #7aa2f7;
    border-color: #7aa2f7;
    border-bottom: none;
}

QGroupBox {
    border: 1px solid #3b4261;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: #565f89;
    font-family: 'Consolas', 'Courier New', monospace;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}

QStatusBar {
    background-color: #16161e;
    color: #565f89;
    border-top: 1px solid #3b4261;
    font-family: 'Consolas', 'Courier New', monospace;
}

QSlider::groove:horizontal {
    border: 1px solid #3b4261;
    height: 6px;
    background-color: #16161e;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #7aa2f7;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    border: none;
}

QSlider::sub-page:horizontal {
    background-color: #3b4261;
    border-radius: 3px;
}

QCheckBox {
    spacing: 8px;
    color: #c0caf5;
    font-family: 'Consolas', 'Courier New', monospace;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 2px solid #3b4261;
    background-color: #16161e;
}

QCheckBox::indicator:checked {
    background-color: #7aa2f7;
    border-color: #7aa2f7;
    image: none;
}

QCheckBox::indicator:unchecked {
    background-color: #16161e;
    border-color: #3b4261;
}

QCheckBox::indicator:hover {
    border-color: #7aa2f7;
}

QLabel#titleLabel {
    font-size: 14px;
    font-weight: bold;
    color: #c0caf5;
    font-family: 'Consolas', 'Courier New', monospace;
}

QLabel#subtitleLabel {
    font-size: 12px;
    color: #565f89;
    font-family: 'Consolas', 'Courier New', monospace;
}

QLabel#sectionLabel {
    font-size: 12px;
    font-weight: bold;
    color: #7aa2f7;
    font-family: 'Consolas', 'Courier New', monospace;
}

QLabel#asciiArt {
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    color: #7aa2f7;
    background-color: transparent;
}

QSplitter::handle {
    background-color: #3b4261;
    width: 1px;
}

QScrollBar:vertical {
    background-color: #1a1b26;
    width: 8px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #3b4261;
    min-height: 30px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background-color: #565f89;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1a1b26;
    height: 8px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #3b4261;
    min-width: 30px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #565f89;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}
"""


# --- Login Screen ---

class LoginWidget(QWidget):
    """Master password login / vault creation screen."""

    # Pause at front-facing (frame 0) for ~4 seconds, spin through everything else
    PAUSE_FRAME = 0        # Which frame to pause on (0 = front-facing "LOCKBOX")
    PAUSE_TICKS = 60       # How many ticks to pause (~4 seconds at 66ms)
    SPIN_INTERVAL = 66     # ms per tick (~15 FPS)

    def __init__(self, on_unlock, parent=None):
        super().__init__(parent)
        self.on_unlock = on_unlock
        self._frame_index = 0
        self._pause_counter = self.PAUSE_TICKS  # Start paused on the logo
        self._frames = generate_all_frames(72)  # 72 frames = 5 degrees per step
        self._setup_ui()

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._next_frame)
        self._anim_timer.start(self.SPIN_INTERVAL)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

        # Spinning ASCII logo
        self.ascii_label = QLabel(self._frames[0])
        self.ascii_label.setObjectName("asciiArt")
        self.ascii_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ascii_label.setFont(QFont("Consolas", 11))
        self.ascii_label.setFixedHeight(220)  # Fixed height prevents bouncing
        layout.addWidget(self.ascii_label)

        layout.addSpacing(10)

        # Form container
        form_container = QWidget()
        form_container.setMaximumWidth(500)
        form_layout = QVBoxLayout(form_container)

        # Terminal-style prompt
        prompt_label = QLabel("> VAULT LOCATION:")
        prompt_label.setStyleSheet("color: #565f89; font-weight: bold;")
        form_layout.addWidget(prompt_label)

        # Vault file
        file_layout = QHBoxLayout()
        self.vault_path_edit = QLineEdit(get_default_vault_path())
        self.vault_path_edit.setPlaceholderText("path/to/vault.lockbox")
        self.vault_path_edit.textChanged.connect(self._update_ui_state)
        file_layout.addWidget(self.vault_path_edit)

        browse_btn = QPushButton("[BROWSE]")
        browse_btn.setMaximumWidth(100)
        browse_btn.clicked.connect(self._browse_vault)
        file_layout.addWidget(browse_btn)
        form_layout.addLayout(file_layout)

        form_layout.addSpacing(8)

        pw_prompt = QLabel("> MASTER PASSWORD:")
        pw_prompt.setStyleSheet("color: #565f89; font-weight: bold;")
        form_layout.addWidget(pw_prompt)

        # Master password
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("enter master password...")
        self.password_edit.returnPressed.connect(self._do_action)
        form_layout.addWidget(self.password_edit)

        # Confirm password (for new vaults)
        self.confirm_label = QLabel("> CONFIRM PASSWORD:")
        self.confirm_label.setStyleSheet("color: #565f89; font-weight: bold;")
        form_layout.addWidget(self.confirm_label)

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_edit.setPlaceholderText("confirm master password...")
        self.confirm_edit.returnPressed.connect(self._do_action)
        form_layout.addWidget(self.confirm_edit)

        form_layout.addSpacing(12)

        # Buttons
        btn_layout = QHBoxLayout()

        self.quick_unlock_btn = QPushButton("[QUICK UNLOCK - 2FA ONLY]")
        self.quick_unlock_btn.setObjectName("secondaryBtn")
        self.quick_unlock_btn.clicked.connect(self._do_quick_unlock)
        btn_layout.addWidget(self.quick_unlock_btn)

        self.open_btn = QPushButton("[UNLOCK VAULT]")
        self.open_btn.setObjectName("accentBtn")
        self.open_btn.clicked.connect(self._do_unlock)
        btn_layout.addWidget(self.open_btn)

        self.create_btn = QPushButton("[CREATE NEW VAULT]")
        self.create_btn.setObjectName("accentBtn")
        self.create_btn.clicked.connect(self._do_create)
        btn_layout.addWidget(self.create_btn)

        form_layout.addLayout(btn_layout)

        # "or create new" link when a vault already exists
        self.create_new_link = QPushButton("or create a new vault...")
        self.create_new_link.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #565f89; "
            "font-size: 11px; text-decoration: underline; padding: 2px; } "
            "QPushButton:hover { color: #7aa2f7; }"
        )
        self.create_new_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_new_link.clicked.connect(self._switch_to_create_mode)
        form_layout.addWidget(self.create_new_link, alignment=Qt.AlignmentFlag.AlignCenter)

        # "back to existing vault" link when in create mode
        self.back_link = QPushButton("back to existing vault...")
        self.back_link.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #565f89; "
            "font-size: 11px; text-decoration: underline; padding: 2px; } "
            "QPushButton:hover { color: #7aa2f7; }"
        )
        self.back_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_link.clicked.connect(self._switch_to_unlock_mode)
        form_layout.addWidget(self.back_link, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #f7768e; font-weight: bold;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        form_layout.addWidget(self.status_label)

        layout.addWidget(form_container, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

        self._update_ui_state()

    def _next_frame(self):
        # If we're on the pause frame, hold for PAUSE_TICKS before continuing
        if self._frame_index == self.PAUSE_FRAME and self._pause_counter > 0:
            self._pause_counter -= 1
            return

        self._frame_index = (self._frame_index + 1) % len(self._frames)
        self.ascii_label.setText(self._frames[self._frame_index])

        # Reset pause counter when we land back on the pause frame
        if self._frame_index == self.PAUSE_FRAME:
            self._pause_counter = self.PAUSE_TICKS

    def _update_ui_state(self):
        vault_path = self.vault_path_edit.text()
        vault_exists = Path(vault_path).exists()
        self._create_mode = getattr(self, "_create_mode", False)
        session_exists = has_session(vault_path) if vault_exists else False

        show_create = (not vault_exists) or self._create_mode
        self.confirm_edit.setVisible(show_create)
        self.confirm_label.setVisible(show_create)
        self.open_btn.setVisible(not show_create)
        self.create_btn.setVisible(show_create)
        self.create_new_link.setVisible(vault_exists and not self._create_mode)
        self.back_link.setVisible(self._create_mode)

        # Quick unlock: show when session exists (2FA was set up and user previously logged in)
        self.quick_unlock_btn.setVisible(session_exists and not show_create)

    def _switch_to_create_mode(self):
        """Switch to create-new-vault mode even when a vault already exists."""
        self._create_mode = True
        # Clear the path to a new location
        lockbox_dir = Path.home() / ".lockbox"
        i = 2
        new_path = lockbox_dir / f"vault_{i}.lockbox"
        while new_path.exists():
            i += 1
            new_path = lockbox_dir / f"vault_{i}.lockbox"
        self.vault_path_edit.setText(str(new_path))
        self.password_edit.clear()
        self.confirm_edit.clear()
        self.status_label.setText("")
        self._update_ui_state()
        self.password_edit.setFocus()

    def _switch_to_unlock_mode(self):
        """Switch back to unlock-existing-vault mode."""
        self._create_mode = False
        self.vault_path_edit.setText(get_default_vault_path())
        self.password_edit.clear()
        self.confirm_edit.clear()
        self.status_label.setText("")
        self._update_ui_state()
        self.password_edit.setFocus()

    def _browse_vault(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Vault File", "", "LockBox Vault (*.lockbox);;All Files (*)"
        )
        if path:
            self.vault_path_edit.setText(path)
            self._update_ui_state()

    def _do_action(self):
        """Handle Enter key -- unlock or create depending on state."""
        vault_exists = Path(self.vault_path_edit.text()).exists()
        if vault_exists:
            self._do_unlock()
        else:
            self._do_create()

    def _do_unlock(self):
        path = self.vault_path_edit.text().strip()
        password = self.password_edit.text()

        if not path:
            self.status_label.setText("[ERROR] Specify a vault file path.")
            return
        if not password:
            self.status_label.setText("[ERROR] Enter your master password.")
            return

        self.status_label.setText("> DECRYPTING VAULT...")
        self.status_label.setStyleSheet("color: #565f89; font-weight: bold;")
        QApplication.processEvents()

        vault = Vault()
        try:
            vault.open(path, password)
            # Save session for quick unlock if 2FA is enabled
            if vault.has_totp:
                save_session(path, password)
            self.password_edit.clear()
            self.confirm_edit.clear()
            self.status_label.setText("")
            self.on_unlock(vault, path)
        except FileNotFoundError:
            self.status_label.setStyleSheet("color: #f7768e; font-weight: bold;")
            self.status_label.setText("[ERROR] Vault file not found.")
            self._update_ui_state()
        except ValueError as e:
            self.status_label.setStyleSheet("color: #f7768e; font-weight: bold;")
            self.status_label.setText(f"[ERROR] {e}")

    def _do_quick_unlock(self):
        """Quick unlock using saved session + 2FA code only."""
        path = self.vault_path_edit.text().strip()
        if not path:
            return

        password = load_session(path)
        if not password:
            self.status_label.setStyleSheet("color: #f7768e; font-weight: bold;")
            self.status_label.setText("[ERROR] Session expired. Enter master password.")
            self._update_ui_state()
            return

        self.status_label.setText("> DECRYPTING VAULT...")
        self.status_label.setStyleSheet("color: #565f89; font-weight: bold;")
        QApplication.processEvents()

        vault = Vault()
        try:
            vault.open(path, password)
            # Re-save session to keep it fresh
            if vault.has_totp:
                save_session(path, password)
            self.password_edit.clear()
            self.status_label.setText("")
            self.on_unlock(vault, path)
        except (ValueError, FileNotFoundError):
            # Session is stale -- clear it
            clear_session(path)
            self.status_label.setStyleSheet("color: #f7768e; font-weight: bold;")
            self.status_label.setText("[ERROR] Session expired. Enter master password.")
            self._update_ui_state()

    def _do_create(self):
        path = self.vault_path_edit.text().strip()
        password = self.password_edit.text()
        confirm = self.confirm_edit.text()

        if not path:
            self.status_label.setText("[ERROR] Specify a vault file path.")
            return
        if not password:
            self.status_label.setText("[ERROR] Enter a master password.")
            return
        if len(password) < 8:
            self.status_label.setText("[ERROR] Password must be >= 8 characters.")
            return
        if password != confirm:
            self.status_label.setText("[ERROR] Passwords do not match.")
            return

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        self.status_label.setText("> GENERATING VAULT...")
        self.status_label.setStyleSheet("color: #565f89; font-weight: bold;")
        QApplication.processEvents()

        vault = Vault()
        try:
            vault.create(path, password)
            self.password_edit.clear()
            self.confirm_edit.clear()
            self.status_label.setText("")
            self.on_unlock(vault, path)
        except Exception as e:
            self.status_label.setStyleSheet("color: #f7768e; font-weight: bold;")
            self.status_label.setText(f"[ERROR] {e}")

    def refresh_state(self):
        """Called when returning to login screen to re-check vault existence."""
        self._create_mode = False
        self.vault_path_edit.setText(get_default_vault_path())
        self._update_ui_state()
        self.status_label.setText("")
        self.password_edit.setFocus()


# --- Password Generator Dialog ---

class PasswordGeneratorDialog(QDialog):
    """Dialog for generating secure passwords."""

    def __init__(self, parent=None, save_callback=None):
        super().__init__(parent)
        self.save_callback = save_callback
        self.setWindowTitle("// PASSWORD GENERATOR")
        self.setMinimumWidth(520)
        self._setup_ui()
        self._generate()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(">> GENERATE SECURE PASSWORD")
        header.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        layout.addSpacing(8)

        # Generated password display
        self.password_display = QLineEdit()
        self.password_display.setReadOnly(True)
        self.password_display.setFont(QFont("Consolas", 15))
        self.password_display.setMinimumHeight(44)
        self.password_display.setStyleSheet(
            "QLineEdit { background-color: #16161e; color: #9ece6a; font-size: 15px; "
            "letter-spacing: 2px; border: 1px solid #3b4261; padding: 8px; }"
        )
        layout.addWidget(self.password_display)

        # Strength indicator
        self.strength_label = QLabel("")
        self.strength_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.strength_label.setFont(QFont("Consolas", 12))
        layout.addWidget(self.strength_label)

        layout.addSpacing(8)

        # Tabs for password vs passphrase
        tabs = QTabWidget()

        # --- Password tab ---
        pw_tab = QWidget()
        pw_layout = QVBoxLayout(pw_tab)

        # Length slider
        len_layout = QHBoxLayout()
        len_label = QLabel("LENGTH:")
        len_label.setStyleSheet("color: #565f89;")
        len_layout.addWidget(len_label)
        self.length_spin = QSpinBox()
        self.length_spin.setRange(4, 128)
        self.length_spin.setValue(20)
        self.length_spin.valueChanged.connect(self._generate)
        len_layout.addWidget(self.length_spin)

        self.length_slider = QSlider(Qt.Orientation.Horizontal)
        self.length_slider.setRange(4, 128)
        self.length_slider.setValue(20)
        self.length_slider.valueChanged.connect(lambda v: self.length_spin.setValue(v))
        self.length_spin.valueChanged.connect(lambda v: self.length_slider.setValue(v))
        len_layout.addWidget(self.length_slider)
        pw_layout.addLayout(len_layout)

        pw_layout.addSpacing(8)

        # Character options
        charset_label = QLabel("CHARACTER SETS:")
        charset_label.setStyleSheet("color: #565f89;")
        pw_layout.addWidget(charset_label)

        opts_layout = QHBoxLayout()
        opts_layout.setSpacing(20)

        self.upper_check = QCheckBox("[A-Z]")
        self.upper_check.setChecked(True)
        self.upper_check.stateChanged.connect(self._generate)
        opts_layout.addWidget(self.upper_check)

        self.lower_check = QCheckBox("[a-z]")
        self.lower_check.setChecked(True)
        self.lower_check.stateChanged.connect(self._generate)
        opts_layout.addWidget(self.lower_check)

        self.digit_check = QCheckBox("[0-9]")
        self.digit_check.setChecked(True)
        self.digit_check.stateChanged.connect(self._generate)
        opts_layout.addWidget(self.digit_check)

        self.symbol_check = QCheckBox("[!@#$]")
        self.symbol_check.setChecked(True)
        self.symbol_check.stateChanged.connect(self._generate)
        opts_layout.addWidget(self.symbol_check)

        pw_layout.addLayout(opts_layout)

        self.ambiguous_check = QCheckBox("Exclude ambiguous (0/O, 1/l/I)")
        self.ambiguous_check.stateChanged.connect(self._generate)
        pw_layout.addWidget(self.ambiguous_check)

        self.mode = "password"
        tabs.addTab(pw_tab, "PASSWORD")

        # --- Passphrase tab ---
        pp_tab = QWidget()
        pp_layout = QVBoxLayout(pp_tab)

        words_layout = QHBoxLayout()
        words_label = QLabel("WORDS:")
        words_label.setStyleSheet("color: #565f89;")
        words_layout.addWidget(words_label)
        self.words_spin = QSpinBox()
        self.words_spin.setRange(3, 10)
        self.words_spin.setValue(5)
        self.words_spin.valueChanged.connect(self._generate_passphrase)
        words_layout.addWidget(self.words_spin)
        words_layout.addStretch()
        pp_layout.addLayout(words_layout)

        sep_layout = QHBoxLayout()
        sep_label = QLabel("SEPARATOR:")
        sep_label.setStyleSheet("color: #565f89;")
        sep_layout.addWidget(sep_label)
        self.sep_edit = QLineEdit("-")
        self.sep_edit.setMaximumWidth(60)
        self.sep_edit.textChanged.connect(self._generate_passphrase)
        sep_layout.addWidget(self.sep_edit)
        sep_layout.addStretch()
        pp_layout.addLayout(sep_layout)

        pp_layout.addStretch()
        tabs.addTab(pp_tab, "PASSPHRASE")

        tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(tabs)

        layout.addSpacing(10)

        # Buttons
        btn_layout = QHBoxLayout()

        regen_btn = QPushButton("[REGENERATE]")
        regen_btn.clicked.connect(self._generate)
        btn_layout.addWidget(regen_btn)

        copy_btn = QPushButton("[COPY]")
        copy_btn.clicked.connect(self._copy)
        btn_layout.addWidget(copy_btn)

        if self.save_callback:
            save_btn = QPushButton("[USE PASSWORD]")
            save_btn.setObjectName("accentBtn")
            save_btn.clicked.connect(self._use_password)
            btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _on_tab_changed(self, index):
        if index == 0:
            self.mode = "password"
            self._generate()
        else:
            self.mode = "passphrase"
            self._generate_passphrase()

    def _generate(self):
        if hasattr(self, "mode") and self.mode == "passphrase":
            self._generate_passphrase()
            return

        pw = generate_password(
            length=self.length_spin.value(),
            uppercase=self.upper_check.isChecked(),
            lowercase=self.lower_check.isChecked(),
            digits=self.digit_check.isChecked(),
            symbols=self.symbol_check.isChecked(),
            exclude_ambiguous=self.ambiguous_check.isChecked(),
        )
        self.password_display.setText(pw)
        self._update_strength(pw)

    def _generate_passphrase(self):
        pp = generate_passphrase(
            word_count=self.words_spin.value(),
            separator=self.sep_edit.text() or "-",
        )
        self.password_display.setText(pp)
        self._update_strength(pp)

    def _update_strength(self, password: str):
        length = len(password)
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(not c.isalnum() for c in password)

        pool = 0
        if has_upper:
            pool += 26
        if has_lower:
            pool += 26
        if has_digit:
            pool += 10
        if has_symbol:
            pool += 32

        if pool == 0:
            pool = 26

        entropy = length * math.log2(pool)

        if entropy < 40:
            label, color = "[ WEAK ]", "#f7768e"
        elif entropy < 60:
            label, color = "[ FAIR ]", "#e0af68"
        elif entropy < 80:
            label, color = "[ GOOD ]", "#9ece6a"
        elif entropy < 100:
            label, color = "[ STRONG ]", "#73daca"
        else:
            label, color = "[ EXCELLENT ]", "#7dcfff"

        self.strength_label.setText(f"{label}  //  {int(entropy)} bits entropy")
        self.strength_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _copy(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.password_display.text())
        QTimer.singleShot(30000, lambda: clipboard.clear())
        self.strength_label.setText(">> COPIED  //  clipboard clears in 30s")
        self.strength_label.setStyleSheet("color: #7dcfff; font-weight: bold;")

    def _use_password(self):
        if self.save_callback:
            self.save_callback(self.password_display.text())
        self.accept()


# --- Entry Editor Dialog ---

class EntryDialog(QDialog):
    """Dialog for creating/editing a vault entry."""

    def __init__(self, categories: list[str], entry: Optional[VaultEntry] = None, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.categories = categories
        self.setWindowTitle("// EDIT ENTRY" if entry else "// NEW ENTRY")
        self.setMinimumWidth(550)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(">> EDIT ENTRY" if self.entry else ">> NEW ENTRY")
        header.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        layout.addSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Style labels
        def make_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #565f89; font-weight: bold;")
            return lbl

        self.name_edit = QLineEdit(self.entry.name if self.entry else "")
        self.name_edit.setPlaceholderText("GitHub, Gmail, AWS...")
        form.addRow(make_label("NAME:"), self.name_edit)

        self.username_edit = QLineEdit(self.entry.username if self.entry else "")
        self.username_edit.setPlaceholderText("username or email...")
        form.addRow(make_label("USER:"), self.username_edit)

        # Password row with generate button
        pw_widget = QWidget()
        pw_layout = QHBoxLayout(pw_widget)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_layout.setSpacing(4)

        self.password_edit = QLineEdit(self.entry.password if self.entry else "")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("password...")
        pw_layout.addWidget(self.password_edit, stretch=1)

        toggle_btn = QPushButton("SHOW")
        toggle_btn.setFixedWidth(70)
        toggle_btn.clicked.connect(lambda: self._toggle_password(toggle_btn))
        pw_layout.addWidget(toggle_btn)

        gen_btn = QPushButton("GEN")
        gen_btn.setFixedWidth(55)
        gen_btn.setObjectName("accentBtn")
        gen_btn.clicked.connect(self._open_generator)
        pw_layout.addWidget(gen_btn)

        form.addRow(make_label("PASS:"), pw_widget)

        self.url_edit = QLineEdit(self.entry.url if self.entry else "")
        self.url_edit.setPlaceholderText("https://...")
        form.addRow(make_label("URL:"), self.url_edit)

        self.category_combo = QComboBox()
        style_combobox(self.category_combo)
        self.category_combo.addItems(self.categories)
        if self.entry:
            idx = self.category_combo.findText(self.entry.category)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
        form.addRow(make_label("CAT:"), self.category_combo)

        self.notes_edit = QPlainTextEdit(self.entry.notes if self.entry else "")
        self.notes_edit.setPlaceholderText("additional notes...")
        self.notes_edit.setMaximumHeight(80)
        form.addRow(make_label("NOTES:"), self.notes_edit)

        layout.addLayout(form)

        layout.addSpacing(12)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("[SAVE]")
        save_btn.setObjectName("accentBtn")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("[CANCEL]")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _toggle_password(self, btn):
        if self.password_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            btn.setText("HIDE")
        else:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            btn.setText("SHOW")

    def _open_generator(self):
        dlg = PasswordGeneratorDialog(self, save_callback=self._set_generated_password)
        dlg.exec()

    def _set_generated_password(self, password: str):
        self.password_edit.setText(password)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)

    def _save(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "ERROR", "[ERROR] Name is required.")
            return
        self.accept()

    def get_entry_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text(),
            "url": self.url_edit.text().strip(),
            "category": self.category_combo.currentText(),
            "notes": self.notes_edit.toPlainText().strip(),
        }


# --- Import Dialog ---

class ImportDialog(QDialog):
    """Dialog for importing passwords from a plaintext file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("// IMPORT PASSWORDS")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.imported_entries: list[VaultEntry] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(">> IMPORT FROM PLAINTEXT")
        header.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        info = QLabel(
            "Paste passwords below or load from file.\n"
            "Supported formats:\n"
            "  > name | username | password | url\n"
            "  > key=value blocks (separated by blank lines)\n"
            "  > CSV with headers (name, username, password, url, notes)"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #565f89; margin-bottom: 8px;")
        layout.addWidget(info)

        load_btn = QPushButton("[LOAD FROM FILE]")
        load_btn.clicked.connect(self._load_file)
        layout.addWidget(load_btn)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "Paste your passwords here...\n\n"
            "GitHub | myuser | mypassword123 | https://github.com\n"
            "Gmail | me@gmail.com | p@ssw0rd | https://gmail.com"
        )
        self.text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text_edit)

        cat_layout = QHBoxLayout()
        cat_label = QLabel("CATEGORY:")
        cat_label.setStyleSheet("color: #565f89;")
        cat_layout.addWidget(cat_label)
        self.category_combo = QComboBox()
        style_combobox(self.category_combo)
        self.category_combo.addItems(["General", "Email", "Social", "Finance", "API Keys", "Work", "Other"])
        cat_layout.addWidget(self.category_combo)
        cat_layout.addStretch()
        layout.addLayout(cat_layout)

        btn_layout = QHBoxLayout()

        preview_btn = QPushButton("[PREVIEW]")
        preview_btn.clicked.connect(self._preview)
        btn_layout.addWidget(preview_btn)

        import_btn = QPushButton("[IMPORT]")
        import_btn.setObjectName("accentBtn")
        import_btn.clicked.connect(self._do_import)
        btn_layout.addWidget(import_btn)

        cancel_btn = QPushButton("[CANCEL]")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: #565f89;")
        layout.addWidget(self.preview_label)

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Password File", "", "Text Files (*.txt *.csv);;All Files (*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    self.text_edit.setPlainText(f.read())
            except Exception as e:
                QMessageBox.critical(self, "ERROR", f"[ERROR] Failed to read file: {e}")

    def _parse_entries(self) -> list[VaultEntry]:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return []

        category = self.category_combo.currentText()
        entries = []

        # Try CSV first
        try:
            reader = csv.DictReader(io.StringIO(text))
            fields_lower = [f.lower().strip() for f in (reader.fieldnames or [])]
            if any(f in fields_lower for f in ("name", "title", "site", "service")):
                for row in reader:
                    mapped = {k.lower().strip(): v for k, v in row.items()}
                    entry = VaultEntry(
                        name=mapped.get("name") or mapped.get("title") or mapped.get("site") or mapped.get("service") or "",
                        username=mapped.get("username") or mapped.get("user") or mapped.get("email") or mapped.get("login") or "",
                        password=mapped.get("password") or mapped.get("pass") or mapped.get("secret") or "",
                        url=mapped.get("url") or mapped.get("website") or mapped.get("site_url") or "",
                        notes=mapped.get("notes") or mapped.get("note") or mapped.get("comment") or "",
                        category=category,
                    )
                    if entry.name or entry.username or entry.password:
                        entries.append(entry)
                if entries:
                    return entries
        except (csv.Error, StopIteration, KeyError):
            pass

        # Try key=value format
        if "=" in text and "\n\n" in text:
            blocks = text.split("\n\n")
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                data = {}
                for line in block.split("\n"):
                    line = line.strip()
                    if "=" in line:
                        key, _, value = line.partition("=")
                        data[key.strip().lower()] = value.strip()
                if data:
                    entry = VaultEntry(
                        name=data.get("name") or data.get("title") or data.get("site") or "",
                        username=data.get("username") or data.get("user") or data.get("email") or "",
                        password=data.get("password") or data.get("pass") or data.get("secret") or data.get("key") or data.get("api_key") or data.get("apikey") or data.get("token") or "",
                        url=data.get("url") or data.get("website") or "",
                        notes=data.get("notes") or data.get("note") or "",
                        category=category,
                    )
                    if entry.name or entry.username or entry.password:
                        entries.append(entry)
            if entries:
                return entries

        # Try pipe/tab delimited
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---"):
                continue

            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
            elif "\t" in line:
                parts = [p.strip() for p in line.split("\t")]
            elif "," in line and text.count(",") > 2:
                parts = [p.strip().strip('"') for p in line.split(",")]
            else:
                parts = [line]

            entry = VaultEntry(category=category)
            if len(parts) >= 1:
                entry.name = parts[0]
            if len(parts) >= 2:
                entry.username = parts[1]
            if len(parts) >= 3:
                entry.password = parts[2]
            if len(parts) >= 4:
                entry.url = parts[3]
            if len(parts) >= 5:
                entry.notes = parts[4]

            if entry.name or entry.password:
                entries.append(entry)

        return entries

    def _preview(self):
        entries = self._parse_entries()
        if not entries:
            self.preview_label.setText("[ERROR] No entries detected. Check format.")
            self.preview_label.setStyleSheet("color: #f7768e;")
            return

        self.preview_label.setStyleSheet("color: #565f89;")
        lines = [f">> Found {len(entries)} entries:"]
        for i, e in enumerate(entries[:10], 1):
            pw_display = "*" * min(len(e.password), 8) if e.password else "(empty)"
            lines.append(f"  [{i:02d}] {e.name or '(unnamed)'} / {e.username or '(no user)'} / {pw_display}")
        if len(entries) > 10:
            lines.append(f"  ... and {len(entries) - 10} more")

        self.preview_label.setText("\n".join(lines))

    def _do_import(self):
        entries = self._parse_entries()
        if not entries:
            QMessageBox.warning(self, "IMPORT", "[ERROR] No entries detected.")
            return

        confirm = QMessageBox.question(
            self,
            "CONFIRM IMPORT",
            f"Import {len(entries)} entries into the vault?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.imported_entries = entries
            self.accept()


# --- Change Master Password Dialog ---

class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("// CHANGE MASTER PASSWORD")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(">> CHANGE MASTER PASSWORD")
        header.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        layout.addSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)

        def make_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #565f89; font-weight: bold;")
            return lbl

        self.current_edit = QLineEdit()
        self.current_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_edit.setPlaceholderText("current master password...")
        form.addRow(make_label("CURRENT:"), self.current_edit)

        self.new_edit = QLineEdit()
        self.new_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_edit.setPlaceholderText("new password (8+ chars)...")
        form.addRow(make_label("NEW:"), self.new_edit)

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_edit.setPlaceholderText("confirm new password...")
        form.addRow(make_label("CONFIRM:"), self.confirm_edit)

        layout.addLayout(form)

        layout.addSpacing(12)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton("[CHANGE]")
        ok_btn.setObjectName("accentBtn")
        ok_btn.clicked.connect(self._validate)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("[CANCEL]")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _validate(self):
        if not self.current_edit.text():
            QMessageBox.warning(self, "ERROR", "[ERROR] Enter current password.")
            return
        if len(self.new_edit.text()) < 8:
            QMessageBox.warning(self, "ERROR", "[ERROR] New password must be >= 8 characters.")
            return
        if self.new_edit.text() != self.confirm_edit.text():
            QMessageBox.warning(self, "ERROR", "[ERROR] Passwords do not match.")
            return
        self.accept()


# --- TOTP 2FA Dialogs ---

class TOTPVerifyDialog(QDialog):
    """Dialog to enter a 6-digit TOTP code during login."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("// 2FA VERIFICATION")
        self.setMinimumWidth(400)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(">> TWO-FACTOR AUTHENTICATION")
        header.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        layout.addSpacing(8)

        info = QLabel("Enter the 6-digit code from Duo Mobile:")
        info.setStyleSheet("color: #565f89;")
        layout.addWidget(info)

        layout.addSpacing(8)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("000000")
        self.code_edit.setMaxLength(6)
        self.code_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_edit.setFont(QFont("Consolas", 24))
        self.code_edit.setStyleSheet(
            "QLineEdit { background-color: #16161e; color: #7aa2f7; font-size: 24px; "
            "letter-spacing: 8px; border: 1px solid #3b4261; padding: 12px; }"
        )
        self.code_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.code_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f7768e; font-weight: bold;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_label)

        layout.addSpacing(12)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        verify_btn = QPushButton("[VERIFY]")
        verify_btn.setObjectName("accentBtn")
        verify_btn.clicked.connect(self.accept)
        btn_layout.addWidget(verify_btn)

        cancel_btn = QPushButton("[CANCEL]")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def get_code(self) -> str:
        return self.code_edit.text().strip()

    def show_error(self, msg: str):
        self.error_label.setText(msg)
        self.code_edit.clear()
        self.code_edit.setFocus()


class TOTPSetupDialog(QDialog):
    """Dialog to set up TOTP 2FA with QR code."""

    def __init__(self, totp_uri: str, totp_secret: str, parent=None):
        super().__init__(parent)
        self.totp_secret = totp_secret
        self.totp_uri = totp_uri
        self.setWindowTitle("// SETUP 2FA")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(">> SETUP TWO-FACTOR AUTHENTICATION")
        header.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        layout.addSpacing(8)

        # Instructions
        info = QLabel(
            "1. Open Duo Mobile (or any TOTP authenticator app)\n"
            "2. Tap '+' to add a new account\n"
            "3. Scan the QR code below OR enter the secret manually"
        )
        info.setStyleSheet("color: #565f89;")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(12)

        # QR Code -- render as actual image for reliable scanning
        if HAS_TOTP:
            qr = qrcode.QRCode(version=1, box_size=8, border=4)
            qr.add_data(self.totp_uri)
            qr.make(fit=True)

            # Render to PIL image then convert to QPixmap
            pil_img = qr.make_image(fill_color="#c0caf5", back_color="#1a1b26")
            pil_img = pil_img.convert("RGBA")

            # Convert PIL -> QImage -> QPixmap
            data = pil_img.tobytes("raw", "RGBA")
            qimage = QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)

            qr_label = QLabel()
            qr_label.setPixmap(pixmap)
            qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qr_label.setStyleSheet("background-color: #1a1b26; padding: 12px; border: 1px solid #3b4261; border-radius: 4px;")
            layout.addWidget(qr_label, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        # Manual secret
        secret_label = QLabel("> MANUAL SECRET (if you can't scan):")
        secret_label.setStyleSheet("color: #565f89; font-weight: bold;")
        layout.addWidget(secret_label)

        secret_edit = QLineEdit(self.totp_secret)
        secret_edit.setReadOnly(True)
        secret_edit.setFont(QFont("Consolas", 14))
        secret_edit.setStyleSheet(
            "QLineEdit { background-color: #16161e; color: #7dcfff; font-size: 14px; "
            "letter-spacing: 2px; border: 1px solid #3b4261; padding: 8px; }"
        )
        layout.addWidget(secret_edit)

        copy_btn = QPushButton("[COPY SECRET]")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.totp_secret))
        layout.addWidget(copy_btn)

        layout.addSpacing(12)

        # Verify before enabling
        verify_label = QLabel("> ENTER CODE FROM APP TO CONFIRM SETUP:")
        verify_label.setStyleSheet("color: #e0af68; font-weight: bold;")
        layout.addWidget(verify_label)

        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("000000")
        self.code_edit.setMaxLength(6)
        self.code_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_edit.setFont(QFont("Consolas", 20))
        self.code_edit.setStyleSheet(
            "QLineEdit { background-color: #16161e; color: #9ece6a; font-size: 20px; "
            "letter-spacing: 8px; border: 1px solid #3b4261; padding: 8px; }"
        )
        self.code_edit.returnPressed.connect(self._verify)
        layout.addWidget(self.code_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #f7768e; font-weight: bold;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.error_label)

        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        confirm_btn = QPushButton("[CONFIRM SETUP]")
        confirm_btn.setObjectName("accentBtn")
        confirm_btn.clicked.connect(self._verify)
        btn_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton("[CANCEL]")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _verify(self):
        code = self.code_edit.text().strip()
        if len(code) != 6 or not code.isdigit():
            self.error_label.setText("[ERROR] Enter a 6-digit code")
            return

        totp = pyotp.TOTP(self.totp_secret)
        if totp.verify(code, valid_window=1):
            self.accept()
        else:
            self.error_label.setText("[ERROR] Invalid code. Try again.")
            self.code_edit.clear()
            self.code_edit.setFocus()

    def get_code(self) -> str:
        return self.code_edit.text().strip()


# --- Main Application Window ---

class LockBoxApp(QMainWindow):
    """Main application window."""

    CLIPBOARD_CLEAR_MS = 30_000  # 30 seconds
    AUTO_LOCK_MS = 300_000  # 5 minutes

    def __init__(self):
        super().__init__()
        self.vault: Optional[Vault] = None
        self.vault_path: Optional[str] = None
        self._clipboard_timer = QTimer(self)
        self._clipboard_timer.setSingleShot(True)
        self._clipboard_timer.timeout.connect(self._clear_clipboard)
        self._auto_lock_timer = QTimer(self)
        self._auto_lock_timer.setSingleShot(True)
        self._auto_lock_timer.timeout.connect(self._auto_lock)

        self._setup_window()
        self._setup_ui()
        self.setStyleSheet(TERMINAL_STYLESHEET)

    def _setup_window(self):
        self.setWindowTitle("LockBox")
        self.resize(950, 650)
        self.setMinimumSize(750, 500)

    def _setup_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Login screen
        self.login_widget = LoginWidget(on_unlock=self._on_vault_unlocked)
        self.stack.addWidget(self.login_widget)

        # Vault screen
        self.vault_widget = QWidget()
        self._setup_vault_ui()
        self.stack.addWidget(self.vault_widget)

        self.stack.setCurrentIndex(0)

        self._setup_menu()

        # Hide menu bar and status bar on login screen
        self.menuBar().setVisible(False)
        self.statusBar().setVisible(False)

    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("FILE")

        self.save_action = QAction("Save Vault  [Ctrl+S]", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self._save_vault)
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)

        file_menu.addSeparator()

        import_action = QAction("Import from File  [Ctrl+I]", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._import_passwords)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        lock_action = QAction("Lock Vault  [Ctrl+L]", self)
        lock_action.setShortcut("Ctrl+L")
        lock_action.triggered.connect(self._lock_vault)
        file_menu.addAction(lock_action)

        entry_menu = menubar.addMenu("ENTRY")

        add_action = QAction("New Entry  [Ctrl+N]", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(self._add_entry)
        entry_menu.addAction(add_action)

        edit_action = QAction("Edit Entry  [Ctrl+E]", self)
        edit_action.setShortcut("Ctrl+E")
        edit_action.triggered.connect(self._edit_entry)
        entry_menu.addAction(edit_action)

        delete_action = QAction("Delete Entry  [Del]", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self._delete_entry)
        entry_menu.addAction(delete_action)

        tools_menu = menubar.addMenu("TOOLS")

        gen_action = QAction("Password Generator  [Ctrl+G]", self)
        gen_action.setShortcut("Ctrl+G")
        gen_action.triggered.connect(self._open_generator)
        tools_menu.addAction(gen_action)

        tools_menu.addSeparator()

        change_pw_action = QAction("Change Master Password", self)
        change_pw_action.triggered.connect(self._change_master_password)
        tools_menu.addAction(change_pw_action)

        if HAS_TOTP:
            tools_menu.addSeparator()

            setup_2fa_action = QAction("Setup 2FA (TOTP)", self)
            setup_2fa_action.triggered.connect(self._setup_totp)
            tools_menu.addAction(setup_2fa_action)

            disable_2fa_action = QAction("Disable 2FA", self)
            disable_2fa_action.triggered.connect(self._disable_totp)
            tools_menu.addAction(disable_2fa_action)

    def _setup_vault_ui(self):
        layout = QVBoxLayout(self.vault_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #16161e;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 8, 8, 8)

        search_label = QLabel(">")
        search_label.setStyleSheet("color: #7aa2f7; font-weight: bold; font-size: 16px;")
        tb_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("search entries...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.setMinimumHeight(36)
        self.search_edit.textChanged.connect(self._filter_entries)
        tb_layout.addWidget(self.search_edit)

        filter_label = QLabel("FILTER:")
        filter_label.setStyleSheet("color: #565f89; font-weight: bold;")
        tb_layout.addWidget(filter_label)

        self._filter_current = "ALL"
        self.filter_btn = QPushButton("ALL")
        self.filter_btn.setMaximumWidth(150)
        self._filter_menu = QMenu(self)
        self.filter_btn.setMenu(self._filter_menu)
        self._rebuild_filter_menu(["ALL"])
        tb_layout.addWidget(self.filter_btn)

        tb_layout.addStretch()

        add_btn = QPushButton("[+ NEW]")
        add_btn.setObjectName("accentBtn")
        add_btn.clicked.connect(self._add_entry)
        tb_layout.addWidget(add_btn)

        gen_btn = QPushButton("[GEN]")
        gen_btn.clicked.connect(self._open_generator)
        tb_layout.addWidget(gen_btn)

        lock_btn = QPushButton("[LOCK]")
        lock_btn.setObjectName("dangerBtn")
        lock_btn.clicked.connect(self._lock_vault)
        tb_layout.addWidget(lock_btn)

        layout.addWidget(toolbar)

        # Toolbar separator line
        tb_sep = QWidget()
        tb_sep.setFixedHeight(1)
        tb_sep.setStyleSheet("background-color: #3b4261;")
        layout.addWidget(tb_sep)

        # Entry table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["NAME", "USERNAME", "PASSWORD", "URL", "CATEGORY"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.doubleClicked.connect(self._edit_entry)
        layout.addWidget(self.table)

        # Entry count
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #565f89; padding: 4px 8px;")
        layout.addWidget(self.count_label)

    def _on_vault_unlocked(self, vault: Vault, path: str):
        """Called when the vault is successfully unlocked (password verified).
        If TOTP is enabled, prompt for 2FA code before proceeding."""

        # Check if 2FA is required
        if vault.has_totp and HAS_TOTP:
            dlg = TOTPVerifyDialog(self)
            while True:
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    # User cancelled 2FA -- lock the vault back up
                    vault.lock()
                    self.login_widget.status_label.setText("[CANCELLED] 2FA verification cancelled.")
                    self.login_widget.status_label.setStyleSheet("color: #e0af68; font-weight: bold;")
                    return
                code = dlg.get_code()
                if vault.verify_totp(code):
                    break
                else:
                    dlg.show_error("[ERROR] Invalid code. Try again.")

        self.vault = vault
        self.vault_path = path
        self.save_action.setEnabled(True)

        cats = ["ALL"] + list(vault.categories)
        self._rebuild_filter_menu(cats)
        self._set_filter("ALL")

        self._refresh_table()
        self.stack.setCurrentIndex(1)
        self.menuBar().setVisible(True)
        self.statusBar().setVisible(True)
        self.setWindowTitle(f"LockBox // {Path(path).name}")
        totp_status = " // 2FA ON" if vault.has_totp else ""
        self.statusBar().showMessage(f"> VAULT UNLOCKED // {len(vault.entries)} entries loaded{totp_status}")

        self._reset_auto_lock()

    def _refresh_table(self):
        if not self.vault:
            return
        self._filter_entries()

    def _rebuild_filter_menu(self, items: list[str]):
        """Rebuild the filter dropdown menu with the given items."""
        self._filter_menu.clear()
        for item in items:
            action = self._filter_menu.addAction(item)
            action.triggered.connect(lambda checked, t=item: self._set_filter(t))

    def _set_filter(self, text: str):
        """Set the active filter and refresh."""
        self._filter_current = text
        self.filter_btn.setText(text)
        self._filter_entries()

    def _filter_entries(self):
        if not self.vault:
            return

        query = self.search_edit.text().strip()
        category = self._filter_current
        if category == "ALL":
            category = None

        if query:
            entries = self.vault.search(query, category)
        elif category:
            entries = self.vault.get_entries_by_category(category)
        else:
            entries = self.vault.entries

        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            # Get category color
            cat_color = QColor(CATEGORY_COLORS.get(entry.category, "#c0caf5"))
            # Dimmer version for non-name columns
            dim_color = QColor(cat_color)
            dim_color.setAlpha(180)

            name_item = QTableWidgetItem(entry.name)
            name_item.setForeground(cat_color)
            name_item.setData(Qt.ItemDataRole.UserRole, entry.id)
            self.table.setItem(row, 0, name_item)

            user_item = QTableWidgetItem(entry.username)
            user_item.setForeground(QColor("#c0caf5"))
            self.table.setItem(row, 1, user_item)

            pw_item = QTableWidgetItem("*" * min(len(entry.password), 12))
            pw_item.setForeground(QColor("#3b4261"))
            pw_item.setData(Qt.ItemDataRole.UserRole, entry.password)
            pw_item.setData(Qt.ItemDataRole.UserRole + 1, entry.id)
            self.table.setItem(row, 2, pw_item)

            url_item = QTableWidgetItem(entry.url)
            url_item.setForeground(QColor("#565f89"))
            self.table.setItem(row, 3, url_item)

            cat_item = QTableWidgetItem(entry.category)
            cat_item.setForeground(cat_color)
            self.table.setItem(row, 4, cat_item)

        total = len(self.vault.entries)
        shown = len(entries)
        if shown == total:
            self.count_label.setText(f"> {total} entries")
        else:
            self.count_label.setText(f"> showing {shown} of {total} entries")

    def _get_selected_entry_id(self) -> Optional[str]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_entry(self):
        if not self.vault:
            return

        dlg = EntryDialog(self.vault.categories, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_entry_data()
            entry = VaultEntry(**data)
            self.vault.add_entry(entry)
            self.vault.save()
            self._refresh_table()
            self.statusBar().showMessage(f"> ADDED: {entry.name}")
        self._reset_auto_lock()

    def _edit_entry(self):
        if not self.vault:
            return

        entry_id = self._get_selected_entry_id()
        if not entry_id:
            self.statusBar().showMessage("> SELECT AN ENTRY TO EDIT")
            return

        entry = next((e for e in self.vault.entries if e.id == entry_id), None)
        if not entry:
            return

        dlg = EntryDialog(self.vault.categories, entry=entry, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_entry_data()
            self.vault.update_entry(entry_id, **data)
            self.vault.save()
            self._refresh_table()
            self.statusBar().showMessage(f"> UPDATED: {data['name']}")
        self._reset_auto_lock()

    def _delete_entry(self):
        if not self.vault:
            return

        entry_id = self._get_selected_entry_id()
        if not entry_id:
            self.statusBar().showMessage("> SELECT AN ENTRY TO DELETE")
            return

        entry = next((e for e in self.vault.entries if e.id == entry_id), None)
        if not entry:
            return

        confirm = QMessageBox.question(
            self,
            "CONFIRM DELETE",
            f"Delete '{entry.name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.vault.delete_entry(entry_id)
            self.vault.save()
            self._refresh_table()
            self.statusBar().showMessage(f"> DELETED: {entry.name}")
        self._reset_auto_lock()

    def _show_context_menu(self, pos):
        if not self.vault:
            return

        entry_id = self._get_selected_entry_id()
        if not entry_id:
            return

        entry = next((e for e in self.vault.entries if e.id == entry_id), None)
        if not entry:
            return

        menu = QMenu(self)

        copy_pw = menu.addAction("Copy Password")
        copy_user = menu.addAction("Copy Username")
        copy_url = menu.addAction("Copy URL")
        menu.addSeparator()
        edit = menu.addAction("Edit")
        delete = menu.addAction("Delete")

        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if action == copy_pw:
            self._copy_to_clipboard(entry.password, "PASSWORD")
        elif action == copy_user:
            self._copy_to_clipboard(entry.username, "USERNAME")
        elif action == copy_url:
            self._copy_to_clipboard(entry.url, "URL")
        elif action == edit:
            self._edit_entry()
        elif action == delete:
            self._delete_entry()

        self._reset_auto_lock()

    def _copy_to_clipboard(self, text: str, label: str = "TEXT"):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self._clipboard_timer.start(self.CLIPBOARD_CLEAR_MS)
        self.statusBar().showMessage(f"> {label} COPIED // clipboard clears in 30s")

    def _clear_clipboard(self):
        QApplication.clipboard().clear()
        self.statusBar().showMessage("> CLIPBOARD CLEARED")

    def _save_vault(self):
        if self.vault and self.vault.is_unlocked:
            self.vault.save()
            self.statusBar().showMessage("> VAULT SAVED")

    def _lock_vault(self):
        if self.vault:
            if self.vault.is_dirty:
                self.vault.save()
            self.vault.lock()

        self.vault = None
        self.save_action.setEnabled(False)
        self.table.setRowCount(0)
        self.search_edit.clear()
        self._auto_lock_timer.stop()
        self._clipboard_timer.stop()
        QApplication.clipboard().clear()

        # Return to login -- refresh state so it detects existing vault
        self.login_widget.refresh_state()
        self.stack.setCurrentIndex(0)
        self.menuBar().setVisible(False)
        self.statusBar().setVisible(False)
        self.setWindowTitle("LockBox")

    def _auto_lock(self):
        self._lock_vault()
        self.statusBar().showMessage("> AUTO-LOCKED // inactivity timeout")

    def _reset_auto_lock(self):
        self._auto_lock_timer.start(self.AUTO_LOCK_MS)

    def _open_generator(self):
        dlg = PasswordGeneratorDialog(self)
        dlg.exec()
        self._reset_auto_lock()

    def _import_passwords(self):
        if not self.vault:
            self.statusBar().showMessage("> UNLOCK VAULT FIRST")
            return

        dlg = ImportDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.imported_entries:
            count = self.vault.import_entries(dlg.imported_entries)
            self.vault.save()
            self._refresh_table()
            self.statusBar().showMessage(f"> IMPORTED {count} ENTRIES")
        self._reset_auto_lock()

    def _change_master_password(self):
        if not self.vault or not self.vault.is_unlocked:
            return

        dlg = ChangePasswordDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            from crypto_utils import derive_key
            try:
                test_key = derive_key(dlg.current_edit.text(), self.vault._salt)
                if test_key != self.vault._key:
                    QMessageBox.critical(self, "ERROR", "[ERROR] Current password is incorrect.")
                    return
            except Exception:
                QMessageBox.critical(self, "ERROR", "[ERROR] Current password is incorrect.")
                return

            self.vault.change_master_password(dlg.new_edit.text())
            QMessageBox.information(self, "SUCCESS", "> Master password changed.")
            self.statusBar().showMessage("> MASTER PASSWORD CHANGED")

    def _setup_totp(self):
        """Set up TOTP 2FA for the vault."""
        if not self.vault or not self.vault.is_unlocked:
            return
        if not HAS_TOTP:
            QMessageBox.warning(self, "ERROR", "[ERROR] pyotp/qrcode not installed.")
            return

        if self.vault.has_totp:
            QMessageBox.information(self, "2FA", "2FA is already enabled on this vault.")
            return

        # Generate secret and show setup dialog
        secret = self.vault.enable_totp()
        uri = self.vault.get_totp_uri()

        dlg = TOTPSetupDialog(uri, secret, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # User verified the code, 2FA is now active
            # Save session so quick unlock works immediately
            if self.vault_path:
                self._save_session_with_password_prompt()
            QMessageBox.information(
                self, "SUCCESS",
                "> 2FA ENABLED\n\n"
                "You will now need to enter a 6-digit code from\n"
                "Duo Mobile each time you unlock the vault.\n\n"
                "Your password has been saved for quick unlock\n"
                "(valid for 30 days)."
            )
            self.statusBar().showMessage("> 2FA ENABLED")
        else:
            # User cancelled -- disable TOTP
            self.vault.disable_totp()
            self.statusBar().showMessage("> 2FA SETUP CANCELLED")

    def _save_session_with_password_prompt(self):
        """Prompt user for master password and save a session for quick unlock."""
        from crypto_utils import derive_key

        dlg = QDialog(self)
        dlg.setWindowTitle("Save Session")
        dlg.setFixedWidth(400)
        layout = QVBoxLayout(dlg)

        info = QLabel(
            "Enter your master password to enable quick unlock.\n"
            "You'll only need your 2FA code for the next 30 days."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        pw_edit = QLineEdit()
        pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        pw_edit.setPlaceholderText("Master password")
        layout.addWidget(pw_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            password = pw_edit.text()
            if password:
                try:
                    test_key = derive_key(password, self.vault._salt)
                    if test_key == self.vault._key:
                        save_session(self.vault_path, password)
                        return
                except Exception:
                    pass
                QMessageBox.warning(self, "ERROR", "[ERROR] Incorrect password. Session not saved.")

    def _disable_totp(self):
        """Disable TOTP 2FA."""
        if not self.vault or not self.vault.is_unlocked:
            return

        if not self.vault.has_totp:
            QMessageBox.information(self, "2FA", "2FA is not currently enabled.")
            return

        # Require current TOTP code to disable
        dlg = TOTPVerifyDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            code = dlg.get_code()
            if self.vault.verify_totp(code):
                confirm = QMessageBox.question(
                    self,
                    "CONFIRM",
                    "Disable 2FA? You will only need your master password to unlock.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if confirm == QMessageBox.StandardButton.Yes:
                    self.vault.disable_totp()
                    if self.vault_path:
                        clear_session(self.vault_path)
                    QMessageBox.information(self, "SUCCESS", "> 2FA DISABLED")
                    self.statusBar().showMessage("> 2FA DISABLED")
            else:
                QMessageBox.critical(self, "ERROR", "[ERROR] Invalid code. 2FA not disabled.")

    def closeEvent(self, event):
        if self.vault and self.vault.is_unlocked:
            if self.vault.is_dirty:
                self.vault.save()
            self.vault.lock()
        QApplication.clipboard().clear()
        event.accept()

    def keyPressEvent(self, event):
        self._reset_auto_lock()
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self._reset_auto_lock()
        super().mousePressEvent(event)
