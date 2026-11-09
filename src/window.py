from PySide6.QtWidgets import QApplication, QWidget, QLabel
from PySide6.QtGui import QPainter, QPixmap, QTransform
from PySide6.QtCore import Qt, QTimer, Slot
from time import perf_counter

from src.asset_manager import get_asset
from src.animation import AnimationController
from src.control import KeyboardController
from src.physics import Physics
from src.chatbot import ChatBubble, ChatbotService
from src.cff import CffBubble, CffService
from src.combo import ComboBubble
from src.sound import SoundController

# Window class for the sparkle pet application.

class SparkleWindow(QWidget):
    def __init__(self, physics: Physics):
        super().__init__()        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.physics = physics
        self.keyboard_controller = KeyboardController()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.scale = 6
        self.drag_offset = None
        self.last_drag_position = None
        self.last_drag_time = None
        self.click_position = None
        self.drag_started = False
        self.double_click = False
        self.single_click_timer = QTimer(self)
        self.single_click_timer.setSingleShot(True)
        self.single_click_timer.timeout.connect(self.toggle_chatbox)

        self.pet_label = QLabel(self)
        self.pet_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.current_image = None
        self.base_pixmap = None
        self.animation_controller = AnimationController()
        self.sounds = SoundController(self)
        self.chatbot = ChatbotService()
        self.chatbox = ChatBubble()
        self.chatbox.submitted.connect(self.chatbot.ask)
        self.chatbot.response_ready.connect(
            self.chatbox.answer_label.setPlainText
        )
        self.chatbot.answer_received.connect(self._play_talk_sound)
        self.cff_service = CffService(self)
        self.cff_bubble = CffBubble(self)
        self.cff_service.response_ready.connect(self.cff_bubble.answer_label.setPlainText)
        self.cff_bubble.search_requested.connect(self.cff_service.refresh)
        self.cff_bubble.search_invalidated.connect(self.cff_service.cancel)
        self.cff_service.itinerary_received.connect(self._play_cff_sound)
        self.combo_bubble = ComboBubble(self, scale=self.scale)
        self.set_image("idle/normal/idle_left_down.png")

    def update_animation(self, dt: float, cursor_x: float, cursor_y: float):
        self.animation_controller.set_cff_active(
            self.cff_bubble.isVisible(), getattr(self.cff_bubble, "side", "right")
        )
        image_name = self.animation_controller.update(
            dt,
            self.x(),
            self.y(),
            self.width(),
            self.height(),
            cursor_x,
            cursor_y,
            self.physics.is_airborne(),
            self.physics.velocity_x,
            self.physics.velocity_y,
            self.physics.cursor_hit_triggered,
            self.physics.landed_triggered,
            self.physics.crush_triggered,
            self.physics.crush_held,
        )
        if not self.chatbox.isVisible() and not self.cff_bubble.isVisible():
            if self.physics.cursor_hit_triggered:
                self.combo_bubble.add_point()
            if self.physics.landed_triggered:
                self.combo_bubble.finish()
        if self.physics.landed_triggered:
            self.sounds.play("crush")
        if self.physics.edge_hit_triggered or self.physics.cursor_hit_triggered:
            self.sounds.play("glass")
        if self.animation_controller.special_state_triggered:
            self.sounds.play("shine")
        if image_name != self.current_image:
            self.set_image(image_name)
        self.set_rotation(self.animation_controller.salto_angle)

    @Slot()
    def _play_talk_sound(self):
        if self.isVisible():
            self.sounds.play("talk")

    @Slot()
    def _play_cff_sound(self):
        if self.isVisible() and self.cff_bubble.isVisible():
            self.sounds.play("cff")

    def set_image(self, name: str):  
        image_path = get_asset(name)

        pixmap = QPixmap(str(image_path))

        if pixmap.isNull():
            raise RuntimeError(f"Impossible de charger : {image_path}")

        pixmap = pixmap.scaled(
            pixmap.width() * self.scale,
            pixmap.height() * self.scale,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )

        self.base_pixmap = pixmap
        self.pet_label.setPixmap(pixmap)
        self.current_image = name

        self.pet_label.resize(pixmap.size())
        self.resize(pixmap.size())

    def set_rotation(self, angle: float):
        if self.base_pixmap is None:
            return

        if angle == 0:
            self.pet_label.setPixmap(self.base_pixmap)
            return

        rotated = self.base_pixmap.transformed(
            QTransform().rotate(angle),
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(self.base_pixmap.size())
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawPixmap(
            (canvas.width() - rotated.width()) // 2,
            (canvas.height() - rotated.height()) // 2,
            rotated,
        )
        painter.end()
        self.pet_label.setPixmap(canvas)

    def set_position(self, x: int, y: int):
        self.move(x, y)
        if self.cff_bubble.isVisible():
            self.cff_bubble.position_for(self)

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "combo_bubble"):
            self.combo_bubble.position_for(self)

    def showEvent(self, event):
        super().showEvent(event)
        if self.combo_bubble.has_score:
            self.combo_bubble.show_for(self)

    def hideEvent(self, event):
        self.combo_bubble.hide()
        super().hideEvent(event)

    def hide_bubbles(self):
        self.chatbox.hide()
        self.cff_bubble.hide()
        self.animation_controller.set_chat_active(False)

    def toggle_chatbox(self):
        if self.chatbox.isVisible() or self.cff_bubble.isVisible():
            self.hide_bubbles()
        else:
            self.combo_bubble.reset()
            self.chatbox.show_for(self)
            self.animation_controller.set_chat_active(True, self.chatbox.side)

    def show_cff(self):
        self.combo_bubble.reset()
        self.hide_bubbles()
        self.cff_bubble.show_for(self)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.single_click_timer.stop()
            self.toggle_chatbox()
            event.accept()
            return
        self.keyboard_controller.press(event.key())
        event.accept()

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            event.accept()
            return
        self.keyboard_controller.release(event.key())
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            position = event.globalPosition().toPoint()
            self.click_position = position
            self.drag_started = False
            self.drag_offset = position - self.pos()
            self.last_drag_position = position
            self.last_drag_time = perf_counter()

            event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.single_click_timer.stop()
            self.double_click = True
            self.click_position = None
            self.show_cff()
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            self.click_position is not None
            and not self.drag_started
            and (
                event.globalPosition().toPoint() - self.click_position
            ).manhattanLength() >= 4
        ):
            self.single_click_timer.stop()
            self.hide_bubbles()
            self.drag_started = True
            self.physics.clear_support()
            self.physics.is_dragging = True
            self.physics.velocity_x = 0.0
            self.physics.velocity_y = 0.0

        if self.physics.is_dragging and self.drag_offset is not None:
            position = event.globalPosition().toPoint()
            now = perf_counter()
            elapsed = (
                now - self.last_drag_time
                if self.last_drag_time is not None
                else 0.0
            )

            if self.last_drag_position is not None and elapsed > 0:
                movement = position - self.last_drag_position
                self.physics.velocity_x = movement.x() / elapsed
                self.physics.velocity_y = movement.y() / elapsed

            new_pos = position - self.drag_offset
            self.physics.set_position(new_pos.x(), new_pos.y())
            self.set_position(new_pos.x(), new_pos.y())
            self.last_drag_position = position
            self.last_drag_time = now

            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.drag_started and not self.double_click:
                self.single_click_timer.start(QApplication.doubleClickInterval())
            self.physics.is_dragging = False
            self.drag_offset = None
            self.last_drag_position = None
            self.last_drag_time = None
            self.click_position = None
            self.drag_started = False
            self.double_click = False

            event.accept()

    def closeEvent(self, event):
        self.single_click_timer.stop()
        self.sounds.close()
        self.combo_bubble.reset()
        self.combo_bubble.close()
        self.chatbox.close()
        self.cff_bubble.close()
        super().closeEvent(event)
