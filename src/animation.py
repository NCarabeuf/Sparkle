from pathlib import Path
import random


IDLE_DOWN_THRESHOLD = 0.0
MIN_NORMAL_DURATION = 30.0
MAX_NORMAL_DURATION = 60.0
SPECIAL_STATE_DURATION = 8.0
SPECIAL_STATES = ("cute", "sad", "love")


def get_idle_image(
    sparkle_x: float,
    sparkle_y: float,
    sparkle_width: float,
    sparkle_height: float,
    cursor_x: float,
    cursor_y: float,
) -> str:
    center_x = sparkle_x + sparkle_width / 2
    center_y = sparkle_y + sparkle_height / 2
    horizontal = "left" if cursor_x < center_x else "right"
    down_threshold = sparkle_y + sparkle_height * IDLE_DOWN_THRESHOLD
    vertical = "up" if cursor_y < down_threshold else "down"
    return str(Path("idle") / "normal" / f"idle_{horizontal}_{vertical}.png")


def get_state_image(
    state: str,
    sparkle_x: float,
    sparkle_y: float,
    sparkle_width: float,
    sparkle_height: float,
    cursor_x: float,
    cursor_y: float,
    sad_frame: int = 0,
) -> str:
    horizontal = "left" if cursor_x < sparkle_x + sparkle_width / 2 else "right"

    if state == "normal":
        return get_idle_image(
            sparkle_x,
            sparkle_y,
            sparkle_width,
            sparkle_height,
            cursor_x,
            cursor_y,
        )
    if state == "sad":
        return str(
            Path("idle") / state / f"idle_{horizontal}_{state}{sad_frame}.png"
        )
    if state in ("cute", "love"):
        return str(Path("idle") / state / f"idle_{horizontal}_{state}.png")
    raise ValueError(f"Unknown animation state: {state}")


class AnimationController:
    def __init__(self):
        self.state = "normal"
        self.sad_frame = 0
        self.time_until_transition = random.uniform(
            MIN_NORMAL_DURATION,
            MAX_NORMAL_DURATION,
        )

    def update(
        self,
        dt: float,
        sparkle_x: float,
        sparkle_y: float,
        sparkle_width: float,
        sparkle_height: float,
        cursor_x: float,
        cursor_y: float,
    ) -> str:
        self.time_until_transition -= max(dt, 0.0)
        if self.time_until_transition <= 0:
            if self.state == "normal":
                self.state = random.choice(SPECIAL_STATES)
                if self.state == "sad":
                    self.sad_frame = random.randrange(4)
                self.time_until_transition = SPECIAL_STATE_DURATION
            else:
                self.state = "normal"
                self.time_until_transition = random.uniform(
                    MIN_NORMAL_DURATION,
                    MAX_NORMAL_DURATION,
                )

        return get_state_image(
            self.state,
            sparkle_x,
            sparkle_y,
            sparkle_width,
            sparkle_height,
            cursor_x,
            cursor_y,
            self.sad_frame,
        )