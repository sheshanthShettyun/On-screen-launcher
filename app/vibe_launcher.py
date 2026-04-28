#!/usr/bin/env python3

import configparser
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from PyQt5.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, Qt, QSize
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QIcon, QKeySequence, QPalette
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QShortcut,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


APP_DIRS = [
    Path.home() / ".local/share/applications",
    Path("/usr/local/share/applications"),
    Path("/usr/share/applications"),
]
STATE_DIR = Path.home() / ".cache/vibe-launcher"
HISTORY_FILE = STATE_DIR / "history.json"
KACTIVITY_DB = Path.home() / ".local/share/kactivitymanagerd/resources/database"
SOCKET_NAME = "com.vibe.launcher.toggle"


FIELD_CODE_RE = re.compile(r"\s+%[fFuUdDnNickvm]")


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.full_text = text
        self.setText(text)

    def setText(self, text):
        self.full_text = text or ""
        metrics = QFontMetrics(self.font())
        QLabel.setText(self, metrics.elidedText(self.full_text, Qt.ElideRight, max(12, self.width())))

    def resizeEvent(self, event):
        self.setText(self.full_text)
        super().resizeEvent(event)


def icon_for(name):
    icon = QIcon.fromTheme(name or "application-x-executable")
    if icon.isNull():
        icon = QIcon.fromTheme("application-x-executable")
    return icon


def clean_exec(command):
    return FIELD_CODE_RE.sub("", command or "").strip()


def desktop_id(path):
    return path.name


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return {}


def save_history(history):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def parse_desktop(path):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path, encoding="utf-8")
        entry = parser["Desktop Entry"]
    except Exception:
        return None

    if entry.get("Type") != "Application":
        return None
    if entry.getboolean("Hidden", fallback=False):
        return None

    name = entry.get("Name", "").strip()
    exec_line = clean_exec(entry.get("Exec", ""))
    if not name or not exec_line:
        return None

    generic = entry.get("GenericName", "").strip()
    comment = entry.get("Comment", "").strip()
    categories = entry.get("Categories", "").replace(";", " ").strip()

    return {
        "id": desktop_id(path),
        "path": str(path),
        "name": name,
        "subtitle": generic or comment or exec_line,
        "comment": comment,
        "categories": categories,
        "exec": exec_line,
        "icon": entry.get("Icon", "application-x-executable").strip(),
        "nodisplay": entry.getboolean("NoDisplay", fallback=False),
    }


def load_apps():
    apps = []
    seen = set()
    for app_dir in APP_DIRS:
        if not app_dir.exists():
            continue
        for path in sorted(app_dir.glob("*.desktop")):
            app = parse_desktop(path)
            if not app or app["id"] in seen:
                continue
            seen.add(app["id"])
            apps.append(app)
    return apps


def load_kde_recent_desktop_ids(limit=18):
    if not KACTIVITY_DB.exists():
        return []

    query = """
        SELECT targettedResource, MAX(lastUpdate) AS last_update, MAX(cachedScore) AS cached_score
        FROM ResourceScoreCache
        WHERE targettedResource LIKE 'applications:%'
        GROUP BY targettedResource
        ORDER BY last_update DESC, cached_score DESC
        LIMIT ?
    """

    try:
        conn = sqlite3.connect(str(KACTIVITY_DB))
        cur = conn.cursor()
        rows = cur.execute(query, (limit,)).fetchall()
        conn.close()
    except Exception:
        return []

    desktop_ids = []
    for resource, _, _ in rows:
        if not resource:
            continue
        desktop_id = str(resource).split("applications:", 1)[-1].strip()
        if desktop_id and desktop_id not in desktop_ids:
            desktop_ids.append(desktop_id)
    return desktop_ids


def launch_app(app):
    desktop = app["id"]
    commands = [
        ["gtk-launch", desktop],
        ["kioclient5", "exec", "applications:" + desktop],
        ["kstart5", "--application", desktop],
    ]
    for command in commands:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    try:
        subprocess.Popen(app["exec"], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


class AppTile(QFrame):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.hovered = False
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(72, 82)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 7, 4, 5)
        layout.setSpacing(6)

        self.icon = QLabel()
        self.icon.setFixedSize(52, 48)
        self.icon_name = app["icon"]
        self.base_icon_size = 44
        self.hover_icon_size = 50
        pixmap = icon_for(app["icon"]).pixmap(self.base_icon_size, self.base_icon_size)
        if pixmap.isNull():
            self.icon.setText(app["name"][:1].upper())
            self.icon.setObjectName("tileFallbackIcon")
        else:
            self.icon.setPixmap(pixmap)
        self.icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon, 0, Qt.AlignHCenter)

        self.title = ElidedLabel(app["name"])
        self.title.setObjectName("tileTitle")
        self.title.setFixedHeight(16)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(False)
        layout.addWidget(self.title)

    def set_hovered(self, hovered):
        self.hovered = hovered
        self.setProperty("hovered", hovered)
        pixmap = icon_for(self.icon_name).pixmap(
            self.hover_icon_size if hovered else self.base_icon_size,
            self.hover_icon_size if hovered else self.base_icon_size,
        )
        if not pixmap.isNull():
            self.icon.setPixmap(pixmap)
        self.title.setStyleSheet("font-size: 11px;" if hovered else "")
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, event):
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_hovered(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.window().open_app(self.app)


class ResultRow(QFrame):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.selected = False
        self.hovered = False
        self.item = None
        self.list_widget = None
        self.base_height = 56
        self.hover_height = 62
        self.setObjectName("resultRow")
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(11)

        self.icon = QLabel()
        self.icon.setFixedSize(30, 30)
        self.icon_name = app["icon"]
        self.base_icon_size = 26
        self.hover_icon_size = 30
        pixmap = icon_for(app["icon"]).pixmap(self.base_icon_size, self.base_icon_size)
        if pixmap.isNull():
            self.icon.setText(app["name"][:1].upper())
            self.icon.setObjectName("rowFallbackIcon")
        else:
            self.icon.setPixmap(pixmap)
        self.icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon)

        text_box = QVBoxLayout()
        text_box.setSpacing(1)

        self.title = ElidedLabel(app["name"])
        self.title.setObjectName("rowTitle")
        self.title.setFixedHeight(18)
        text_box.addWidget(self.title)

        self.subtitle = ElidedLabel(app["subtitle"])
        self.subtitle.setObjectName("rowSubtitle")
        self.subtitle.setFixedHeight(15)
        text_box.addWidget(self.subtitle)

        layout.addLayout(text_box, 1)

        self.arrow = QLabel("↵")
        self.arrow.setObjectName("rowArrow")
        self.arrow.setFixedSize(32, 22)
        self.arrow.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.arrow)

    def bind_item(self, item, list_widget):
        self.item = item
        self.list_widget = list_widget
        self.item.setSizeHint(QSize(0, self.base_height))

    def set_selected(self, selected):
        self.selected = selected
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_hovered(self, hovered):
        self.hovered = hovered
        self.setProperty("hovered", hovered)
        pixmap = icon_for(self.icon_name).pixmap(
            self.hover_icon_size if hovered else self.base_icon_size,
            self.hover_icon_size if hovered else self.base_icon_size,
        )
        if not pixmap.isNull():
            self.icon.setPixmap(pixmap)
        self.title.setStyleSheet("font-size: 14px;" if hovered else "")
        self.subtitle.setStyleSheet("font-size: 11px;" if hovered else "")
        if self.item is not None:
            self.item.setSizeHint(QSize(0, self.hover_height if hovered else self.base_height))
            if self.list_widget is not None:
                self.list_widget.doItemsLayout()
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, event):
        self.set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_hovered(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.window().open_app(self.app)


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.apps = load_apps()
        self.history = load_history()
        self.results = []
        self.selected = 0
        self.rows = []

        self.setWindowTitle("Vibe Launcher")
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(520, 585)

        self.build_ui()
        self.apply_style()
        self.refresh_home()

        QShortcut(QKeySequence("Escape"), self, self.close)

    def toggle_visibility(self):
        if self.isVisible():
            self.close()
            return
        self.show()
        self.raise_()
        self.activateWindow()

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.shell = QFrame()
        self.shell.setObjectName("shell")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 125))
        self.shell.setGraphicsEffect(shadow)
        root.addWidget(self.shell)

        layout = QVBoxLayout(self.shell)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(12)

        self.search_box = QFrame()
        self.search_box.setObjectName("searchBox")
        search_layout = QHBoxLayout(self.search_box)
        search_layout.setContentsMargins(18, 0, 14, 0)
        search_layout.setSpacing(12)
        layout.addWidget(self.search_box)

        icon = QLabel("⌕")
        icon.setObjectName("searchIcon")
        search_layout.addWidget(icon)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Search apps, commands, settings...")
        self.input.textChanged.connect(self.on_query)
        self.input.installEventFilter(self)
        search_layout.addWidget(self.input, 1)

        small = QLabel("▤")
        small.setObjectName("rightHint")
        search_layout.addWidget(small)

        self.section = QLabel("Recent apps")
        self.section.setObjectName("section")
        self.section.setFixedHeight(18)
        layout.addWidget(self.section)

        self.recent_grid = QWidget()
        self.recent_grid.setFixedHeight(92)
        self.recent_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.recent_layout = QGridLayout(self.recent_grid)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setHorizontalSpacing(10)
        self.recent_layout.setVerticalSpacing(0)
        layout.addWidget(self.recent_grid)

        self.recommended_section = QLabel("Recommended")
        self.recommended_section.setObjectName("section")
        self.recommended_section.setFixedHeight(18)
        layout.addWidget(self.recommended_section)

        self.empty = QLabel("Start typing to search desktop apps\n\nApplications, settings, commands, and runner results")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty, 1)

        self.list = QListWidget()
        self.list.setObjectName("resultList")
        self.list.setFrameShape(QFrame.NoFrame)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.itemClicked.connect(lambda item: self.open_app(item.data(Qt.UserRole)))
        layout.addWidget(self.list, 1)

        footer_line = QFrame()
        footer_line.setObjectName("footerLine")
        footer_line.setFixedHeight(1)
        layout.addWidget(footer_line)

        self.footer_widget = QWidget()
        self.footer_widget.setFixedHeight(22)
        footer = QHBoxLayout(self.footer_widget)
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addWidget(self.key_hint("↑↓", "Navigate"))
        footer.addWidget(self.key_hint("↵", "Open"))
        footer.addStretch()
        layout.addWidget(self.footer_widget)

    def key_hint(self, key, text):
        box = QWidget()
        box.setFixedHeight(20)
        box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        badge = QLabel(key)
        badge.setObjectName("keyBadge")
        badge.setFixedHeight(17)
        badge.setMinimumWidth(28)
        badge.setAlignment(Qt.AlignCenter)
        label = QLabel(text)
        label.setObjectName("keyText")
        label.setFixedHeight(17)
        label.setAlignment(Qt.AlignVCenter)
        layout.addWidget(badge)
        layout.addWidget(label)
        return box

    def apply_style(self):
        font = QFont("JetBrains Mono")
        if not font.exactMatch():
            font = QFont("monospace")
        QApplication.instance().setFont(font)

        self.setStyleSheet("""
            QWidget {
                color: #ffffff;
                background: transparent;
                font-family: "JetBrains Mono", monospace;
                letter-spacing: 0px;
            }
            #shell {
                background: #242424;
                border: 1px solid #303030;
                border-radius: 5px;
            }
            #searchBox {
                min-height: 58px;
                max-height: 58px;
                background: #303030;
                border: 1px solid #474747;
                border-radius: 8px;
            }
            #searchIcon {
                color: #b8b8b8;
                font-size: 24px;
            }
            QLineEdit {
                background: transparent;
                border: none;
                color: #eeeeee;
                selection-background-color: #555555;
                font-size: 18px;
            }
            QLineEdit::placeholder {
                color: #8e8e8e;
            }
            #rightHint {
                color: #a0a0a0;
                font-size: 15px;
            }
            #section {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 700;
            }
            #tile {
                background: transparent;
                border-radius: 8px;
            }
            #tile:hover {
                background: #303030;
            }
            #tileTitle {
                color: #dedede;
                font-size: 10px;
            }
            #tileFallbackIcon {
                color: #d8d8d8;
                background: #333333;
                border-radius: 12px;
                font-size: 22px;
                font-weight: 700;
            }
            #empty {
                color: #8f8f8f;
                font-size: 12px;
                line-height: 1.4;
            }
            #resultList {
                background: transparent;
                border: none;
                outline: none;
            }
            #resultList::item {
                border: none;
                padding: 0px;
                margin: 0px;
            }
            #resultRow {
                min-height: 52px;
                max-height: 52px;
                background: transparent;
                border-radius: 7px;
            }
            #resultRow:hover, #resultRow[selected="true"] {
                background: #333333;
            }
            #rowTitle {
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
            }
            #rowSubtitle {
                color: #a8a8a8;
                font-size: 10px;
            }
            #rowArrow {
                color: #bdbdbd;
                font-size: 13px;
            }
            #rowFallbackIcon {
                color: #d8d8d8;
                background: #333333;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
            }
            #footerLine {
                background: #3a3a3a;
            }
            #keyBadge {
                padding: 0px 5px;
                color: #b8b8b8;
                background: #333333;
                border-radius: 4px;
                font-size: 10px;
            }
            #keyText {
                color: #a3a3a3;
                font-size: 11px;
            }
            QScrollBar:vertical {
                width: 7px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #8a8a8a;
                border-radius: 3px;
                min-height: 34px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

    def center_on_screen(self):
        screen = QApplication.screenAt(QPoint(self.cursor().pos()))
        if screen is None:
            screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        visual_offset = 36
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2 + visual_offset,
        )

    def showEvent(self, event):
        self.center_on_screen()
        self.input.setFocus()
        self.input.selectAll()
        super().showEvent(event)

    def eventFilter(self, obj, event):
        if obj == self.input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Down:
                self.move_selection(1)
                return True
            if event.key() == Qt.Key_Up:
                self.move_selection(-1)
                return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self.results:
                    self.open_app(self.results[self.selected])
                return True
            if event.key() == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)

    def rank(self, app, query):
        q = query.lower().strip()
        hay = " ".join([app["name"], app["subtitle"], app["comment"], app["categories"], app["id"]]).lower()
        name = app["name"].lower()
        hist = self.history.get(app["id"], {})
        score = 0

        if name.startswith(q):
            score += 180
        elif app["id"].lower().startswith(q):
            score += 130
        elif q in name:
            score += 95
        elif q in hay:
            score += 55
        else:
            return -1

        score += min(int(hist.get("count", 0)) * 14, 90)
        score += int(hist.get("last", 0)) / 100000000000
        if not app["nodisplay"]:
            score += 12
        return score

    def on_query(self, text):
        query = text.strip()
        self.selected = 0
        if not query:
            self.refresh_home()
            return

        ranked = []
        for app in self.apps:
            score = self.rank(app, query)
            if score >= 0:
                ranked.append((score, app))

        ranked.sort(key=lambda item: (-item[0], item[1]["name"].lower()))
        self.results = [app for _, app in ranked[:12]]
        self.render_results()

    def recent_apps(self):
        by_id = {app["id"]: app for app in self.apps}
        recent = []
        seen_ids = set()

        for app_id in load_kde_recent_desktop_ids():
            if app_id in by_id and app_id not in seen_ids:
                recent.append(by_id[app_id])
                seen_ids.add(app_id)

        for app_id, data in sorted(self.history.items(), key=lambda item: item[1].get("last", 0), reverse=True):
            if app_id in by_id and app_id not in seen_ids:
                recent.append(by_id[app_id])
                seen_ids.add(app_id)

        preferred = ["code.desktop", "org.kde.dolphin.desktop", "org.kde.konsole.desktop", "firefox.desktop", "systemsettings.desktop"]
        seed = [by_id[p] for p in preferred if p in by_id and p not in seen_ids]
        filler = [app for app in self.apps if not app["nodisplay"] and app["id"] not in seen_ids and app["id"] not in {item["id"] for item in seed}]
        return (recent + seed + filler)[:6]

    def recommended_apps(self, recent):
        recent_ids = {app["id"] for app in recent}
        visible_apps = [app for app in self.apps if not app["nodisplay"] and app["id"] not in recent_ids]

        def score(app):
            text = (app["name"] + " " + app["categories"]).lower()
            value = 0
            for word in ("development", "utility", "system", "settings", "graphics", "internet", "terminal", "editor"):
                if word in text:
                    value += 8
            value -= len(app["name"]) / 40
            return value

        return sorted(visible_apps, key=lambda app: (-score(app), app["name"].lower()))[:7]

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def refresh_home(self):
        self.section.setText("Recent apps")
        self.empty.setVisible(False)
        self.recent_grid.show()
        self.recommended_section.show()
        self.clear_layout(self.recent_layout)
        recent = self.recent_apps()
        if not recent:
            self.recent_grid.hide()
            self.recommended_section.hide()
            self.list.hide()
            self.empty.show()
            return
        for i, app in enumerate(recent):
            self.recent_layout.addWidget(AppTile(app), 0, i, Qt.AlignLeft | Qt.AlignTop)

        self.results = self.recommended_apps(recent)
        self.selected = 0
        self.populate_list()
        self.list.setVisible(len(self.results) > 0)

    def render_results(self):
        self.section.setText("Top results")
        self.recent_grid.hide()
        self.recommended_section.hide()
        self.empty.setVisible(len(self.results) == 0)
        self.list.setVisible(len(self.results) > 0)
        self.populate_list()

    def populate_list(self):
        self.list.clear()
        self.rows = []
        for app in self.results:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 56))
            item.setData(Qt.UserRole, app)
            row = ResultRow(app)
            row.bind_item(item, self.list)
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self.rows.append(row)
        self.update_selection()

    def move_selection(self, direction):
        if not self.results:
            return
        self.selected = max(0, min(self.selected + direction, len(self.results) - 1))
        self.update_selection()

    def update_selection(self):
        for i, row in enumerate(self.rows):
            row.set_selected(i == self.selected)
        if self.results:
            self.list.setCurrentRow(self.selected)

    def open_app(self, app):
        if launch_app(app):
            entry = self.history.get(app["id"], {"count": 0})
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["last"] = int(time.time() * 1000)
            self.history[app["id"]] = entry
            save_history(self.history)
            self.close()


def main():
    socket = QLocalSocket()
    socket.connectToServer(SOCKET_NAME)
    if socket.waitForConnected(150):
        socket.write(b"toggle")
        socket.flush()
        socket.waitForBytesWritten(150)
        socket.disconnectFromServer()
        return

    QLocalServer.removeServer(SOCKET_NAME)
    app = QApplication(sys.argv)
    app.setApplicationName("Vibe Launcher")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#242424"))
    app.setPalette(palette)

    launcher = Launcher()
    server = QLocalServer()
    if not server.listen(SOCKET_NAME):
        QLocalServer.removeServer(SOCKET_NAME)
        server.listen(SOCKET_NAME)

    def handle_toggle():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                return
            connection.waitForReadyRead(50)
            connection.disconnectFromServer()
            launcher.toggle_visibility()

    server.newConnection.connect(handle_toggle)
    launcher.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
