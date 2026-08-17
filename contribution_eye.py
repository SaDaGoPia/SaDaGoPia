from __future__ import annotations

import math
from typing import Callable

CELL = 10
GAP = 3
LID_ROWS = 1
EMPTY_COLOR = "#161b22"

Resolver = Callable[[int, int], str]

PALETTES = {
    # The Eye of Ender (End Portal item) -- not the Enderman's eye.
    "ender": {
        "lid": "#241a30",
        "lid_noise": 0.06,
        "pupil": "#050208",
        "iris_bands": ["#0a3d33", "#12735f", "#1fae87", "#3fd39a", "#8fe000"],
        "sclera": "#a698bb",
        "sclera_noise_color": "#5c4d6e",
        "catchlight": "#eafff6",
        "pupil_half_width": 2.0,
        "iris_max_width": 9,
        "swirl": True,
    },
    "smaug": {
        "lid": "#2b1405",
        "lid_noise": 0.08,
        "pupil": "#100600",
        "iris_bands": ["#3a0a02", "#8a1f04", "#d9530a", "#ffb020", "#ffe29a"],
        "sclera": "#4a2510",
        "sclera_noise_color": "#20100a",
        "catchlight": "#fff6d9",
        "pupil_half_width": 2.3,
        "iris_max_width": 10,
        "swirl": False,
    },
}

GAZE_OFFSETS = {
    "center": (0.0, 0.0),
    "left": (-3.0, 0.0),
    "right": (3.0, 0.0),
}

RESTING_HOLD_SECONDS = 10.0
BLINK_CLOSE_SECONDS = 0.20
BLINK_OPEN_SECONDS = 0.25


def _seeded(col: float, row: float, salt: float) -> float:
    x = math.sin(col * 12.9898 + row * 78.233 + salt) * 43758.5453
    return x - math.floor(x)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    n = int(hex_color[1:], 16)
    return (n >> 16) & 255, (n >> 8) & 255, n & 255


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    def c(v: float) -> str:
        return format(max(0, min(255, round(v))), "02x")

    return f"#{c(r)}{c(g)}{c(b)}"


def _mix(hex_a: str, hex_b: str, t: float) -> str:
    a, b = _hex_to_rgb(hex_a), _hex_to_rgb(hex_b)
    return _rgb_to_hex(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _shade(hex_color: str, amount: float) -> str:
    target = 255 if amount > 0 else 0
    return _mix(hex_color, _rgb_to_hex(target, target, target), abs(amount))


def eye_color(col: int, row: int, cols: int, rows: int, variant: str, gaze: tuple[float, float] = (0.0, 0.0)) -> str:
    """Color of one dot when the grid shows `variant`'s eye, with the pupil/iris
    center offset by `gaze` (dCol, dRow). Dots never move -- the illusion of
    the eye looking around comes purely from which dots read as pupil/iris/
    sclera at a given gaze offset."""
    p = PALETTES[variant]
    center_col = (cols - 1) / 2 + gaze[0]
    center_row = (rows - 1) / 2 + gaze[1]
    d_col = col - center_col
    d_row = row - center_row
    abs_d_col = abs(d_col)
    abs_d_row = abs(d_row)

    if row < LID_ROWS or row >= rows - LID_ROWS:
        return _shade(p["lid"], (_seeded(col, row, 11) - 0.5) * p["lid_noise"])

    row_half = (rows - 1) / 2
    inner_half = row_half - LID_ROWS
    row_frac = min(1.0, abs_d_row / inner_half) if inner_half > 0 else 0.0

    if col == round(center_col - 3) and row == round(center_row - 1):
        return p["catchlight"]

    pupil_half_width = p["pupil_half_width"] * math.sqrt(max(0.0, 1 - row_frac * row_frac))
    if abs_d_col <= pupil_half_width:
        return _shade(p["pupil"], (_seeded(col, row, 22) - 0.5) * 0.05)

    iris_half_width = p["iris_max_width"] * math.sqrt(max(0.0, 1 - row_frac * row_frac * 0.6))
    if abs_d_col <= iris_half_width and iris_half_width > pupil_half_width:
        t = (abs_d_col - pupil_half_width) / (iris_half_width - pupil_half_width)
        if p["swirl"]:
            angle = math.atan2(d_row, d_col)
            t += math.sin(angle * 3 + abs_d_col * 0.9) * 0.15
        band_pos = max(0.0, min(0.999, t))
        bands = p["iris_bands"]
        scaled = band_pos * (len(bands) - 1)
        i = int(scaled)
        base = _mix(bands[i], bands[min(i + 1, len(bands) - 1)], scaled - i)
        noise = (_seeded(col, row, 33) - 0.5) * (0.14 if p["swirl"] else 0.18)
        return _shade(base, noise)

    noise = (_seeded(col, row, 44) - 0.5) * 0.5
    base = p["sclera_noise_color"] if noise > 0.15 else p["sclera"]
    return _shade(base, (_seeded(col, row, 55) - 0.5) * 0.12)


def _blink_color(col: int, row: int, variant: str) -> str:
    p = PALETTES[variant]
    return _shade(p["lid"], (_seeded(col, row, 77) - 0.5) * p["lid_noise"])


def _gaze_block(cols: int, rows: int, variant: str) -> list[tuple[float, Resolver]]:
    """Center -> glance left -> center (via a blink, not a slide) -> glance
    right -> center (via a blink) -> hold, before the closing blink-out.
    Blinking on the return to center reads more like a real eye than sliding
    the pupil straight back each time."""

    def at(pos: str) -> Resolver:
        gaze = GAZE_OFFSETS[pos]
        return lambda c, r: eye_color(c, r, cols, rows, variant, gaze)

    def blink(c: int, r: int) -> str:
        return _blink_color(c, r, variant)

    return [
        (1.3, at("center")),
        (0.5, at("left")),
        (1.0, at("left")),
        (BLINK_CLOSE_SECONDS, blink),
        (BLINK_OPEN_SECONDS, at("center")),
        (0.8, at("center")),
        (0.5, at("right")),
        (1.0, at("right")),
        (BLINK_CLOSE_SECONDS, blink),
        (BLINK_OPEN_SECONDS, at("center")),
        (0.8, at("center")),
    ]


def build_schedule(cols: int, rows: int, real_color: Resolver) -> list[tuple[float, Resolver]]:
    """A shared list of (absolute_time_seconds, resolver) keyframes, identical
    for every dot -- only the color each resolver returns for a given (col,
    row) differs. Consecutive identical resolvers create a held color;
    different resolvers create a transition, since SMIL interpolates
    linearly between consecutive `values`."""

    def blink_close(variant: str) -> Resolver:
        return lambda c, r: _blink_color(c, r, variant)

    def open_center(variant: str) -> Resolver:
        return lambda c, r: eye_color(c, r, cols, rows, variant, GAZE_OFFSETS["center"])

    steps: list[tuple[float, Resolver]] = [
        (0.0, real_color),
        (RESTING_HOLD_SECONDS, real_color),
        (BLINK_CLOSE_SECONDS, blink_close("ender")),
        (BLINK_OPEN_SECONDS, open_center("ender")),
        *_gaze_block(cols, rows, "ender"),
        (BLINK_CLOSE_SECONDS, blink_close("ender")),
        (BLINK_OPEN_SECONDS, real_color),
        (RESTING_HOLD_SECONDS, real_color),
        (BLINK_CLOSE_SECONDS, blink_close("smaug")),
        (BLINK_OPEN_SECONDS, open_center("smaug")),
        *_gaze_block(cols, rows, "smaug"),
        (BLINK_CLOSE_SECONDS, blink_close("smaug")),
        (BLINK_OPEN_SECONDS, real_color),
    ]

    schedule: list[tuple[float, Resolver]] = []
    elapsed = 0.0
    for duration, resolver in steps:
        elapsed += duration
        schedule.append((elapsed, resolver))
    return schedule


def render_svg(calendar: dict[tuple[int, int], str], cols: int, rows: int) -> str:
    def real_color(col: int, row: int) -> str:
        return calendar.get((col, row), EMPTY_COLOR)

    schedule = build_schedule(cols, rows, real_color)
    total = schedule[-1][0]
    key_times = ";".join(f"{t / total:.4f}" for t, _ in schedule)

    width = cols * (CELL + GAP) - GAP
    height = rows * (CELL + GAP) - GAP

    circles = []
    for row in range(rows):
        for col in range(cols):
            cx = col * (CELL + GAP) + CELL / 2
            cy = row * (CELL + GAP) + CELL / 2
            values = ";".join(resolver(col, row) for _, resolver in schedule)
            circles.append(
                f'<circle cx="{cx}" cy="{cy}" r="{CELL / 2}">'
                f'<animate attributeName="fill" values="{values}" keyTimes="{key_times}" '
                f'dur="{total:.2f}s" repeatCount="indefinite" calcMode="linear"/>'
                f"</circle>"
            )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">' + "".join(circles) + "</svg>"
    )
