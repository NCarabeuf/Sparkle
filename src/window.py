from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from time import perf_counter

from src.asset_manager import get_asset
from src.animation import AnimationController
from src.physics import Physics

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

        self.scale = 6
        self.drag_offset = None
        self.last_drag_position = None
        self.last_drag_time = None

        self.pet_label = QLabel(self)
        self.pet_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.current_image = None
        self.animation_controller = AnimationController()
        self.set_image("idle/normal/idle_left_down.png")

    def update_animation(self, dt: float, cursor_x: float, cursor_y: float):
        image_name = self.animation_controller.update(
            dt,
            self.x(),
            self.y(),
            self.width(),
            self.height(),
            cursor_x,
            cursor_y,
        )
        if image_name != self.current_image:
            self.set_image(image_name)

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

        self.pet_label.setPixmap(pixmap)
        self.current_image = name

        self.pet_label.resize(pixmap.size())
        self.resize(pixmap.size())

    def set_position(self, x: int, y: int):
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.physics.clear_support()
            self.physics.is_dragging = True
            position = event.globalPosition().toPoint()
            self.drag_offset = position - self.pos()
            self.last_drag_position = position
            self.last_drag_time = perf_counter()
            self.physics.velocity_x = 0.0
            self.physics.velocity_y = 0.0

            event.accept()

    def mouseMoveEvent(self, event):
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
            self.physics.is_dragging = False
            self.drag_offset = None
            self.last_drag_position = None
            self.last_drag_time = None

            event.accept()