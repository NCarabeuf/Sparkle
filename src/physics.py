from math import hypot

from src import bounce, static


class Physics:
    def __init__(self):
        self.x = 0
        self.y = 0

        self.velocity_x = 0.0
        self.velocity_y = 0.0

        self.gravity = 2000.0
        self.max_speed = 2500.0
        self.bounce_restitution = 0.50
        self.left_wall = None
        self.right_wall = None
        self.ceiling_y = None
        self.floor_y = None
        self.width = 0
        self.height = 0
        self.platforms = []
        self.support_hwnd = None
        self.support_offset_x = None
        self.support_rectangle = None
        self.cursor_hit_cooldown = 0.25
        self.cursor_hit_cooldown_remaining = 0.0
        self.is_dragging = False

    def set_position(self, x: float, y: float):
        self.x = x
        self.y = y

    def is_airborne(self):
        return bounce.is_airborne(self)

    def apply_cursor_hit(self, previous_cursor, cursor, dt: float, was_over: bool):
        return bounce.apply_cursor_hit(
            self, previous_cursor, cursor, dt, was_over
        )

    def clear_support(self):
        static.clear_support(self)

    def follow_support(self):
        return static.follow_support(self)

    def update_physics(self, dt: float):
        if self.is_dragging:
            return
        if self.follow_support():
            return

        previous_y = self.y
        self.velocity_y += self.gravity * dt
        falling = self.velocity_y >= 0
        speed = hypot(self.velocity_x, self.velocity_y)
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.velocity_x *= scale
            self.velocity_y *= scale

        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt

        if self.left_wall is not None and self.x <= self.left_wall:
            self.x = self.left_wall
            self.velocity_x = -self.velocity_x
            self.velocity_x *= self.bounce_restitution
        elif self.right_wall is not None and self.x >= self.right_wall:
            self.x = self.right_wall
            self.velocity_x = -self.velocity_x
            self.velocity_x *= self.bounce_restitution

        if self.ceiling_y is not None and self.y <= self.ceiling_y:
            self.y = self.ceiling_y
            self.velocity_y = -self.velocity_y

        if self.floor_y is not None and self.y >= self.floor_y:
            self.y = self.floor_y
            self.velocity_x = 0.0
            self.velocity_y = 0.0
        elif falling:
            previous_bottom = previous_y + self.height
            current_bottom = self.y + self.height
            left = self.x
            right = self.x + self.width
            landing_y = None

            landing_platform = None
            for platform in self.platforms:
                (
                    _,
                    window_left,
                    platform_left,
                    platform_top,
                    platform_right,
                    _,
                ) = platform
                overlaps_horizontally = (
                    right > platform_left and left < platform_right
                )
                crossed_top = (
                    previous_bottom <= platform_top
                    and current_bottom >= platform_top
                )
                touching_top_while_falling = (
                    current_bottom >= platform_top
                    and self.y <= platform_top - self.height
                )
                if (
                    overlaps_horizontally
                    and (crossed_top or touching_top_while_falling)
                ):
                    if landing_y is None or platform_top < landing_y:
                        landing_y = platform_top
                        landing_platform = platform

            if landing_y is not None:
                self.y = landing_y - self.height
                self.velocity_x = 0.0
                self.velocity_y = 0.0
                self.support_hwnd = landing_platform[0]
                self.support_offset_x = self.x - landing_platform[1]
