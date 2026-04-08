# ── Color Palette ─────────────────────────────────────────────────────────────
COLORS = {
    'bg_primary':    '#0a0f1e',
    'bg_card':       '#131929',
    'bg_card_hover': '#1a2235',
    'accent_teal':   '#00d4aa',
    'accent_purple': '#7c3aed',
    'accent_amber':  '#f59e0b',
    'accent_red':    '#ef4444',
    'accent_green':  '#10b981',
    'text_primary':  '#f1f5f9',
    'text_secondary':'#94a3b8',
    'border':        '#1e2d45',
    'header_bg':     '#0d1526',
    'button_bg':     '#1e2d45',
    'button_hover':  '#2a3f5f',
    'emergency_red': '#dc2626',
    'emergency_hover':'#b91c1c',
}

FONT_MONO = "JetBrains Mono, Consolas, Courier New, monospace"
FONT_UI   = "Segoe UI, Inter, Arial, sans-serif"

def get_main_stylesheet() -> str:
    c = COLORS
    return f"""
    /* ── Global ─────────────────────────────────────────── */
    QMainWindow, QWidget {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        font-family: {FONT_UI};
        font-size: 13px;
    }}

    /* ── Cards ───────────────────────────────────────────── */
    QFrame#card {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}

    /* ── Labels ──────────────────────────────────────────── */
    QLabel#panel_title {{
        color: {c['accent_teal']};
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 1.5px;
        font-family: {FONT_MONO};
    }}
    QLabel#value_large {{
        color: {c['text_primary']};
        font-size: 28px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QLabel#value_medium {{
        color: {c['text_primary']};
        font-size: 16px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QLabel#value_small {{
        color: {c['text_secondary']};
        font-size: 11px;
        font-family: {FONT_MONO};
    }}

    /* ── Buttons ─────────────────────────────────────────── */
    QPushButton {{
        background-color: {c['button_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {c['button_hover']};
        border-color: {c['accent_teal']};
    }}
    QPushButton:pressed {{
        background-color: {c['accent_teal']};
        color: {c['bg_primary']};
    }}
    QPushButton#btn_emergency {{
        background-color: {c['emergency_red']};
        color: white;
        border: 2px solid #ff6b6b;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        letter-spacing: 1px;
    }}
    QPushButton#btn_emergency:hover {{
        background-color: {c['emergency_hover']};
    }}
    QPushButton#btn_connect {{
        background-color: {c['accent_green']};
        color: {c['bg_primary']};
        font-weight: bold;
    }}
    QPushButton#btn_connect:hover {{
        background-color: #059669;
    }}
    QPushButton#btn_active {{
        background-color: {c['accent_teal']};
        color: {c['bg_primary']};
        border: none;
    }}
    QPushButton#btn_dpad {{
        background-color: {c['button_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
    }}
    QPushButton#btn_dpad:pressed {{
        background-color: {c['accent_teal']};
        color: {c['bg_primary']};
    }}
    QPushButton#btn_stop_center {{
        background-color: {c['accent_amber']};
        color: {c['bg_primary']};
        border-radius: 8px;
        font-size: 16px;
        font-weight: bold;
        border: none;
    }}
    QPushButton#btn_stop_center:hover {{
        background-color: #d97706;
    }}
    QPushButton#btn_takeoff {{
        background-color: {c['accent_green']};
        color: {c['bg_primary']};
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_hover {{
        background-color: {c['accent_teal']};
        color: {c['bg_primary']};
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_land {{
        background-color: {c['accent_amber']};
        color: {c['bg_primary']};
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_wasd {{
        background-color: {c['accent_teal']};
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_wasd:pressed {{
        background-color: #009980;
    }}
    QPushButton#btn_maneuver {{
        background-color: #1a6ea8;
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_maneuver:hover {{
        background-color: #1e80c4;
    }}
    QPushButton#btn_apply {{
        background-color: {c['accent_green']};
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_reset_default {{
        background-color: {c['accent_amber']};
        color: {c['bg_primary']};
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_square {{
        background-color: #7b2fbe;
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QLabel#uptime_label {{
        color: {c['accent_teal']};
        font-size: 11px;
        font-family: {FONT_MONO};
    }}
    QLabel#video_frame {{
        background-color: {c['bg_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        font-size: 13px;
        color: {c['text_secondary']};
    }}
    QPushButton#btn_safety_unlock {{
        background-color: {c['accent_amber']};
        color: #0f172a;
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_high_level {{
        background-color: {c['accent_purple']};
        color: white;
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QFrame#status_value_frame {{
        background-color: {c['bg_primary']};
        border-radius: 6px;
    }}
    QLabel#connect_page_title {{
        color: {c['accent_teal']};
        font-size: 18px;
        font-weight: bold;
        font-family: {FONT_MONO};
        letter-spacing: 2px;
    }}
    QLineEdit#uri_input {{
        background-color: {c['bg_primary']};
        color: {c['accent_teal']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QLabel#sensor_val_green {{
        color: {c['accent_green']};
        font-size: 22px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QLabel#sensor_val_teal {{
        color: {c['accent_teal']};
        font-size: 22px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QProgressBar#batt_bar::chunk {{
        background-color: {c['accent_green']};
        border-radius: 3px;
    }}
    QProgressBar#tof_bar::chunk {{
        background-color: {c['accent_teal']};
        border-radius: 3px;
    }}
    QTextEdit#connection_console {{
        background-color: {c['bg_primary']};
        color: {c['accent_teal']};
        border: 1px solid {c['border']};
        border-radius: 6px;
    }}

    /* ── Progress Bars ───────────────────────────────────── */
    QProgressBar {{
        background-color: {c['bg_primary']};
        border: 1px solid {c['border']};
        border-radius: 4px;
        text-align: center;
        color: {c['text_primary']};
        font-size: 11px;
    }}
    QProgressBar::chunk {{
        background-color: {c['accent_teal']};
        border-radius: 3px;
    }}
    QProgressBar#motor_bar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {c['accent_purple']}, stop:1 {c['accent_teal']});
    }}

    /* ── Sliders ─────────────────────────────────────────── */
    QSlider::groove:vertical {{
        background: {c['bg_primary']};
        border: 1px solid {c['border']};
        width: 8px;
        border-radius: 4px;
    }}
    QSlider::handle:vertical {{
        background: {c['accent_teal']};
        border: none;
        height: 16px;
        width: 16px;
        border-radius: 8px;
        margin: 0 -4px;
    }}
    QSlider::sub-page:vertical {{
        background: {c['accent_teal']};
        border-radius: 4px;
    }}
    QSlider::groove:horizontal {{
        background: {c['bg_primary']};
        border: 1px solid {c['border']};
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {c['accent_teal']};
        border: none;
        height: 16px;
        width: 16px;
        border-radius: 8px;
        margin: -5px 0;
    }}
    QSlider::sub-page:horizontal {{
        background: {c['accent_teal']};
        border-radius: 3px;
    }}

    /* ── Log Viewer ──────────────────────────────────────── */
    QListWidget#security_log {{
        background-color: #080d18;
        border: 1px solid {c['border']};
        border-radius: 8px;
        font-family: {FONT_MONO};
        font-size: 11px;
        color: {c['text_primary']};
    }}
    QListWidget#security_log::item {{
        padding: 3px 6px;
        border-bottom: 1px solid #0f1829;
    }}

    /* ── ScrollBar ───────────────────────────────────────── */
    QScrollBar:vertical {{
        background: {c['bg_primary']};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border']};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: {c['bg_primary']};
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c['border']};
        border-radius: 4px;
        min-width: 20px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    """


def card_style() -> str:
    """Returns inline style for a card frame — uses current COLORS dict."""
    return (f"background-color: {COLORS['bg_card']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 12px;")


def card_style_light() -> str:
    """Returns inline style for a card frame (light theme)."""
    return (f"background-color: {LIGHT_COLORS['bg_card']}; "
            f"border: 1px solid {LIGHT_COLORS['border']}; border-radius: 12px;")


_DARK_COLORS = dict(COLORS)   # snapshot of dark palette


def apply_light_mode() -> None:
    """Patch COLORS in-place so card_style() returns light values."""
    COLORS.update(LIGHT_COLORS)


def apply_dark_mode() -> None:
    """Restore COLORS to dark palette."""
    COLORS.update(_DARK_COLORS)


# ── Light theme palette ────────────────────────────────────────────────────────
LIGHT_COLORS = {
    'bg_primary':    '#f0f4f8',
    'bg_card':       '#ffffff',
    'bg_card_hover': '#e8eef5',
    'accent_teal':   '#0097a7',
    'accent_purple': '#6d28d9',
    'accent_amber':  '#d97706',
    'accent_red':    '#dc2626',
    'accent_green':  '#059669',
    'text_primary':  '#0f172a',
    'text_secondary':'#475569',
    'border':        '#cbd5e1',
    'header_bg':     '#e2e8f0',
    'button_bg':     '#dde3eb',
    'button_hover':  '#c8d3e0',
    'emergency_red': '#dc2626',
    'emergency_hover':'#b91c1c',
}


def get_light_stylesheet() -> str:
    c = LIGHT_COLORS
    return f"""
    /* ── Global ─────────────────────────────────────────── */
    QMainWindow, QWidget {{
        background-color: {c['bg_primary']};
        color: {c['text_primary']};
        font-family: {FONT_UI};
        font-size: 13px;
    }}
    QScrollArea {{
        background-color: {c['bg_primary']};
        border: none;
    }}
    QStackedWidget {{
        background-color: {c['bg_primary']};
    }}

    /* ── Cards ───────────────────────────────────────────── */
    QFrame#card {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}
    QFrame {{
        background-color: transparent;
    }}
    QGroupBox {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        margin-top: 8px;
        padding-top: 6px;
        font-weight: bold;
        color: {c['text_primary']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        color: {c['accent_teal']};
    }}

    /* ── Labels ──────────────────────────────────────────── */
    QLabel {{
        background: transparent;
        color: {c['text_primary']};
    }}
    QLabel#panel_title {{
        color: {c['accent_teal']};
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 1.5px;
        font-family: {FONT_MONO};
    }}
    QLabel#value_large {{
        color: {c['text_primary']};
        font-size: 28px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QLabel#value_medium {{
        color: {c['text_primary']};
        font-size: 16px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QLabel#value_small {{
        color: {c['text_secondary']};
        font-size: 11px;
        font-family: {FONT_MONO};
    }}

    /* ── Input fields ────────────────────────────────────── */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {c['bg_card']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
        selection-background-color: {c['accent_teal']};
        selection-color: white;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border-color: {c['accent_teal']};
    }}

    /* ── Buttons ─────────────────────────────────────────── */
    QPushButton {{
        background-color: {c['button_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {c['button_hover']};
        border-color: {c['accent_teal']};
    }}
    QPushButton:pressed {{
        background-color: {c['accent_teal']};
        color: white;
    }}
    QPushButton:disabled {{
        background-color: #e2e8f0;
        color: #94a3b8;
        border-color: #e2e8f0;
    }}
    QPushButton#btn_emergency {{
        background-color: {c['emergency_red']};
        color: white;
        border: 2px solid #fca5a5;
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        letter-spacing: 1px;
    }}
    QPushButton#btn_emergency:hover {{
        background-color: {c['emergency_hover']};
    }}
    QPushButton#btn_connect {{
        background-color: {c['accent_green']};
        color: white;
        font-weight: bold;
        border: none;
    }}
    QPushButton#btn_connect:hover {{
        background-color: #047857;
    }}
    QPushButton#btn_active {{
        background-color: {c['accent_teal']};
        color: white;
        border: none;
    }}
    QPushButton#btn_dpad {{
        background-color: {c['button_bg']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
    }}
    QPushButton#btn_dpad:pressed {{
        background-color: {c['accent_teal']};
        color: white;
    }}
    QPushButton#btn_stop_center {{
        background-color: {c['accent_amber']};
        color: white;
        border-radius: 8px;
        font-size: 16px;
        font-weight: bold;
        border: none;
    }}
    QPushButton#btn_stop_center:hover {{
        background-color: #b45309;
    }}
    QPushButton#btn_takeoff {{
        background-color: {c['accent_green']};
        color: white;
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_hover {{
        background-color: {c['accent_teal']};
        color: white;
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_land {{
        background-color: {c['accent_amber']};
        color: white;
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_wasd {{
        background-color: {c['accent_teal']};
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_maneuver {{
        background-color: #1a6ea8;
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_apply {{
        background-color: {c['accent_green']};
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_reset_default {{
        background-color: {c['accent_amber']};
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QPushButton#btn_square {{
        background-color: #7b2fbe;
        color: white;
        font-weight: bold;
        border-radius: 4px;
        border: none;
    }}
    QLabel#uptime_label {{
        color: {c['accent_teal']};
        font-size: 11px;
        font-family: {FONT_MONO};
    }}
    QLabel#video_frame {{
        background-color: {c['bg_primary']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        font-size: 13px;
        color: {c['text_secondary']};
    }}
    QPushButton#btn_safety_unlock {{
        background-color: {c['accent_amber']};
        color: #0f172a;
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QPushButton#btn_high_level {{
        background-color: {c['accent_purple']};
        color: white;
        font-weight: bold;
        border-radius: 6px;
        border: none;
    }}
    QFrame#status_value_frame {{
        background-color: {c['bg_primary']};
        border-radius: 6px;
    }}
    QLabel#connect_page_title {{
        color: {c['accent_teal']};
        font-size: 18px;
        font-weight: bold;
        font-family: {FONT_MONO};
        letter-spacing: 2px;
    }}
    QLineEdit#uri_input {{
        background-color: {c['bg_primary']};
        color: {c['accent_teal']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QLabel#sensor_val_green {{
        color: {c['accent_green']};
        font-size: 22px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QLabel#sensor_val_teal {{
        color: {c['accent_teal']};
        font-size: 22px;
        font-weight: bold;
        font-family: {FONT_MONO};
    }}
    QProgressBar#batt_bar::chunk {{
        background-color: {c['accent_green']};
        border-radius: 3px;
    }}
    QProgressBar#tof_bar::chunk {{
        background-color: {c['accent_teal']};
        border-radius: 3px;
    }}
    QTextEdit#connection_console {{
        background-color: {c['bg_primary']};
        color: {c['accent_teal']};
        border: 1px solid {c['border']};
        border-radius: 6px;
    }}

    /* ── Combo / Spin ────────────────────────────────────── */
    QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {c['bg_card']};
        color: {c['text_primary']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        padding: 3px 8px;
    }}
    QComboBox::drop-down {{
        border: none;
    }}

    /* ── Progress Bars ───────────────────────────────────── */
    QProgressBar {{
        background-color: #e2e8f0;
        border: 1px solid {c['border']};
        border-radius: 4px;
        text-align: center;
        color: {c['text_primary']};
        font-size: 11px;
        font-weight: bold;
    }}
    QProgressBar::chunk {{
        background-color: {c['accent_teal']};
        border-radius: 3px;
    }}
    QProgressBar#motor_bar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {c['accent_purple']}, stop:1 {c['accent_teal']});
    }}

    /* ── Sliders ─────────────────────────────────────────── */
    QSlider::groove:vertical {{
        background: #e2e8f0;
        border: 1px solid {c['border']};
        width: 8px;
        border-radius: 4px;
    }}
    QSlider::handle:vertical {{
        background: {c['accent_teal']};
        border: none;
        height: 16px;
        width: 16px;
        border-radius: 8px;
        margin: 0 -4px;
    }}
    QSlider::sub-page:vertical {{
        background: {c['accent_teal']};
        border-radius: 4px;
    }}
    QSlider::groove:horizontal {{
        background: #dde3eb;
        border: 1px solid {c['border']};
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {c['accent_teal']};
        border: none;
        height: 16px;
        width: 16px;
        border-radius: 8px;
        margin: -5px 0;
    }}
    QSlider::sub-page:horizontal {{
        background: {c['accent_teal']};
        border-radius: 3px;
    }}

    /* ── Tab widget ──────────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {c['border']};
        background: {c['bg_card']};
        border-radius: 0 8px 8px 8px;
    }}
    QTabBar::tab {{
        background: {c['button_bg']};
        color: {c['text_secondary']};
        border: 1px solid {c['border']};
        padding: 6px 14px;
        margin-right: 2px;
        border-radius: 6px 6px 0 0;
    }}
    QTabBar::tab:selected {{
        background: {c['bg_card']};
        color: {c['accent_teal']};
        border-bottom: 2px solid {c['accent_teal']};
        font-weight: bold;
    }}

    /* ── List / Tree ─────────────────────────────────────── */
    QListWidget, QTreeWidget, QTableWidget {{
        background-color: {c['bg_card']};
        border: 1px solid {c['border']};
        border-radius: 6px;
        alternate-background-color: {c['bg_primary']};
        color: {c['text_primary']};
    }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {c['accent_teal']};
        color: white;
    }}
    QListWidget#security_log {{
        background-color: #f8fafc;
        border: 1px solid {c['border']};
        border-radius: 8px;
        font-family: {FONT_MONO};
        font-size: 11px;
        color: {c['text_primary']};
    }}
    QListWidget#security_log::item {{
        padding: 3px 6px;
        border-bottom: 1px solid {c['border']};
    }}

    /* ── Header ──────────────────────────────────────────── */
    QHeaderView::section {{
        background-color: {c['button_bg']};
        color: {c['text_secondary']};
        border: none;
        padding: 4px 8px;
        font-weight: bold;
        font-size: 11px;
    }}

    /* ── Splitter ────────────────────────────────────────── */
    QSplitter::handle {{
        background-color: {c['border']};
        width: 2px;
        height: 2px;
    }}

    /* ── ScrollBar ───────────────────────────────────────── */
    QScrollBar:vertical {{
        background: #e8eef5;
        width: 8px;
        border-radius: 4px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: #94a3b8;
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {c['accent_teal']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background: #e8eef5;
        height: 8px;
        border-radius: 4px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: #94a3b8;
        border-radius: 4px;
        min-width: 20px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {c['accent_teal']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    QScrollBar::corner {{
        background: transparent;
    }}
    """
