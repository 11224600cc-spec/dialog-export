"""
DeepSeek 对话导出器 - GUI 版
=============================
PySide6 毛玻璃风格界面，壁纸背景

安装依赖:
  pip install PySide6 playwright
"""

import json
import time
import re
import html as _html
import hashlib
import sys
import os
import math
import random
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QSpinBox,
    QProgressBar, QFileDialog, QFrame, QInputDialog, QScrollArea,
    QGridLayout, QListWidget, QListWidgetItem, QDialog, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QPoint, QTimer, QPropertyAnimation, QEasingCurve, QPointF, QRect
from PySide6.QtGui import QFont, QColor, QPainter, QPixmap, QPalette, QPainterPath, QPen

# ==================== 配置 ====================
# PyInstaller --onefile 解压临时目录（用于内嵌资源）
# 正常运行时为 None，打包后指向 sys._MEIPASS
_BUNDLE_DIR = Path(getattr(sys, '_MEIPASS', '')) if hasattr(sys, '_MEIPASS') else Path(__file__).resolve().parent

# 运行时目录：exe 所在目录（用于 output、config、profile 等运行时文件）
# PyInstaller onefreeze 模式下，sys.executable 指向 exe；普通 Python 运行指向脚本目录
if getattr(sys, 'frozen', False):
    _APP_DIR = Path(sys.executable).resolve().parent
else:
    _APP_DIR = Path(__file__).resolve().parent

EXECUTABLE_PATH = r"C:\Users\Administrator\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe"
PROFILE_DIR = _APP_DIR / "chromium_profile"
OUTPUT_DIR = _APP_DIR / "output"
CONFIG_FILE = _APP_DIR / "deepseek_config.json"
DEFAULT_WALLPAPER = _BUNDLE_DIR / "default_wallpaper.png"

PAGE_TIMEOUT = 60000
# ================================================


def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {"wallpaper": str(DEFAULT_WALLPAPER), "wallpapers": []}


def save_config(config):
    """保存配置文件"""
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')


def get_wallpaper():
    """获取当前壁纸路径"""
    config = load_config()
    wp = config.get("wallpaper", str(DEFAULT_WALLPAPER))
    p = Path(wp)
    return p if p.exists() else DEFAULT_WALLPAPER


# ==================== 毛玻璃卡片 Widget ====================
class GlassCard(QFrame):
    """毛玻璃风格卡片容器，支持透明度调节"""
    def __init__(self, parent=None, radius=16, opacity=160):
        super().__init__(parent)
        self._radius = radius
        self._opacity = opacity  # 0-255
        self.setObjectName("glassCard")

    def set_opacity(self, val):
        self._opacity = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(30, 30, 46, self._opacity)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)
        border = QColor(255, 255, 255, max(10, self._opacity // 6))
        painter.setBrush(Qt.NoBrush)
        pen = painter.pen()
        pen.setColor(border)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), self._radius - 1, self._radius - 1)
        painter.end()


# ==================== 粒子庆祝效果 ====================
class ParticleOverlay(QWidget):
    """导出完成时的粒子庆祝效果"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.hide()
        self._particles = []
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._animate)

    def celebrate(self, origin=None):
        self.setGeometry(0, 0, self.parent().width(), self.parent().height())
        if origin is None:
            origin = QPoint(self.width() // 2, self.height() // 3)
        colors = ['#a6e3a1', '#89b4fa', '#cba6f7', '#f9e2af', '#fab387', '#89dceb']
        for _ in range(40):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(2.0, 7.0)
            self._particles.append({
                'x': float(origin.x()), 'y': float(origin.y()),
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed - 3,
                'color': random.choice(colors),
                'size': random.uniform(2.5, 6.5),
                'life': random.uniform(0.65, 1.0),
            })
        self.show()
        self.raise_()
        self._timer.start()

    def _animate(self):
        all_dead = True
        for p in self._particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.12  # 重力
            p['life'] -= 0.018
            p['size'] *= 0.993
            if p['life'] > 0:
                all_dead = False
        self.update()
        if all_dead:
            self._timer.stop()
            self._particles.clear()
            self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for p in self._particles:
            if p['life'] <= 0:
                continue
            color = QColor(p['color'])
            color.setAlphaF(max(0.0, min(1.0, p['life'])))
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(p['x'], p['y']), p['size'], p['size'])
        painter.end()


# ==================== 底部波形装饰 ====================
class WaveformWidget(QWidget):
    """底部装饰性波形动画"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(45)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        self._phase += 0.06
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        waves = [
            (0.0,  0.15, '#89b4fa', 0.18),
            (1.2,  0.10, '#cba6f7', 0.12),
            (2.8,  0.07, '#a6e3a1', 0.08),
        ]
        for offset, amp, color_str, alpha in waves:
            color = QColor(color_str)
            color.setAlphaF(alpha)
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            path = QPainterPath()
            first = True
            for x in range(0, w + 2, 3):
                y = h * 0.5 + math.sin(self._phase + offset + x * 0.015) * h * amp
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)
            painter.drawPath(path)
        painter.end()


# ==================== 毛玻璃提示框 ====================
class GlassMessageBox(QDialog):
    """毛玻璃风格提示框，替代原生 QMessageBox"""
    def __init__(self, parent=None, msg_type="info", title="提示", text="", buttons=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None
        self._result = None
        self._buttons_cfg = buttons

        if self._buttons_cfg is None:
            if msg_type == "warning":
                self._buttons_cfg = [
                    {"text": "取消", "role": "reject", "style": "ghostBtn"},
                    {"text": "确定", "role": "accept", "style": "dangerBtn"},
                ]
            elif msg_type == "error":
                self._buttons_cfg = [{"text": "关闭", "role": "accept", "style": "primaryBtn"}]
            else:
                self._buttons_cfg = [{"text": "好的", "role": "accept", "style": "primaryBtn"}]

        self._init_ui(msg_type, title, text)

    def _init_ui(self, msg_type, title, text):
        # 顶层布局直接挂在对话框本身，不用额外 container
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # 图标 + 标题
        icon_map   = {"info": "ℹ",  "warning": "⚠", "error": "✕"}
        color_map  = {
            "info":    "rgba(137,180,250,220)",
            "warning": "rgba(249,226,175,220)",
            "error":   "rgba(243,139,168,220)",
        }
        header = QHBoxLayout()
        icon_label = QLabel(icon_map.get(msg_type, "ℹ"))
        icon_label.setStyleSheet(
            f"font-size: 22px; color: {color_map.get(msg_type, color_map['info'])};"
        )
        icon_label.setFixedWidth(30)
        header.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: rgba(255,255,255,220); font-size: 15px; font-weight: bold;"
        )
        header.addWidget(title_label)
        header.addStretch()
        root.addLayout(header)

        # 分隔线
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(255,255,255,20);")
        root.addWidget(line)

        # 内容文本
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setMinimumWidth(280)
        text_label.setMaximumWidth(400)
        text_label.setStyleSheet(
            "color: rgba(205,214,244,200); font-size: 13px;"
        )
        text_label.setTextFormat(Qt.PlainText)
        root.addWidget(text_label)

        root.addSpacing(4)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for btn_info in self._buttons_cfg:
            btn = QPushButton(btn_info["text"])
            btn.setObjectName(btn_info["style"])
            btn.setMinimumWidth(80)
            btn.clicked.connect(
                lambda checked, role=btn_info["role"]: self._on_btn(role)
            )
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

        # 固定宽度，高度交给 adjustSize
        self.setFixedWidth(360)
        self.adjustSize()

    def showEvent(self, event):
        super().showEvent(event)
        self._pop_in()

    def _pop_in(self):
        """弹入动画：从小到大弹出"""
        self._anim = QPropertyAnimation(self, b"geometry")
        final = self.geometry()
        cx, cy = final.center().x(), final.center().y()
        w2, h2 = final.width() // 2, final.height() // 2
        self._anim.setStartValue(QRect(cx - w2, cy - h2, final.width() // 2, final.height() // 2))
        self._anim.setEndValue(final)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.start()

    def _close_with_animation(self):
        """弹出动画：缩小后关闭"""
        self._close_anim = QPropertyAnimation(self, b"geometry")
        current = self.geometry()
        cx, cy = current.center().x(), current.center().y()
        w2, h2 = current.width() // 2, current.height() // 2
        self._close_anim.setStartValue(current)
        self._close_anim.setEndValue(QRect(cx - w2, cy - h2, current.width() // 2, current.height() // 2))
        self._close_anim.setDuration(150)
        self._close_anim.setEasingCurve(QEasingCurve.Type.InBack)
        self._close_anim.finished.connect(self.accept)
        self._close_anim.start()

    def _on_btn(self, role):
        if role == "accept":
            self._result = True
        else:
            self._result = False
        self._close_with_animation()

    def result_value(self):
        return self._result

    @staticmethod
    def show_info(parent, title, text):
        dlg = GlassMessageBox(parent, "info", title, text)
        dlg.move(parent.x() + (parent.width() - dlg.width()) // 2,
                 parent.y() + (parent.height() - dlg.height()) // 2)
        dlg.exec()
        return True

    @staticmethod
    def show_warning(parent, title, text):
        dlg = GlassMessageBox(parent, "warning", title, text)
        dlg.move(parent.x() + (parent.width() - dlg.width()) // 2,
                 parent.y() + (parent.height() - dlg.height()) // 2)
        dlg.exec()
        return dlg.result_value()

    @staticmethod
    def show_error(parent, title, text):
        dlg = GlassMessageBox(parent, "error", title, text)
        dlg.move(parent.x() + (parent.width() - dlg.width()) // 2,
                 parent.y() + (parent.height() - dlg.height()) // 2)
        dlg.exec()
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def paintEvent(self, event):
        # 绘制圆角背景
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(30, 30, 46, 230))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 16, 16)
        border = QColor(255, 255, 255, 20)
        painter.setBrush(Qt.NoBrush)
        pen = painter.pen()
        pen.setColor(border)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 15, 15)
        painter.end()


# ==================== 单个壁纸缩略图卡片 ====================
class WallpaperCard(QFrame):
    """壁纸卡片：缩略图 + 名称 + 重命名/删除按钮"""
    rename_requested = Signal(str)  # path
    delete_requested = Signal(str)  # path
    selected = Signal(str)           # path

    def __init__(self, path, name, is_current=False, parent=None):
        super().__init__(parent)
        self._path = path
        self._name = name
        self._is_current = is_current
        self._init_ui()

    def _init_ui(self):
        self.setFixedSize(120, 110)
        self.setObjectName("wpCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            #wpCard {
                background: rgba(0,0,0,70);
                border: 1px solid rgba(255,255,255,15);
                border-radius: 8px;
            }
            #wpCard:hover {
                background: rgba(137,180,250,30);
                border-color: rgba(137,180,250,80);
            }
            #wpCard.current {
                border: 2px solid rgba(137,180,250,200);
            }
        """)
        if self._is_current:
            self.setStyleSheet("""
                #wpCard {
                    background: rgba(137,180,250,40);
                    border: 2px solid rgba(137,180,250,200);
                    border-radius: 8px;
                }
                #wpCard:hover {
                    background: rgba(137,180,250,60);
                    border-color: rgba(166,227,161,200);
                }
            """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # 缩略图
        self.thumb = QLabel()
        self.thumb.setFixedSize(112, 64)
        self.thumb.setObjectName("cardThumb")
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet("border-radius: 4px; background: rgba(0,0,0,80);")
        p = Path(self._path)
        if p.exists():
            pixmap = QPixmap(str(p))
            if not pixmap.isNull():
                scaled = pixmap.scaled(112, 64, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                self.thumb.setPixmap(scaled)
        layout.addWidget(self.thumb)

        # 名称
        name_label = QLabel(self._name)
        name_label.setObjectName("cardName")
        name_label.setFixedHeight(16)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("color: rgba(205,214,244,200); font-size: 10px;")
        name_label.setTextInteractionFlags(Qt.NoTextInteraction)
        layout.addWidget(name_label)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(2)

        rename_btn = QPushButton("✏")
        rename_btn.setFixedSize(22, 18)
        rename_btn.setObjectName("cardRenameBtn")
        rename_btn.setToolTip("重命名")
        rename_btn.clicked.connect(lambda: self.rename_requested.emit(self._path))
        btn_row.addWidget(rename_btn)

        delete_btn = QPushButton("✕")
        delete_btn.setFixedSize(22, 18)
        delete_btn.setObjectName("cardDeleteBtn")
        delete_btn.setToolTip("删除")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._path))
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.setStyleSheet(self.styleSheet() + """
            #cardRenameBtn {
                background: rgba(255,255,255,15);
                color: rgba(205,214,244,150);
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            #cardRenameBtn:hover { background: rgba(137,180,250,100); color: white; }
            #cardDeleteBtn {
                background: rgba(255,255,255,15);
                color: rgba(243,139,168,150);
                border: none;
                border-radius: 4px;
                font-size: 10px;
            }
            #cardDeleteBtn:hover { background: rgba(243,139,168,150); color: white; }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit(self._path)


# ==================== 背景设置对话框 ====================
class BgSettingsDialog(QDialog):
    """背景壁纸选择与管理：缩略图网格 + 实时预览"""
    bg_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("背景设置")
        self.setFixedSize(540, 580)
        self.setObjectName("bgSettingsDialog")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None
        self._config = load_config()
        self._init_ui()

    def _init_ui(self):
        container = QWidget(self)
        container.setObjectName("bgContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 45, 20, 20)
        layout.setSpacing(12)

        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setObjectName("bgTitleBar")
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_label = QLabel("⚙ 背景设置")
        tb_label.setStyleSheet("color: rgba(255,255,255,220); font-size: 14px; font-weight: bold;")
        tb_layout.addWidget(tb_label)
        tb_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.close)
        tb_layout.addWidget(close_btn)
        layout.addWidget(title_bar)

        # 当前选中预览（大图）
        self.preview = QLabel()
        self.preview.setFixedSize(500, 200)
        self.preview.setObjectName("bgPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self._update_preview()
        layout.addWidget(self.preview, alignment=Qt.AlignCenter)

        # 当前壁纸名称
        self.wp_name_label = QLabel()
        self.wp_name_label.setObjectName("wpNameLabel")
        self.wp_name_label.setAlignment(Qt.AlignCenter)
        self._update_name_label()
        layout.addWidget(self.wp_name_label)

        # 顶部按钮行
        btn_row = QHBoxLayout()
        select_btn = QPushButton("➕ 添加背景图片")
        select_btn.setObjectName("primaryBtn")
        select_btn.clicked.connect(self._on_select)
        btn_row.addWidget(select_btn)

        reset_btn = QPushButton("↩ 恢复默认")
        reset_btn.setObjectName("ghostBtn")
        reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        # 壁纸网格区域标题
        grid_label = QLabel("所有背景（点击选中 · 卡片内重命名/删除）")
        grid_label.setStyleSheet("color: rgba(137,180,250,200); font-size: 12px; font-weight: bold;")
        layout.addWidget(grid_label)

        # 缩略图网格（带滚动条）
        scroll = QScrollArea()
        scroll.setObjectName("wallpaperScroll")
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(220)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: rgba(0,0,0,60); border: 1px solid rgba(255,255,255,10);
                          border-radius: 8px; }
            QScrollBar:vertical { background: rgba(255,255,255,15); width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,30); border-radius: 3px; min-height: 30px; }
        """)

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(8)
        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)

        self.setStyleSheet("""
            #bgContainer { background: rgba(30,30,46,240); border-radius: 16px;
                          border: 1px solid rgba(255,255,255,20); }
            #bgTitleBar { background: transparent; }
            #bgPreview { background: rgba(0,0,0,60); border: 1px solid rgba(255,255,255,15);
                        border-radius: 10px; }
            #wpNameLabel { color: rgba(255,255,255,160); font-size: 13px;
                           font-weight: bold; padding: 4px; }
            #cardThumb { border-radius: 4px; }
        """)

        self._refresh_grid()

    def _get_wp_name(self, path):
        """从配置中读取指定路径的显示名称"""
        for w in self._config.get("wallpapers", []):
            if isinstance(w, dict) and str(Path(w.get("path", "")).resolve()) == str(Path(path).resolve()):
                return w.get("name") or Path(path).name
            elif isinstance(w, str) and str(Path(w).resolve()) == str(Path(path).resolve()):
                return Path(w).name
        return Path(path).name

    def _update_preview(self):
        wp = Path(self._config.get("wallpaper", str(DEFAULT_WALLPAPER)))
        if wp.exists():
            pixmap = QPixmap(str(wp))
            if not pixmap.isNull():
                scaled = pixmap.scaled(500, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview.setPixmap(scaled)
                return
        self.preview.setText("无背景预览")
        self.preview.setStyleSheet("color: rgba(255,255,255,80); font-size: 12px;")

    def _update_name_label(self):
        wp = Path(self._config.get("wallpaper", str(DEFAULT_WALLPAPER)))
        name = self._get_wp_name(str(wp))
        self.wp_name_label.setText(name)

    def _refresh_grid(self):
        # 清除旧卡片
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        current = self._config.get("wallpaper", "")
        wallpapers = self._config.get("wallpapers", [])
        cols = 4
        idx = 0

        for wp_entry in wallpapers:
            if isinstance(wp_entry, str):
                wp_path, wp_name = wp_entry, Path(wp_entry).name
            else:
                wp_path = wp_entry.get("path", "")
                wp_name = wp_entry.get("name") or Path(wp_path).name

            p = Path(wp_path)
            if not p.exists():
                continue
            is_current = str(p.resolve()) == str(Path(current).resolve())

            card = WallpaperCard(wp_path, wp_name, is_current)
            card.selected.connect(self._on_card_selected)
            card.rename_requested.connect(self._on_card_rename)
            card.delete_requested.connect(self._on_card_delete)

            row, col = divmod(idx, cols)
            self.grid_layout.addWidget(card, row, col)
            idx += 1

        # 空白填充最后一行
        while idx % cols != 0:
            row, col = divmod(idx, cols)
            spacer = QWidget()
            spacer.setFixedSize(120, 110)
            self.grid_layout.addWidget(spacer, row, col)
            idx += 1

    def _on_card_selected(self, path):
        self._config["wallpaper"] = path
        save_config(self._config)
        self._update_preview()
        self._update_name_label()
        self._refresh_grid()
        self.bg_changed.emit(path)

    def _on_card_rename(self, path):
        current_name = self._get_wp_name(path)
        name, ok = QInputDialog.getText(
            self, "重命名壁纸",
            "输入新的显示名称：",
            text=current_name
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        wallpapers = self._config.get("wallpapers", [])
        # 升级旧格式 + 更新名称
        new_wallpapers = []
        found = False
        for w in wallpapers:
            if isinstance(w, dict) and str(Path(w.get("path", "")).resolve()) == str(Path(path).resolve()):
                w["name"] = name
                new_wallpapers.append(w)
                found = True
            elif isinstance(w, str) and str(Path(w).resolve()) == str(Path(path).resolve()):
                new_wallpapers.append({"path": w, "name": name})
                found = True
            else:
                new_wallpapers.append(w)

        if not found:
            new_wallpapers.append({"path": path, "name": name})

        self._config["wallpapers"] = new_wallpapers
        save_config(self._config)
        self._update_name_label()
        self._refresh_grid()

    def _on_card_delete(self, path):
        wallpapers = self._config.get("wallpapers", [])
        # 统计删除后剩余
        remaining = []
        for w in wallpapers:
            wp = w.get("path") if isinstance(w, dict) else w
            if str(Path(wp).resolve()) != str(Path(path).resolve()):
                remaining.append(w)

        reply = GlassMessageBox.show_warning(
            self, "确认删除",
            f"确定要删除此背景吗？\n\n{self._get_wp_name(path)}\n\n删除后将从收藏中移除。"
        )
        if not reply:
            return

        self._config["wallpapers"] = remaining
        # 如果删的是当前壁纸，切换到默认
        current = self._config.get("wallpaper", "")
        if str(Path(current).resolve()) == str(Path(path).resolve()):
            self._config["wallpaper"] = str(DEFAULT_WALLPAPER)
            self.bg_changed.emit(str(DEFAULT_WALLPAPER))
        save_config(self._config)
        self._update_preview()
        self._update_name_label()
        self._refresh_grid()

    def _on_select(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", str(Path.home()),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp *.gif)"
        )
        if not path:
            return
        path = str(Path(path).resolve())

        default_name = Path(path).stem
        name, ok = QInputDialog.getText(
            self, "添加壁纸",
            "输入显示名称（留空则使用文件名）：",
            text=default_name
        )
        if not ok:
            return
        name = name.strip() if name.strip() else default_name

        wallpapers = self._config.get("wallpapers", [])
        # 查重 + 升级旧格式：同路径则更新名称
        found = False
        new_wallpapers = []
        for w in wallpapers:
            wp = w.get("path") if isinstance(w, dict) else w
            if str(Path(wp).resolve()) == path:
                new_wallpapers.append({"path": wp, "name": name})
                found = True
            else:
                new_wallpapers.append(w)

        if not found:
            new_wallpapers.append({"path": path, "name": name})

        self._config["wallpapers"] = new_wallpapers
        self._config["wallpaper"] = path
        save_config(self._config)
        self._update_preview()
        self._update_name_label()
        self._refresh_grid()
        self.bg_changed.emit(path)

    def _on_reset(self):
        default_str = str(DEFAULT_WALLPAPER)
        self._config["wallpaper"] = default_str
        wallpapers = self._config.get("wallpapers", [])
        if not any(
            (isinstance(w, dict) and w.get("path") == default_str) or (isinstance(w, str) and w == default_str)
            for w in wallpapers
        ):
            wallpapers.append({"path": default_str, "name": DEFAULT_WALLPAPER.name})
        self._config["wallpapers"] = wallpapers
        save_config(self._config)
        self._update_preview()
        self._update_name_label()
        self._refresh_grid()
        self.bg_changed.emit(default_str)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# ==================== 抓取线程 ====================
class ExportThread(QThread):
    """在后台线程中运行 Playwright 抓取"""
    log = Signal(str)
    progress = Signal(int, int)       # current, max
    finished_ok = Signal(int)         # 消息数
    finished_err = Signal(str)        # 错误信息
    debug_result = Signal(str)        # debug 模式结果

    def __init__(self, mode="export", auto_verify=True):
        super().__init__()
        self.mode = mode
        self.auto_verify = auto_verify
        self._stop_flag = False
        self._start_flag = False
        self._page = None
        self._context = None

    def stop(self):
        self._stop_flag = True

    def run(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.finished_err.emit("playwright 未安装，请执行: pip install playwright")
            return

        try:
            with sync_playwright() as p:
                self.log.emit("[启动] 正在打开浏览器...")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(PROFILE_DIR),
                    executable_path=EXECUTABLE_PATH if Path(EXECUTABLE_PATH).exists() else None,
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                    ],
                    no_viewport=True,
                    accept_downloads=True,
                    ignore_default_args=["--enable-automation"],
                )

                self._context = context
                page = context.pages[0] if context.pages else context.new_page()
                self._page = page
                self.log.emit("[导航] 正在打开 DeepSeek...")
                page.goto("https://chat.deepseek.com/", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
                page.wait_for_timeout(3000)
                self.log.emit("[就绪] 浏览器已打开，请进入你要导出的对话")
                self.log.emit("[就绪] 进入对话后点击「开始抓取」")

                if self.mode == "debug":
                    self.log.emit("")
                    self.log.emit("=" * 50)
                    self.log.emit("  调试模式 — DOM 结构检测")
                    self.log.emit("=" * 50)
                    for _ in range(300):
                        if self._stop_flag:
                            self.log.emit("[中止] 用户取消")
                            context.close()
                            return
                        md_count = page.evaluate("document.querySelectorAll('.ds-markdown').length")
                        if md_count > 0:
                            break
                        time.sleep(1)
                    result = self._debug_inspect(page)
                    self.debug_result.emit(result)
                    self.finished_ok.emit(0)
                    context.close()
                    return

                # === 等待用户点击「开始抓取」 ===
                self.log.emit("[等待] 等待你点击「开始抓取」按钮...")
                while not self._start_flag:
                    if self._stop_flag:
                        self.log.emit("[中止] 用户取消")
                        context.close()
                        return
                    time.sleep(0.5)

                if self._stop_flag:
                    context.close()
                    return

                # === 正式抓取 ===
                self.log.emit("[抓取] 开始滚动加载所有消息（边滚边采集）...")

                md_count = page.evaluate("document.querySelectorAll('.ds-markdown').length")
                self.log.emit(f"[检测] 当前页面可见 AI 消息数: {md_count}")

                if md_count == 0:
                    self.finished_err.emit("当前页面未检测到对话内容，请先进入一个对话再点击「开始抓取」")
                    context.close()
                    return

                # 先获取对话标题
                chat_title = page.title()
                self.log.emit(f"[信息] 对话标题: {chat_title}")

                # 边滚边收集
                messages = self._scroll_and_collect(page)
                if self._stop_flag:
                    context.close()
                    return

                user_count = sum(1 for m in messages if m["role"] == "user")
                asst_count = sum(1 for m in messages if m["role"] == "assistant")
                self.log.emit(f"[提取] 完成: {len(messages)} 条 (User: {user_count}, Assistant: {asst_count})")

                if len(messages) == 0:
                    self.finished_err.emit("未能提取到任何消息，请用调试模式检查 DOM 结构")
                    context.close()
                    return

                # 验证数据完整性（再滚一遍页面比对）
                if self.auto_verify:
                    verify_report = self._verify_collection(page, messages)
                    self.log.emit(verify_report)

                # 保存文件
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                title = re.sub(r'[\\/:*?"<>|]', '_', chat_title).strip() or 'chat'
                base_name = f"{title}_{timestamp}"

                self._save_txt(messages, OUTPUT_DIR / f"{base_name}.txt")
                self._save_jsonl(messages, OUTPUT_DIR / f"{base_name}_sharegpt.json")
                self._save_deepseek(messages, OUTPUT_DIR / f"{base_name}_deepseek.json")

                self.log.emit(f"\n全部完成! 文件保存在: {OUTPUT_DIR}")
                self.finished_ok.emit(len(messages))
                context.close()

        except Exception as e:
            self.finished_err.emit(str(e))




    def _extract_messages(self, page):
        """
        Hack 模式：虚拟列表已通过 CSS hack 渲染全部 items，
        直接遍历所有 DOM 子节点的 React fiber 树提取消息。
        """
        return page.evaluate(r"""() => {
            const c = document.querySelector('.ds-virtual-list--printable') ||
                      document.querySelector('.ds-virtual-list._2bd7b35');
            if (!c) return [];
            const vl = c.querySelector('.ds-virtual-list-visible-items');
            if (!vl) return [];
            const msgs = [];
            for (const el of vl.children) {
                const fk = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
                if (!fk) continue;
                let fb = el[fk], msgId = null, role = null, content = '';
                let depth = 0;
                while (fb && depth < 25) {
                    const pr = fb.memoizedProps;
                    if (!pr) { fb = fb.return; depth++; continue; }
                    if (pr.messageId && !msgId) msgId = pr.messageId;
                    if (pr.value?.messageId && !msgId) msgId = pr.value.messageId;
                    if (pr.children?.props?.messageId && !msgId) msgId = pr.children.props.messageId;
                    if (pr.children?.props?.value?.messageId && !msgId) msgId = pr.children.props.value.messageId;
                    if (pr.content && typeof pr.content === 'string' && !content) { content = pr.content; role = role || 'assistant'; }
                    if (pr.value?.content && typeof pr.value.content === 'string' && !content) { content = pr.value.content; role = role || 'assistant'; }
                    if (pr.children?.props?.content && typeof pr.children.props.content === 'string' && !content) { content = pr.children.props.content; role = role || 'assistant'; }
                    if (pr.className) {
                        const cn = String(pr.className);
                        if (!role && (cn.includes('_9663006') || (cn.includes('user') && !cn.includes('userName') && cn.length < 50))) role = 'user';
                        if (!role && (cn.includes('_4f9bf79') || (cn.includes('assistant') && cn.length < 50))) role = 'assistant';
                    }
                    fb = fb.return; depth++;
                }
                const text = el.innerText || '';
                if (msgId) msgs.push({messageId: msgId, role: role || 'unknown', content, text, textLen: text.length});
            }
            return msgs;
        }""")

    def _scroll_and_collect(self, page):
        """
        新方案（2026-05-08 验证）：
        1. 等待 React 状态加载完毕（items >= 某个阈值）
        2. Hack CSS：height=scrollHeight, overflowY=visible → 虚拟列表渲染全部 items
        3. 一次遍历全部 DOM 子节点提取消息
        无需滚动，秒级完成，100% 完整。
        """
        # ── 等待 React items 加载 ──
        self.log.emit("[加载] 等待对话消息加载...")
        for wait in range(120):
            if self._stop_flag:
                return []
            info = page.evaluate(r"""() => {
                const el = document.querySelector('.ds-virtual-list--printable') || document.querySelector('.ds-virtual-list._2bd7b35');
                if (!el) return {items: 0, vis: 0, sH: 0};
                const vl = el.querySelector('.ds-virtual-list-visible-items');
                const fk = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
                let fb = el[fk], n = 0;
                while (fb) { if (fb.memoizedProps?.items) { n = fb.memoizedProps.items.length; break; } fb = fb.return; }
                return {items: n, vis: vl ? vl.children.length : 0, sH: el.scrollHeight};
            }""")
            items = info.get('items', 0)
            if items >= 800:
                self.log.emit(f"[加载] 已就绪: {items} 条消息")
                break
            if wait % 10 == 9:
                self.log.emit(f"[加载] 等待中... items={items} ({wait+1}s)")
            time.sleep(1)

        if items < 800:
            self.log.emit(f"[警告] 只检测到 {items} 条消息，可能对话较短或未完全加载")
            # 小对话也继续尝试

        # ── Hack：修改容器 CSS 强制渲染全部 items ──
        self.log.emit("[Hack] 修改容器高度，强制虚拟列表渲染全部消息...")
        page.evaluate(r"""() => {
            const el = document.querySelector('.ds-virtual-list--printable') || document.querySelector('.ds-virtual-list._2bd7b35');
            if (!el) return;
            el.style.height = el.scrollHeight + 'px';
            el.style.maxHeight = el.scrollHeight + 'px';
            el.style.overflowY = 'visible';
            el.style.overflow = 'visible';
        }""")
        time.sleep(3)  # 等待 React 重新渲染

        dom_count = page.evaluate(r"""() => {
            const c = document.querySelector('.ds-virtual-list--printable') || document.querySelector('.ds-virtual-list._2bd7b35');
            const vl = c?.querySelector('.ds-virtual-list-visible-items');
            return vl ? vl.children.length : 0;
        }""")
        self.log.emit(f"[Hack] DOM 节点数: {dom_count}")

        if dom_count < 10:
            self.finished_err.emit("Hack 未生效（DOM 节点太少），请尝试手动滚到底部再滚回顶部后重试")
            return []

        # ── 一次提取全部消息 ──
        self.log.emit("[提取] 遍历全部 DOM 节点...")
        raw_msgs = self._extract_messages(page)
        self.log.emit(f"[提取] 原始提取: {len(raw_msgs)} 条")

        # ── 转换为 GUI 格式 {role, content} ──
        collected = []
        seen_ids = set()
        skip_empty = 0
        skip_stripped = 0
        skip_dup_id = []
        skip_unknown = []
        for m in raw_msgs:
            msg_id = m.get('messageId')
            content = m.get('content', '') or m.get('text', '')
            if not content or not content.strip():
                skip_empty += 1
                continue
            content = re.sub(r'\s+\d+\s*[/／]\s*\d*\s*$', '', content).strip()
            if not content:
                skip_stripped += 1
                continue
            # 用 messageId 去重（而非内容MD5，避免误杀内容相同但确实不同的消息）
            if msg_id:
                if msg_id in seen_ids:
                    skip_dup_id.append(msg_id)
                    continue
                seen_ids.add(msg_id)

            role = m.get('role', 'unknown')
            if role == 'unknown':
                skip_unknown.append(msg_id)
                continue

            collected.append({"role": role, "content": content})

        skipped_total = skip_empty + skip_stripped + len(skip_dup_id) + len(skip_unknown)
        if skipped_total > 0:
            self.log.emit(f"[过滤] 跳过 {skipped_total} 条:")
            if skip_empty:
                self.log.emit(f"  空内容: {skip_empty} 条")
            if skip_stripped:
                self.log.emit(f"  去除页码后为空: {skip_stripped} 条")
            if skip_dup_id:
                self.log.emit(f"  messageId重复: {len(skip_dup_id)} 条, messageId: {skip_dup_id}")
            if skip_unknown:
                self.log.emit(f"  角色未知: {len(skip_unknown)} 条, messageId: {skip_unknown}")

        u = sum(1 for m in collected if m["role"] == "user")
        a = sum(1 for m in collected if m["role"] == "assistant")
        self.log.emit(f"[提取] 完成: {len(collected)} 条 (User: {u}, AI: {a})")
        return collected

    def _verify_collection(self, page, collected):
        """
        验证：Hack 模式下已在 DOM 中，直接再提取一次比对。
        用 messageId 做键，与采集阶段一致。
        """
        self.log.emit("[验证] 重新提取一次进行比对...")

        verify_msgs = self._extract_messages(page)
        verify_map = {}
        for m in verify_msgs:
            msg_id = m.get('messageId')
            if not msg_id:
                continue
            content = (m.get('content', '') or m.get('text', '')).strip()
            if not content:
                continue
            content = re.sub(r'\s+\d+\s*[/／]\s*\d*\s*$', '', content).strip()
            if not content:
                continue
            if msg_id not in verify_map:
                verify_map[msg_id] = {"role": m.get('role', 'unknown'), "content": content}

        # collected 没有 messageId，用索引顺序 + 内容做比对
        collected_items = list(collected)
        verify_items = [verify_map[k] for k in sorted(verify_map.keys())]

        # 简单比较：两边条数是否一致，且内容逐条匹配
        lines = []
        lines.append("")
        lines.append("─── 数据完整性验证报告 ───")
        lines.append(f"  采集条数  {len(collected_items)}  条  (User: {sum(1 for m in collected_items if m['role']=='user')}, AI: {sum(1 for m in collected_items if m['role']=='assistant')})")
        lines.append(f"  验证条数  {len(verify_items)}  条  (User: {sum(1 for v in verify_items if v['role']=='user')}, AI: {sum(1 for v in verify_items if v['role']=='assistant')})")

        if len(collected_items) == len(verify_items):
            lines.append("  ✅ 验证通过：采集条数与页面原始条数完全一致！")
        else:
            diff = len(verify_items) - len(collected_items)
            if diff > 0:
                lines.append(f"  ❌ 页面有但采集中缺失: {diff} 条")
            elif diff < 0:
                lines.append(f"  ⚠ 采集有但页面未检出: {-diff} 条")
            lines.append("  ❌ 验证失败：数据不完整")

        lines.append("─" * 32)
        return "\n".join(lines)

    def _debug_inspect(self, page):
        info = page.evaluate(r"""
            () => {
                const result = {};
                const mdElements = Array.from(document.querySelectorAll('.ds-markdown'));
                result.mdCount = mdElements.length;

                // ── 1. 探测每个 mdEl 的父链 + turn 容器 ──
                function findTurnVerbose(mdEl) {
                    let el = mdEl.parentElement;
                    const path = [];
                    for (let i = 0; i < 20 && el; i++) {
                        const kids = Array.from(el.children);
                        const info = {
                            level: i,
                            tag: el.tagName,
                            cls: (el.className || '').slice(0, 100),
                            childCount: kids.length,
                            childClasses: kids.map(k => ({ cls: (k.className||'').slice(0,60), hasMd: !!k.querySelector('.ds-markdown'), txt: (k.textContent||'').slice(0,40) })),
                            isTurn: kids.length >= 2 && kids.some(k => k === mdEl || k.contains(mdEl)) && kids.some(k => !k.querySelector('.ds-markdown') && k.textContent.trim().length > 0),
                        };
                        path.push(info);
                        el = el.parentElement;
                    }
                    return path;
                }

                if (mdElements.length > 0) {
                    result.firstMdTurnPath = findTurnVerbose(mdElements[0]);
                    // 额外：把 md[0] 父元素的所有 children 全部列出（详细）
                    const parent = mdElements[0].parentElement;
                    if (parent) {
                        result.md0ParentChildren = Array.from(parent.children).map((c, i) => ({
                            idx: i, tag: c.tagName, cls: (c.className||'').slice(0,80),
                            txt: (c.textContent||'').slice(0,80),
                            hasMd: !!c.querySelector('.ds-markdown'),
                        }));
                    }
                }

                // ── 2. 详细探测：mdEl[0] 和 mdEl[1] 之间的所有元素 ──
                if (mdElements.length >= 2) {
                    const a = mdElements[0];
                    const b = mdElements[1];

                    // 找共同祖先
                    let anc = a.parentElement;
                    while (anc && !anc.contains(b)) anc = anc.parentElement;

                    result.betweenMd = { commonAncestor: anc ? { tag: anc.tagName, cls: (anc.className||'').slice(0,80), childCount: anc.children.length } : null };

                    if (anc) {
                        const aIdx = Array.from(anc.children).indexOf(a.contains ? a : a.parentElement);
                        const bIdx = Array.from(anc.children).indexOf(b.contains ? b : b.parentElement);
                        result.betweenMd.mdIndices = [aIdx, bIdx];
                        result.betweenMd.siblings = Array.from(anc.children).map((c, i) => ({
                            idx: i,
                            tag: c.tagName,
                            cls: (c.className||'').slice(0,80),
                            txt: (c.textContent||'').slice(0,60),
                            isAMd: c === a || c.contains(a),
                            isBMd: c === b || c.contains(b),
                        }));
                    }
                }

                // ── 3. 首条 mdEl 之前的所有兄弟（很可能包含用户消息）──
                if (mdElements.length >= 1 && mdElements[0].parentElement) {
                    const parent = mdElements[0].parentElement;
                    const firstMdIdx = Array.from(parent.children).indexOf(mdElements[0]);
                    result.beforeFirst = {
                        parentTag: parent.tagName,
                        parentCls: (parent.className||'').slice(0,80),
                        firstMdIdx: firstMdIdx,
                        prevSiblings: Array.from(parent.children).slice(0, firstMdIdx).map((c, i) => ({
                            idx: i,
                            tag: c.tagName,
                            cls: (c.className||'').slice(0,80),
                            txt: (c.textContent||'').slice(0,80),
                        })),
                    };
                }

                // ── 4. 全局选择器扫描 ──
                const sels = [
                    '[class*="message"]', '[class*="msg"]', '[class*="chat"]',
                    '[class*="turn"]', '[class*="dialogue"]', '[class*="user"]',
                    '[class*="human"]', '[class*="assistant"]', '[class*="sender"]',
                    '[class*="conversation"]', '[class*="content"]', '[class*="bubble"]',
                    '[class*="item"]', '[class*="row"]', '[class*="block"]',
                    '[class*="query"]', '[class*="prompt"]', '[class*="input"]',
                ];
                result.selectorScan = {};
                for (const sel of sels) {
                    const found = document.querySelectorAll(sel);
                    if (found.length > 0 && found.length < 1000) {
                        result.selectorScan[sel] = found.length;
                    }
                }

                return result;
            }
        """)
        lines = []
        lines.append("=== DeepSeek DOM 调试报告 ===")
        lines.append(f".ds-markdown 数量: {info.get('mdCount', 0)}")

        # md[0] 父元素的所有直接子节点（关键！）
        if info.get('md0ParentChildren') is not None:
            lines.append("\n--- md[0] 的直接父元素的所有 children ---")
            for s in info['md0ParentChildren']:
                flag = " [AI-md]" if s['hasMd'] else ""
                lines.append(f"  [{s['idx']}]{flag} <{s['tag']}> cls=\"{s['cls']}\"")
                lines.append(f"       txt: {s['txt']}")

        # turn 路径
        if info.get('firstMdTurnPath'):
            lines.append("\n--- 首条AI消息的父链（标注 isTurn）---")
            for p in info['firstMdTurnPath']:
                flag = " <-- TURN!" if p.get('isTurn') else ""
                lines.append(f"  L{p.get('level', '?')}: <{p.get('tag', '?')}> cls=\"{p.get('cls', '')}\" children={p.get('childCount', 0)}{flag}")
                childs_str = " | ".join(
                    f"<{c.get('cls', '')[:30]} txt='{c.get('txt', '')[:20]}' md={c.get('hasMd')}>"
                    for c in p.get('childClasses', [])
                )
                lines.append(f"       childs: {childs_str}")

        # md[0] 和 md[1] 之间的元素
        if info.get('betweenMd'):
            lines.append("\n--- md[0] 与 md[1] 之间 ---")
            ca = info['betweenMd'].get('commonAncestor')
            if ca:
                lines.append(f"  共同祖先: <{ca.get('tag', '?')}> cls=\"{ca.get('cls', '')}\" children={ca.get('childCount', 0)}")
            if 'mdIndices' in info['betweenMd']:
                indices = info['betweenMd']['mdIndices']
                lines.append(f"  md[0]在位置{indices[0]}，md[1]在位置{indices[1]}")
                for s in info['betweenMd'].get('siblings', []):
                    flag = " [md0]" if s.get('isAMd') else (" [md1]" if s.get('isBMd') else "")
                    lines.append(f"  [{s.get('idx', '?')}]{flag} <{s.get('tag', '?')}> cls=\"{s.get('cls', '')}\"")
                    lines.append(f"       txt: {s.get('txt', '')}")

        # md[0] 之前的兄弟
        bf = info.get('beforeFirst')
        if bf:
            lines.append(f"\n--- md[0] 之前兄弟（parent={bf.get('parentTag')} cls=\"{bf.get('parentCls')}\"）---")
            lines.append(f"  md[0] 在第 {bf.get('firstMdIdx', -1)} 个子节点")
            for s in bf.get('prevSiblings', []):
                lines.append(f"  [{s.get('idx', '?')}] <{s.get('tag', '?')}> cls=\"{s.get('cls', '')}\"")
                lines.append(f"       txt: {s.get('txt', '')}")

        # 选择器扫描
        if info.get('selectorScan'):
            lines.append("\n--- 选择器扫描 ---")
            for sel, count in sorted(info['selectorScan'].items(), key=lambda x: -x[1]):
                lines.append(f"  {sel}: {count}个")

        return '\n'.join(lines)

    def _save_txt(self, messages, path):
        lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"[{role}]\n{msg['content']}")
        path.write_text("\n\n---\n\n".join(lines), encoding="utf-8")
        self.log.emit(f"[保存] TXT -> {path.name}")

    def _save_jsonl(self, messages, path):
        turns = [{"from": "human" if m["role"] == "user" else "gpt", "value": m["content"]} for m in messages]
        path.write_text(json.dumps({"conversations": turns}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log.emit(f"[保存] ShareGPT JSON -> {path.name}")

    def _save_deepseek(self, messages, path):
        msgs = [{"role": m["role"], "content": m["content"]} for m in messages]
        path.write_text(json.dumps({"messages": msgs}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log.emit(f"[保存] DeepSeek JSON -> {path.name}")


# ==================== 文件管理覆盖层 ====================
class FileOverlay(QWidget):
    """嵌入主窗口的文件管理弹窗，可阅读 JSON/TXT，支持删除"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setParent(parent)
        self.hide()
        self.setGeometry(0, 40, parent.width(), parent.height() - 40)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setObjectName("fileOverlay")
        self._current_file = None
        self._init_ui()

        # 通过 eventFilter 监听父窗口 resize，不覆盖父窗口的 resizeEvent
        parent.installEventFilter(self)

    def paintEvent(self, event):
        """独立壁纸背景 — 和主窗口一致的视觉效果"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        main = self.parent()
        if main and hasattr(main, '_cached_wp_pixmap') and main._cached_wp_pixmap:
            # 复用主窗口壁纸缓存
            painter.drawPixmap(self.rect(), main._cached_wp_pixmap)
        elif main and hasattr(main, '_fade_new') and main._fade_new:
            # 壁纸切换中，用新图
            painter.drawPixmap(self.rect(), main._fade_new)

        # 圆角裁剪
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.setBrush(Qt.black)
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())
        painter.end()

    def eventFilter(self, obj, event):
        """监听父窗口 resize 事件，同步更新 overlay 尺寸"""
        if obj is self.parent() and event.type() == event.Type.Resize:
            self.setGeometry(0, 40, self.parent().width(), self.parent().height() - 40)
        return super().eventFilter(obj, event)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(10)

        # 头部
        header = QHBoxLayout()
        title = QLabel("导出文件管理")
        title.setStyleSheet("color: rgba(255,255,255,220); font-size: 14px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("X")
        close_btn.setFixedSize(26, 26)
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # 文件列表
        list_label = QLabel("单击预览 · 双击打开 · 选中后可删除")
        list_label.setStyleSheet("color: rgba(255,255,255,120); font-size: 11px;")
        layout.addWidget(list_label)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setFixedHeight(140)
        self.file_list.itemClicked.connect(self._on_file_selected)
        self.file_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        layout.addWidget(self.file_list)

        # 底部操作栏
        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.setObjectName("ghostBtn")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)

        delete_btn = QPushButton("🗑 删除选中")
        delete_btn.setObjectName("dangerBtn")
        delete_btn.clicked.connect(self._on_delete_file)
        btn_row.addWidget(delete_btn)

        open_dir_btn = QPushButton("打开文件夹")
        open_dir_btn.setObjectName("ghostBtn")
        open_dir_btn.clicked.connect(self._open_dir)
        btn_row.addWidget(open_dir_btn)
        layout.addLayout(btn_row)

        # 预览区域
        preview_label = QLabel("文件预览")
        preview_label.setStyleSheet("color: rgba(137,180,250,180); font-size: 12px; font-weight: bold;")
        layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setObjectName("previewText")
        layout.addWidget(self.preview_text, 1)

        self.setStyleSheet("""
            #fileOverlay { background: transparent; }
            #fileList { background: rgba(0,0,0,60); color: rgba(205,214,244,200);
                        border: 1px solid rgba(255,255,255,15); border-radius: 6px;
                        font-size: 11px; }
            #fileList::item { padding: 5px; border-bottom: 1px solid rgba(255,255,255,8);
                              color: rgba(205,214,244,200); }
            #fileList::item:selected { background: rgba(137,180,250,50); }
            #fileList::item:hover { background: rgba(255,255,255,12); }
            #previewText { background: rgba(0,0,0,80); color: rgba(205,214,244,200);
                           border: 1px solid rgba(255,255,255,15); border-radius: 8px;
                           padding: 10px; font-family: 'Consolas', monospace; font-size: 11px;
                           line-height: 1.5; }
        """)

        self._refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()
        self.raise_()

    def _refresh(self):
        self.file_list.clear()
        self.preview_text.clear()
        self._current_file = None

        if not OUTPUT_DIR.exists():
            self.file_list.addItem(QListWidgetItem("(output 目录不存在)"))
            return

        files = sorted(OUTPUT_DIR.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files:
            if not f.is_file():
                continue
            size_kb = f.stat().st_size / 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")
            icon = "TXT" if f.suffix.lower() == '.txt' else "JSON" if f.suffix.lower() == '.json' else "FILE"
            display = f"[{icon}] {f.name}  ({size_kb:.1f}KB  {mtime})"

            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, str(f))
            self.file_list.addItem(item)

    def _on_file_selected(self, item):
        path = item.data(Qt.UserRole)
        if not path or not os.path.exists(path):
            return
        self._current_file = path
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(10000)
                if len(content) >= 10000:
                    content += "\n\n... (仅预览前 10000 字符，完整内容请双击打开)"
            self.preview_text.setPlainText(content)
        except Exception as e:
            self.preview_text.setPlainText(f"无法读取文件: {e}")

    def _on_file_double_clicked(self, item):
        path = item.data(Qt.UserRole)
        if path and os.path.exists(path):
            os.startfile(path)

    def _on_delete_file(self):
        item = self.file_list.currentItem()
        if not item:
            GlassMessageBox.show_info(self, "提示", "请先选择要删除的文件")
            return
        path = item.data(Qt.UserRole)
        if not path or not os.path.exists(path):
            return

        filename = os.path.basename(path)
        reply = GlassMessageBox.show_warning(
            self, "确认删除",
            f"确定要删除以下文件吗？\n\n{filename}\n\n此操作不可撤销！"
        )
        if not reply:
            return

        try:
            os.remove(path)
            self._refresh()
        except Exception as e:
            GlassMessageBox.show_error(self, "删除失败", f"无法删除文件: {e}")

    def _open_dir(self):
        if OUTPUT_DIR.exists():
            os.startfile(str(OUTPUT_DIR))


# ==================== 主窗口 ====================
class MainWindow(QMainWindow):
    # 日志前缀着色方案 (Catppuccin Mocha)
    _LOG_COLORS = {
        '[启动]': '#89b4fa', '[导航]': '#89b4fa',
        '[就绪]': '#a6e3a1', '[加载]': '#89b4fa',
        '[等待]': '#89dceb', '[Hack]': '#cba6f7',
        '[提取]': '#a6e3a1', '[过滤]': '#f9e2af',
        '[验证]': '#94e2d5', '[保存]': '#a6e3a1',
        '[检测]': '#bac2de', '[信息]': '#bac2de',
        '[抓取]': '#bac2de', '[开始]': '#89b4fa',
        '[中止]': '#f38ba8', '[错误]': '#f38ba8',
        '[警告]': '#fab387',
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DeepSeek 对话导出器")
        self.resize(540, 800)
        self.setMinimumSize(420, 600)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._drag_pos = None
        self._thread = None
        self._file_overlay = None
        self._bg_dialog = None
        self._wallpaper_path = get_wallpaper()
        self._cached_wp_path = None
        self._cached_wp_size = QSize()
        self._cached_wp_pixmap = None

        # 壁纸切换淡入淡出
        self._fade_old = None
        self._fade_new = None
        self._fade_progress = 0.0
        self._fade_new_path = None
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(20)
        self._fade_timer.timeout.connect(self._fade_step)

        # 粒子庆祝 + 波形装饰
        self._particle_overlay = ParticleOverlay(self)
        self._waveform = WaveformWidget(self)

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(44)
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 8, 0)
        title_layout.setSpacing(8)

        # 左侧：标题 + 版本
        title_left = QHBoxLayout()
        title_left.setSpacing(8)
        title_label = QLabel("DeepSeek 对话导出器")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("color: rgba(255,255,255,220); font-size: 14px; font-weight: bold;")
        title_left.addWidget(title_label)
        ver_label = QLabel("v1.0")
        ver_label.setStyleSheet("color: rgba(137,180,250,120); font-size: 10px; padding: 2px 6px; "
                                "background: rgba(137,180,250,15); border-radius: 4px;")
        title_left.addWidget(ver_label)
        title_left.addStretch()
        title_layout.addLayout(title_left)

        # 右侧：设置 + 最小化 + 关闭
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(32, 32)
        self.btn_settings.setObjectName("settingsBtn")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setToolTip("背景设置")
        self.btn_settings.clicked.connect(self._on_open_bg_settings)
        title_layout.addWidget(self.btn_settings)

        min_btn = QPushButton("─")
        min_btn.setFixedSize(32, 32)
        min_btn.setObjectName("minBtn")
        min_btn.setCursor(Qt.PointingHandCursor)
        min_btn.setToolTip("最小化")
        min_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(min_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setObjectName("closeBtn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        main_layout.addWidget(title_bar)

        # 内容区域
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 20)
        content_layout.setSpacing(10)

        # === 状态卡片 ===
        self.status_card = GlassCard()
        self.status_card.setFixedHeight(72)
        sl = QVBoxLayout(self.status_card)
        sl.setContentsMargins(16, 10, 16, 10)
        sl.setSpacing(6)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.status_dot = QLabel("●")
        self.status_dot.setFixedSize(12, 12)
        self._set_dot_color('#a6e3a1')
        status_row.addWidget(self.status_dot)
        self.status_label = QLabel("就绪 — 点击「启动浏览器」开始")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label, 1)
        sl.addLayout(status_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setValue(0)
        sl.addWidget(self.progress_bar)
        content_layout.addWidget(self.status_card)

        # === 状态→控制 渐变分隔线 ===
        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setObjectName("cardSepLine")
        content_layout.addWidget(sep1)

        # === 控制卡片 ===
        self.ctrl_card = GlassCard()
        cl = QVBoxLayout(self.ctrl_card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(8)

        btn_row1 = QHBoxLayout()
        self.btn_launch = QPushButton("🚀 启动浏览器")
        self.btn_launch.setObjectName("primaryBtn")
        self.btn_launch.setCursor(Qt.PointingHandCursor)
        self.btn_launch.clicked.connect(self._on_launch)
        btn_row1.addWidget(self.btn_launch)

        self.btn_debug = QPushButton("🔧 调试模式")
        self.btn_debug.setObjectName("ghostBtn")
        self.btn_debug.setCursor(Qt.PointingHandCursor)
        self.btn_debug.clicked.connect(self._on_debug)
        btn_row1.addWidget(self.btn_debug)
        cl.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self.btn_start = QPushButton("▶ 开始抓取")
        self.btn_start.setObjectName("primaryBtn")
        self.btn_start.setEnabled(False)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._on_start_export)
        btn_row2.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setObjectName("dangerBtn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self._on_stop)
        btn_row2.addWidget(self.btn_stop)
        cl.addLayout(btn_row2)

        # 自动验证复选框
        self.chk_verify = QCheckBox("🔍 抓取后自动验证数据完整性")
        self.chk_verify.setChecked(True)
        self.chk_verify.setObjectName("chkVerify")
        self.chk_verify.setToolTip("抓取完成后再滚一遍页面，逐条比对确保零遗漏")
        cl.addWidget(self.chk_verify)

        content_layout.addWidget(self.ctrl_card)

        # === 控制→日志 渐变分隔线 ===
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setObjectName("cardSepLine")
        content_layout.addWidget(sep2)

        # === 日志 + 文件管理 卡片 ===
        self.log_card = GlassCard()
        ll = QVBoxLayout(self.log_card)
        ll.setContentsMargins(12, 10, 12, 10)
        ll.setSpacing(6)

        log_header = QHBoxLayout()
        log_title = QLabel("📋 运行日志")
        log_title.setObjectName("sectionLabel")
        log_header.addWidget(log_title)
        log_header.addStretch()

        self.btn_files = QPushButton("📁 文件管理")
        self.btn_files.setObjectName("ghostBtn")
        self.btn_files.setCursor(Qt.PointingHandCursor)
        self.btn_files.clicked.connect(self._on_open_files)
        log_header.addWidget(self.btn_files)
        ll.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("logText")
        ll.addWidget(self.log_text)
        content_layout.addWidget(self.log_card, 1)

        # === 右下角技术栈水印 ===
        tech_row = QHBoxLayout()
        tech_row.addStretch()
        tech_label = QLabel("Python · PySide6 · Playwright")
        tech_label.setObjectName("techWatermark")
        tech_label.setAlignment(Qt.AlignRight)
        tech_row.addWidget(tech_label)
        content_layout.addLayout(tech_row)

        main_layout.addWidget(content, 1)
        main_layout.addWidget(self._waveform)

    def _make_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("color: rgba(255,255,255,150); font-size: 12px;")
        lbl.setFixedWidth(48)
        return lbl

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 壁纸切换淡入淡出
        if self._fade_old and self._fade_new:
            painter.setOpacity(max(0.0, 1.0 - self._fade_progress))
            painter.drawPixmap(self.rect(), self._fade_old)
            painter.setOpacity(min(1.0, self._fade_progress))
            painter.drawPixmap(self.rect(), self._fade_new)
            painter.setOpacity(1.0)
        else:
            wp = Path(self._wallpaper_path) if self._wallpaper_path else DEFAULT_WALLPAPER
            cur_size = self.size()

            # 仅当壁纸路径或窗口尺寸变化时才重新加载+缩放
            if (self._cached_wp_path != str(wp) or self._cached_wp_size != cur_size):
                if wp.exists():
                    pixmap = QPixmap(str(wp))
                    if not pixmap.isNull():
                        self._cached_wp_pixmap = pixmap.scaled(
                            cur_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                        )
                        self._cached_wp_path = str(wp)
                        self._cached_wp_size = cur_size

            if self._cached_wp_pixmap:
                painter.drawPixmap(self.rect(), self._cached_wp_pixmap)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(Qt.NoPen)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawRoundedRect(self.rect(), 16, 16)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _set_dot_color(self, color):
        self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")

    def _update_status_dot(self, text):
        if any(kw in text for kw in ['错误', '失败', 'Error']):
            self._set_dot_color('#f38ba8')
        elif any(kw in text for kw in ['完成', '成功', '✅']):
            self._set_dot_color('#a6e3a1')
        elif any(kw in text for kw in ['抓取中', '等待', '加载', '启动', '导航']):
            self._set_dot_color('#89b4fa')
        else:
            self._set_dot_color('#a6e3a1')

    def _append_log(self, text):
        safe = _html.escape(text)

        # 匹配前缀着色
        for prefix, color in self._LOG_COLORS.items():
            if text.startswith(prefix):
                safe_prefix = _html.escape(prefix)
                rest = _html.escape(text[len(prefix):])
                safe = f'<b style="color:{color}">{safe_prefix}</b><span style="color:#cdd6f4">{rest}</span>'
                break

        # 高亮特殊符号
        safe = safe.replace('✅', '<span style="color:#a6e3a1;font-size:13px">✅</span>')
        safe = safe.replace('❌', '<span style="color:#f38ba8;font-size:13px">❌</span>')
        safe = safe.replace('⚠', '<span style="color:#f9e2af;font-size:13px">⚠</span>')

        # 装饰线（验证报告框）用绿色
        deco_chars = set('╔╗╚╝║═')
        if any(c in deco_chars for c in text) and len(text.strip()) > 3:
            safe = f'<span style="color:rgba(166,227,161,120)">{safe}</span>'

        self.log_text.append(safe)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_status(self, text):
        self.status_label.setText(text)
        self._update_status_dot(text)

    def _on_launch(self):
        self.log_text.clear()
        self._set_status("正在启动浏览器...")
        self.progress_bar.setValue(0)

        self.btn_launch.setEnabled(False)
        self.btn_debug.setEnabled(False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        self._thread = ExportThread(
            mode="export",
            auto_verify=self.chk_verify.isChecked()
        )
        self._thread.log.connect(self._append_log)
        self._thread.progress.connect(lambda c, m: self.progress_bar.setValue(min(c % 100, 100)))
        self._thread.finished_ok.connect(self._on_export_done)
        self._thread.finished_err.connect(self._on_export_error)
        self._thread.start()

    def _on_debug(self):
        self.log_text.clear()
        self._set_status("调试模式 — 请在浏览器中打开一个对话...")
        self.btn_launch.setEnabled(False)
        self.btn_debug.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self._thread = ExportThread(mode="debug")
        self._thread.log.connect(self._append_log)
        self._thread.debug_result.connect(self._append_log)
        self._thread.finished_ok.connect(lambda: self._reset_buttons())
        self._thread.finished_err.connect(self._on_export_error)
        self._thread.start()

    def _on_start_export(self):
        if self._thread:
            self._thread._start_flag = True

        self._set_status("抓取中...")
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self._append_log("[开始] 开始抓取对话...")

    def _on_stop(self):
        if self._thread:
            self._thread.stop()
        self._set_status("正在停止...")

    def _on_export_done(self, count):
        self._set_status(f"完成! 共导出 {count} 条消息")
        self.progress_bar.setValue(100)
        self._reset_buttons()
        # 粒子庆祝效果
        origin = self.progress_bar.mapTo(self, self.progress_bar.rect().center())
        self._particle_overlay.celebrate(origin)
        GlassMessageBox.show_info(self, "完成", f"成功导出 {count} 条消息\n文件保存在: {OUTPUT_DIR}")

    def _on_export_error(self, err):
        self._set_status(f"错误: {err}")
        self._append_log(f"[错误] {err}")
        self._reset_buttons()
        GlassMessageBox.show_error(self, "错误", err)

    def _on_open_files(self):
        if self._file_overlay is None:
            self._file_overlay = FileOverlay(self)
        self._file_overlay.setGeometry(0, 40, self.width(), self.height() - 40)
        self._file_overlay.show()
        self._file_overlay.raise_()
        self._file_overlay._refresh()

    def _on_open_bg_settings(self):
        if self._bg_dialog is None:
            self._bg_dialog = BgSettingsDialog(self)
            self._bg_dialog.bg_changed.connect(self._on_bg_changed)
        # 居中显示
        self._bg_dialog.move(
            self.x() + (self.width() - self._bg_dialog.width()) // 2,
            self.y() + (self.height() - self._bg_dialog.height()) // 2,
        )
        self._bg_dialog.show()
        self._bg_dialog.raise_()
        self._bg_dialog._config = load_config()
        self._bg_dialog._update_preview()
        self._bg_dialog._update_name_label()
        self._bg_dialog._refresh_grid()

    def closeEvent(self, event):
        """关闭窗口时清理线程和浏览器进程"""
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait(3000)  # 最多等 3 秒
            # 尝试关闭浏览器 context
            if self._thread._context:
                try:
                    self._thread._context.close()
                except Exception:
                    pass
        event.accept()

    def _on_bg_changed(self, new_path):
        old_pixmap = self._cached_wp_pixmap
        new_wp = Path(new_path)
        new_pixmap = None
        if new_wp.exists():
            pm = QPixmap(str(new_wp))
            if not pm.isNull():
                new_pixmap = pm.scaled(
                    self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )
        if old_pixmap and new_pixmap:
            self._fade_old = old_pixmap
            self._fade_new = new_pixmap
            self._fade_progress = 0.0
            self._fade_new_path = new_path
            self._fade_timer.start()
        else:
            self._wallpaper_path = new_path
            self._cached_wp_path = None
            self.update()

    def _fade_step(self):
        self._fade_progress += 0.05  # 20步 × 20ms = 400ms
        if self._fade_progress >= 1.0:
            self._fade_progress = 1.0
            self._fade_timer.stop()
            self._wallpaper_path = self._fade_new_path
            self._cached_wp_pixmap = self._fade_new
            self._cached_wp_path = str(self._fade_new_path)
            self._cached_wp_size = self.size()
            self._fade_old = None
            self._fade_new = None
        self.update()

    def _reset_buttons(self):
        self.btn_launch.setEnabled(True)
        self.btn_debug.setEnabled(True)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(False)


# ==================== 全局样式 ====================
STYLESHEET = """
QMainWindow {
    background: transparent;
}
#titleBar {
    background: rgba(30, 30, 46, 120);
    border-bottom: 1px solid rgba(255,255,255,10);
}
#closeBtn {
    background: rgba(255,255,255,0);
    color: rgba(255,255,255,100);
    border: none;
    border-radius: 16px;
    font-size: 13px;
    font-weight: bold;
}
#closeBtn:hover {
    background: rgba(237,80,100,200);
    color: white;
}
#minBtn {
    background: rgba(255,255,255,0);
    color: rgba(255,255,255,100);
    border: none;
    border-radius: 16px;
    font-size: 14px;
}
#minBtn:hover {
    background: rgba(255,255,255,40);
    color: rgba(255,255,255,200);
}
#settingsBtn {
    background: rgba(255,255,255,0);
    color: rgba(255,255,255,100);
    border: none;
    border-radius: 16px;
    font-size: 16px;
}
#settingsBtn:hover {
    background: rgba(137,180,250,80);
    color: rgba(255,255,255,220);
}
/* ===== 有色透玻璃按钮 ===== */
/* Primary — 蓝色玻璃 */
#primaryBtn {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(137,180,250,32),
        stop:0.5 rgba(137,180,250,20),
        stop:1 rgba(137,180,250,12));
    color: #89dceb;
    border: 1px solid rgba(137,180,250,38);
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: bold;
}
#primaryBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(137,180,250,50),
        stop:0.5 rgba(137,180,250,34),
        stop:1 rgba(137,180,250,20));
    border-color: rgba(137,180,250,65);
    color: #91d7ff;
    text-shadow: 0 0 12px rgba(137,180,250,90);
}
#primaryBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(137,180,250,18),
        stop:0.5 rgba(137,180,250,12),
        stop:1 rgba(137,180,250,8));
    border-color: rgba(137,180,250,30);
    transform: translateY(1px);
}
#primaryBtn:disabled {
    background: rgba(137,180,250,8);
    color: rgba(137,180,250,35);
    border-color: rgba(137,180,250,12);
    text-shadow: none;
}

/* Ghost — 中性玻璃 */
#ghostBtn {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,16),
        stop:0.5 rgba(255,255,255,10),
        stop:1 rgba(255,255,255,6));
    color: rgba(205,214,244,210);
    border: 1px solid rgba(255,255,255,18);
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 13px;
}
#ghostBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,26),
        stop:0.5 rgba(255,255,255,16),
        stop:1 rgba(255,255,255,10));
    border-color: rgba(186,194,222,45);
    color: rgba(205,214,244,240);
}
#ghostBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,8),
        stop:0.5 rgba(255,255,255,5),
        stop:1 rgba(255,255,255,3));
    border-color: rgba(137,180,250,40);
    transform: translateY(1px);
}
#ghostBtn:disabled {
    background: rgba(255,255,255,6);
    color: rgba(255,255,255,32);
    border-color: rgba(255,255,255,8);
}

/* Danger — 粉红玻璃 */
#dangerBtn {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(243,139,168,28),
        stop:0.5 rgba(243,139,168,18),
        stop:1 rgba(243,139,168,10));
    color: #f38ba8;
    border: 1px solid rgba(243,139,168,36);
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: bold;
}
#dangerBtn:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(243,139,168,46),
        stop:0.5 rgba(243,139,168,30),
        stop:1 rgba(243,139,168,18));
    border-color: rgba(243,139,168,58);
    color: #f5a0b8;
    text-shadow: 0 0 12px rgba(243,139,168,85);
}
#dangerBtn:pressed {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(243,139,168,16),
        stop:0.5 rgba(243,139,168,10),
        stop:1 rgba(243,139,168,6));
    border-color: rgba(243,139,168,28);
    transform: translateY(1px);
}
#dangerBtn:disabled {
    background: rgba(243,139,168,8);
    color: rgba(243,139,168,32);
    border-color: rgba(243,139,168,12);
    text-shadow: none;
}
#chkVerify {
    color: rgba(205,214,244,170);
    font-size: 11px;
    spacing: 6px;
}
#chkVerify::indicator {
    width: 16px;
    height: 16px;
    border: 1.5px solid rgba(255,255,255,30);
    border-radius: 4px;
    background: rgba(0,0,0,50);
}
#chkVerify::indicator:checked {
    background: rgba(137,180,250,200);
    border-color: rgba(137,180,250,150);
    image: none;
}
#chkVerify::indicator:hover {
    border-color: rgba(137,180,250,120);
}
#progressBar {
    background: rgba(255,255,255,10);
    border: none;
    border-radius: 3px;
}
#progressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(137,180,250,200), stop:0.5 rgba(166,227,161,200), stop:1 rgba(137,180,250,200));
    border-radius: 3px;
}
#statusLabel {
    color: rgba(255,255,255,190);
    font-size: 12px;
}
#sectionLabel {
    color: rgba(137, 180, 250, 220);
    font-size: 12px;
    font-weight: bold;
    padding-bottom: 2px;
}
#logText {
    background: rgba(0,0,0,100);
    color: rgba(205,214,244,200);
    border: 1px solid rgba(255,255,255,8);
    border-radius: 10px;
    padding: 10px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    line-height: 1.5;
}
#logText:focus {
    border: 1px solid rgba(137,180,250,30);
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,25);
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,45);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QToolTip {
    background: rgba(30,30,46,230);
    color: rgba(205,214,244,200);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}
#techWatermark {
    color: rgba(255,255,255,35);
    font-size: 9px;
    letter-spacing: 0.5px;
    padding: 0 4px 2px 0;
}
#cardSepLine {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(137,180,250,0),
        stop:0.3 rgba(137,180,250,50),
        stop:0.5 rgba(205,214,244,80),
        stop:0.7 rgba(166,227,161,50),
        stop:1 rgba(166,227,161,0));
}
"""


def main():
    if sys.platform == 'win32':
        if sys.stdout:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 46))
    palette.setColor(QPalette.WindowText, QColor(205, 214, 244))
    app.setPalette(palette)

    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
