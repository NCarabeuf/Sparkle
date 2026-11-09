from pathlib import Path
import random
from math import atan2, degrees


IDLE_DOWN_THRESHOLD = 0.0

MIN_NORMAL_DURATION = 30.0
MAX_NORMAL_DURATION = 60.0

SPECIAL_STATE_DURATION = 10.0

SAD_FRAME_DURATION = 0.5

SALTO_DURATION = 0.75

CRUSH_FRAME_DURATION = 0.03
CRUSH_HOLD_DURATION = 0.1

SPECIAL_STATES = ("sad", "cute", "love")

MOBILE_ANGLES = (
    (25, 65, 0),
    (65, 115, 270),
    (115, 155, 180),
    (155, 240, 135),
    (240, 300, 90),
)


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


def get_mobile_image(velocity_x: float, velocity_y: float) -> str:
    angle = degrees(atan2(velocity_y, velocity_x)) % 360

    if angle >= 300 or angle < 25:
        direction = 45
    else:
        direction = next(
            direction
            for minimum, maximum, direction in MOBILE_ANGLES
            if minimum <= angle < maximum
        )

    return str(Path("mobile") / f"fast_{direction}.png")


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
        self.special_state_triggered = False
        self.sad_frame = 0
        self.sad_elapsed = 0.0
        self.was_airborne = False
        self.salto_remaining = 0.0
        self.salto_elapsed = 0.0
        self.salto_angle = 0.0
        self.crush_elapsed = None
        self.manual_crush = False
        self.manual_crush_elapsed = None
        self.crush_release_elapsed = None
        self.chat_active = False
        self.chat_side = "right"
        self.cff_active = False
        self.cff_side = "right"
        self.time_until_transition = random.uniform(
            MIN_NORMAL_DURATION,
            MAX_NORMAL_DURATION,
        )

    def set_chat_active(self, active: bool, side: str = "right"):
        self.chat_active = active
        self.chat_side = side

    def set_cff_active(self, active: bool, side: str = "right"):
        self.cff_active = active
        self.cff_side = side

    def update(
        self,
        dt: float,
        sparkle_x: float,
        sparkle_y: float,
        sparkle_width: float,
        sparkle_height: float,
        cursor_x: float,
        cursor_y: float,
        airborne: bool,
        velocity_x: float,
        velocity_y: float,
        cursor_hit: bool,
        landed: bool,
        crush_triggered: bool,
        crush_held: bool,
    ) -> str:
        self.special_state_triggered = False
        if crush_triggered:
            self.manual_crush_elapsed = 0.0
            self.manual_crush = True
            self.crush_release_elapsed = None

        if landed:
            self.salto_remaining = 0.0
            self.salto_elapsed = 0.0
            self.salto_angle = 0.0
            self.crush_elapsed = 0.0
            self.manual_crush = False
            self.manual_crush_elapsed = None
            self.crush_release_elapsed = None
            return str(Path("crush") / "raplapla0.png")

        if self.manual_crush:
            if crush_held:
                self.manual_crush_elapsed += max(dt, 0.0)
                if self.manual_crush_elapsed < CRUSH_FRAME_DURATION:
                    frame = 0
                elif self.manual_crush_elapsed < CRUSH_FRAME_DURATION * 2:
                    frame = 1
                else:
                    frame = 2
                return str(Path("crush") / f"raplapla{frame}.png")

            if self.crush_release_elapsed is None:
                self.crush_release_elapsed = 0.0
            self.crush_release_elapsed += max(dt, 0.0)
            if self.crush_release_elapsed < CRUSH_FRAME_DURATION:
                frame = 2
            elif self.crush_release_elapsed < CRUSH_FRAME_DURATION * 2:
                frame = 1
            elif self.crush_release_elapsed < CRUSH_FRAME_DURATION * 3:
                frame = 0
            else:
                self.manual_crush = False
                self.manual_crush_elapsed = None
                self.crush_release_elapsed = None
                return get_state_image(
                    "normal",
                    sparkle_x,
                    sparkle_y,
                    sparkle_width,
                    sparkle_height,
                    cursor_x,
                    cursor_y,
                )
            return str(Path("crush") / f"raplapla{frame}.png")

        if self.crush_elapsed is not None:
            self.crush_elapsed += max(dt, 0.0)
            if self.crush_elapsed < CRUSH_FRAME_DURATION:
                frame = 0
            elif self.crush_elapsed < CRUSH_FRAME_DURATION * 2:
                frame = 1
            elif self.crush_elapsed < (
                CRUSH_FRAME_DURATION * 2 + CRUSH_HOLD_DURATION
            ):
                frame = 2
            elif self.crush_elapsed < (
                CRUSH_FRAME_DURATION * 3 + CRUSH_HOLD_DURATION
            ):
                frame = 1
            elif self.crush_elapsed < (
                CRUSH_FRAME_DURATION * 4 + CRUSH_HOLD_DURATION
            ):
                frame = 0
            else:
                self.crush_elapsed = None
                frame = None
            if frame is not None:
                return str(Path("crush") / f"raplapla{frame}.png")

        if cursor_hit and airborne:
            self.salto_remaining = SALTO_DURATION
            self.salto_elapsed = 0.0

        self.salto_remaining = max(
            0.0,
            self.salto_remaining - max(dt, 0.0),
        )

        if airborne:
            self.was_airborne = True
            if self.salto_remaining > 0.0:
                self.salto_elapsed += max(dt, 0.0)
                self.salto_angle = (
                    self.salto_elapsed / SALTO_DURATION * 360.0
                )
                return str(Path("mobile") / "salto_state.png")
            self.salto_angle = 0.0
            return get_mobile_image(velocity_x, velocity_y)

        if self.cff_active:
            return str(Path("cff") / f"cff_{self.cff_side}.png")

        if self.chat_active:
            horizontal = self.chat_side
            return str(Path("chatbox") / f"nerd_{horizontal}.png")

        if self.was_airborne:
            self.state = "normal"
            self.sad_frame = 0
            self.sad_elapsed = 0.0
            self.time_until_transition = random.uniform(
                MIN_NORMAL_DURATION,
                MAX_NORMAL_DURATION,
            )
            self.was_airborne = False
            self.salto_remaining = 0.0
            self.salto_elapsed = 0.0
            self.salto_angle = 0.0

        self.time_until_transition -= max(dt, 0.0)
        if self.time_until_transition <= 0:
            if self.state == "normal":
                self.state = random.choice(SPECIAL_STATES)
                self.special_state_triggered = True
                if self.state == "sad":
                    self.sad_frame = 0
                    self.sad_elapsed = 0.0
                self.time_until_transition = SPECIAL_STATE_DURATION
            else:
                self.state = "normal"
                self.time_until_transition = random.uniform(
                    MIN_NORMAL_DURATION,
                    MAX_NORMAL_DURATION,
                )

        if self.state == "sad":
            self.sad_elapsed += max(dt, 0.0)
            self.sad_frame = int(
                self.sad_elapsed / SAD_FRAME_DURATION
            ) % 4

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
