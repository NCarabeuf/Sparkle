def clear_support(physics):
    physics.support_hwnd = None
    physics.support_offset_x = None
    physics.support_rectangle = None


def follow_support(physics):
    if physics.support_hwnd is None or physics.support_offset_x is None:
        return False

    if physics.support_rectangle is None:
        clear_support(physics)
        return False

    window_left, window_top, _, _ = physics.support_rectangle
    physics.x = window_left + physics.support_offset_x
    physics.y = window_top - physics.height
    physics.velocity_x = 0.0
    physics.velocity_y = 0.0
    return True