def is_airborne(physics):
    if physics.is_dragging or physics.support_hwnd is not None:
        return False
    return physics.floor_y is None or physics.y < physics.floor_y


def apply_cursor_hit(physics, previous_cursor, cursor, dt: float, was_over: bool):
    physics.cursor_hit_cooldown_remaining = max(
        0.0,
        physics.cursor_hit_cooldown_remaining - max(dt, 0.0),
    )

    left = physics.x
    top = physics.y
    right = left + physics.width
    bottom = top + physics.height
    cursor_over = left <= cursor[0] <= right and top <= cursor[1] <= bottom

    if (
        not is_airborne(physics)
        or was_over
        or physics.cursor_hit_cooldown_remaining > 0.0
        or dt <= 0
        or not segment_intersects_rectangle(
            previous_cursor, cursor, left, top, right, bottom
        )
    ):
        return cursor_over

    physics.clear_support()
    physics.velocity_x = (cursor[0] - previous_cursor[0]) / dt
    physics.velocity_y = (cursor[1] - previous_cursor[1]) / dt
    physics.cursor_hit_cooldown_remaining = physics.cursor_hit_cooldown
    return cursor_over


def segment_intersects_rectangle(start, end, left, top, right, bottom):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    t_min = 0.0
    t_max = 1.0

    for origin, direction, minimum, maximum in (
        (start[0], dx, left, right),
        (start[1], dy, top, bottom),
    ):
        if direction == 0:
            if origin < minimum or origin > maximum:
                return False
            continue

        near = (minimum - origin) / direction
        far = (maximum - origin) / direction
        if near > far:
            near, far = far, near
        t_min = max(t_min, near)
        t_max = min(t_max, far)
        if t_min > t_max:
            return False

    return True