from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from src.asset_manager import get_asset
from src.chatbot import get_sparkle_font


COMBO_DISPLAY_AFTER_LANDING_MS = 5000


class ComboBubble(QWidget):
    def __init__(self, parent=None, *, scale=6):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.score = 0
        self.scale = scale
        self.sprite = QPixmap(str(get_asset("combo/combo.png")))
        if self.sprite.isNull():
            raise RuntimeError("Impossible de charger la bulle de combo.")
        self.score_label = QLabel(self)
        self.score_label.setFont(get_sparkle_font())
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score_label.setStyleSheet(
            "color: #202020; background: transparent; border: none; padding: 0;"
        )
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.hide_timer.timeout.connect(self.reset)
        self._update_score()

    @property
    def has_score(self):
        return self.score > 0 or self.hide_timer.isActive()

    def add_point(self):
        self.hide_timer.stop()
        self.score += 1
        self._update_score()
        if self.parentWidget() is not None and self.parentWidget().isVisible():
            self.show_for(self.parentWidget())

    def finish(self):
        if self.score > 0:
            # Reset the next run immediately, leaving the final value on screen.
            self.score = 0
            self.hide_timer.start(COMBO_DISPLAY_AFTER_LANDING_MS)

    def reset(self):
        self.hide_timer.stop()
        self.score = 0
        self._update_score()
        self.hide()

    def _update_score(self):
        text = str(self.score)
        padding = self.scale
        width = max(self.sprite.width() * self.scale,
                    self.score_label.fontMetrics().horizontalAdvance(text) + padding * 2)
        height = self.sprite.height() * self.scale
        self.setFixedSize(width, height)
        self.score_label.setGeometry(padding, padding, width - padding * 2, height - padding * 2)
        self.score_label.setText(text)
        self.setAccessibleName(f"Combo : {self.score}")
        self.update()
        if self.parentWidget() is not None:
            self.position_for(self.parentWidget())

    def position_for(self, sparkle):
        overlap = self.scale * 2
        position = sparkle.mapToGlobal(
            QPoint(sparkle.width() - overlap, -self.height() + overlap)
        )
        screen = QGuiApplication.screenAt(sparkle.mapToGlobal(sparkle.rect().center()))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        position.setX(max(area.left(), min(position.x(), area.right() - self.width() + 1)))
        position.setY(max(area.top(), min(position.y(), area.bottom() - self.height() + 1)))
        self.move(position)

    def show_for(self, sparkle):
        self.position_for(sparkle)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(self.rect(), self.sprite)
        painter.end()
