import sys
import ctypes
from ctypes.wintypes import RECT
from time import perf_counter

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QCursor

from src.window import SparkleWindow
from src.physics import Physics

def configure_dpi_awareness():
    user32 = ctypes.windll.user32
    set_context = getattr(user32, "SetProcessDpiAwarenessContext", None)
    if set_context is not None:
        if set_context(ctypes.c_void_p(-4)):
            return

    shcore = ctypes.windll.shcore
    shcore.SetProcessDpiAwareness(2)

def get_visible_window_tops(rectangles):
    visible_tops = []

    for index, (hwnd, left, top, right, bottom) in enumerate(rectangles):
        visible_segments = [(left, right)]

        for _, covering_left, covering_top, covering_right, covering_bottom in (
            rectangles[:index]
        ):
            covers_top = (
                covering_top <= top < covering_bottom
                and covering_right > left
                and covering_left < right
            )
            if not covers_top:
                continue

            uncovered_segments = []
            for segment_left, segment_right in visible_segments:
                if covering_right <= segment_left or covering_left >= segment_right:
                    uncovered_segments.append((segment_left, segment_right))
                    continue

                if segment_left < covering_left:
                    uncovered_segments.append((segment_left, covering_left))
                if covering_right < segment_right:
                    uncovered_segments.append((covering_right, segment_right))
            visible_segments = uncovered_segments

        visible_tops.extend(
            (hwnd, left, segment_left, top, segment_right, bottom)
            for segment_left, segment_right in visible_segments
            if segment_left < segment_right
        )

    return visible_tops

def get_window_rectangle(
    hwnd: int,
    coordinate_scale: float = 1.0,
    coordinate_origin: tuple[int, int] = (0, 0),
):
    user32 = ctypes.windll.user32
    # Query the attached window directly, even when another window covers it.
    native_hwnd = ctypes.c_void_p(hwnd)
    if not user32.IsWindowVisible(native_hwnd) or user32.IsIconic(native_hwnd):
        return None

    rect = RECT()
    if not user32.GetWindowRect(native_hwnd, ctypes.byref(rect)):
        return None

    origin_x, origin_y = coordinate_origin

    def convert(value, origin):
        return origin + (value - origin) * coordinate_scale

    return (
        convert(rect.left, origin_x),
        convert(rect.top, origin_y),
        convert(rect.right, origin_x),
        convert(rect.bottom, origin_y),
    )


def get_window_rectangles(
    excluded_hwnd: int,
    coordinate_scale: float = 1.0,
    coordinate_origin: tuple[int, int] = (0, 0),
):
    user32 = ctypes.windll.user32
    rectangles = []

    enum_windows_proc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )

    def collect_window(hwnd, _):
        if hwnd == excluded_hwnd:
            return True
        rect = get_window_rectangle(hwnd, coordinate_scale, coordinate_origin)
        if rect is not None:
            rectangles.append((hwnd, *rect))
        return True

    user32.EnumWindows(enum_windows_proc(collect_window), None)
    return get_visible_window_tops(rectangles)

def main():
    configure_dpi_awareness()
    app = QApplication(sys.argv)

    physics = Physics()
    Sparkle = SparkleWindow(physics)

    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()

    physics.left_wall = screen_geometry.left()
    physics.right_wall = screen_geometry.right() - Sparkle.width() + 1
    physics.ceiling_y = screen_geometry.top()
    physics.floor_y = screen_geometry.bottom() - Sparkle.height() + 1
    physics.width = Sparkle.width()
    physics.height = Sparkle.height()

    x = screen_geometry.left() + (screen_geometry.width() - Sparkle.width()) // 2
    y = physics.floor_y
    physics.set_position(x, y)
    Sparkle.set_position(x, y)

    Sparkle.show()

    last_time = perf_counter()
    previous_cursor = QCursor.pos()
    cursor_was_over_sparkle = False

    def update():
        nonlocal last_time, previous_cursor, cursor_was_over_sparkle

        now = perf_counter()
        dt = now - last_time
        last_time = now

        cursor = QCursor.pos()
        current_cursor = (cursor.x(), cursor.y())
        Sparkle.update_animation(dt, *current_cursor)
        previous_cursor_position = (
            previous_cursor.x(),
            previous_cursor.y(),
        )
        cursor_was_over_sparkle = physics.apply_cursor_hit(
            previous_cursor_position,
            current_cursor,
            dt,
            cursor_was_over_sparkle,
        )
        previous_cursor = cursor

        screen = app.primaryScreen()
        coordinate_scale = 1.0 / screen.devicePixelRatio()
        screen_geometry = screen.geometry()
        coordinate_origin = (screen_geometry.left(), screen_geometry.top())
        physics.support_rectangle = (
            get_window_rectangle(
                physics.support_hwnd, coordinate_scale, coordinate_origin
            )
            if physics.support_hwnd is not None
            else None
        )
        physics.platforms = get_window_rectangles(
            int(Sparkle.winId()),
            coordinate_scale,
            coordinate_origin,
        )
        physics.update_physics(dt)

        Sparkle.set_position(
            round(physics.x),
            round(physics.y)
        )

    timer = QTimer()
    timer.timeout.connect(update)
    timer.start(15)  # Update every 16 ms (~60 FPS)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
