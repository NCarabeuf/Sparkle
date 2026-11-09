from PySide6.QtCore import Qt


class KeyboardController:
    HORIZONTAL_ACCELERATION = 1800.0
    JUMP_SPEED = 900.0

    def __init__(self):
        self.pressed_keys = set()
        self.jump_requested = False
        self.crush_requested = False

    def press(self, key: int):
        if key == Qt.Key.Key_Up and key not in self.pressed_keys:
            self.jump_requested = True
        if key == Qt.Key.Key_Down and key not in self.pressed_keys:
            self.crush_requested = True
        self.pressed_keys.add(key)

    def release(self, key: int):
        self.pressed_keys.discard(key)

    def update(self, physics, dt: float):
        physics.crush_triggered = False
        physics.crush_held = Qt.Key.Key_Down in self.pressed_keys

        if physics.is_dragging:
            self.jump_requested = False
            self.crush_requested = False
            return

        airborne = physics.is_airborne()
        if airborne:
            if Qt.Key.Key_Right in self.pressed_keys:
                physics.velocity_x += self.HORIZONTAL_ACCELERATION * dt
            elif Qt.Key.Key_Left in self.pressed_keys:
                physics.velocity_x -= self.HORIZONTAL_ACCELERATION * dt
        else:
            physics.velocity_x = 0.0

        if self.jump_requested:
            self.jump_requested = False
            on_floor = (
                physics.floor_y is not None
                and physics.y >= physics.floor_y
            )
            on_window = physics.support_hwnd is not None
            if on_floor or on_window:
                physics.clear_support()
                physics.velocity_y = -self.JUMP_SPEED

        if self.crush_requested:
            self.crush_requested = False
            if not physics.is_airborne():
                physics.crush_triggered = True