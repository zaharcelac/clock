"""Render US Letter PDFs with analog clock faces."""

from __future__ import annotations

import math
import os
import random
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def _safe_font_name(name: str | None) -> str:
    """
    Resolve a PostScript font name for ReportLab. Invalid or unregistered names
    fall back to Helvetica / Helvetica-Bold so ``setFont`` never raises KeyError
    (e.g. typos in module constants or custom names without TT registration).
    """
    if not name or not str(name).strip():
        return "Helvetica"
    name = str(name).strip()
    try:
        pdfmetrics.getFont(name)
        return name
    except (KeyError, AttributeError, TypeError):
        pass
    compact = name.lower().replace(" ", "").replace("-", "")
    if any(
        x in compact
        for x in ("bold", "black", "heavy", "semibold", "demibold", "medium")
    ):
        return "Helvetica-Bold"
    return "Helvetica"


def _font_size_pt(size: float) -> float:
    """Minimum positive size so ReportLab never receives 0 or negative."""
    return max(0.25, float(size))


def _string_width(text: str, font_name: str, size: float) -> float:
    return stringWidth(text, _safe_font_name(font_name), _font_size_pt(size))


# Built-in PostScript fonts (Helvetica, …) only cover Latin-1; extended Latin/symbols need a TTF.
_UNICODE_FONT_ENV = "ANALOG_CLOCK_WORKSHEET_UNICODE_FONT"
_UNICODE_FONT_RL_NAME = "AnalogClockUniSans"
# Supplementary-plane emoji (e.g. U+1F323 sun) needs an emoji-capable TTF, separate from DejaVu.
_EMOJI_FONT_ENV = "ANALOG_CLOCK_WORKSHEET_EMOJI_FONT"
_EMOJI_FONT_RL_NAME = "AnalogClockEmoji"


@lru_cache(maxsize=1)
def _unicode_draw_font_name() -> str | None:
    """
    Register and return a ReportLab font name for broad Unicode coverage, or None.

    Resolution order: environment variable ANALOG_CLOCK_WORKSHEET_UNICODE_FONT,
    packaged ``fonts/DejaVuSans.ttf``, then common Linux locations (DejaVu).
    """
    candidates: list[Path] = []
    env = os.environ.get(_UNICODE_FONT_ENV, "").strip()
    if env:
        candidates.append(Path(env))
    candidates.append(Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf")
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
            Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        ]
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(_UNICODE_FONT_RL_NAME, str(path)))
            return _UNICODE_FONT_RL_NAME
        except Exception:
            continue
    return None


@lru_cache(maxsize=1)
def _emoji_draw_font_name() -> str | None:
    """
    Register a font that includes emoji/pictographic code points (plane > BMP).

    Set ANALOG_CLOCK_WORKSHEET_EMOJI_FONT to a ``.ttf`` path, or rely on common
    Linux locations (Noto Sans Symbols 2, optional Noto Emoji).
    """
    candidates: list[Path] = []
    env = os.environ.get(_EMOJI_FONT_ENV, "").strip()
    if env:
        candidates.append(Path(env))
    # NotoSansSymbols2: includes supplementary pictographs (e.g. U+1F323); works with ReportLab TTFont.
    # NotoColorEmoji often lacks a ``loca`` table and fails TTFont — avoid listing it here.
    candidates.append(
        Path(__file__).resolve().parent / "fonts" / "NotoSansSymbols2-Regular.ttf"
    )
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf"),
        ]
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(_EMOJI_FONT_RL_NAME, str(path)))
            return _EMOJI_FONT_RL_NAME
        except Exception:
            continue
    return None


def _uses_astral_unicode(s: str) -> bool:
    return any(ord(ch) > 0xFFFF for ch in s)


from analog_clock_worksheet.geometry import (
    ClockTime,
    hour_hand_angle_radians,
    minute_hand_angle_radians,
)


# US Letter, points (72pt = 1 inch)
PAGE_W, PAGE_H = letter
MARGIN = 0.5 * inch

# Fixed two columns; at most 4 rows × 2 = 8 clocks.
MAX_CLOCKS_PER_PAGE = 8
# Maximum number of worksheet pages in one PDF (CLI / web).
MAX_PDF_PAGES = 50
COLUMNS = 2

# Line printed centered at the top of the worksheet, above the clock grid.
_WORKSHEET_HEADER_TEXT = "WHAT TIME IS IT"
_WORKSHEET_HEADER_FONT_NAME = "Helvetica-Bold"
_WORKSHEET_HEADER_FONT_SIZE_PT = 14.0

# Footer (centered, below the grid). ``minutes_mode`` (CLI ``--minutes``) maps to the STEP: label.
_WORKSHEET_FOOTER_FONT_NAME = "Courier"
_WORKSHEET_FOOTER_FONT_SIZE_PT = 8.0
# Placed between each footer field; joined with a space on each side (e.g. " | ").
_WORKSHEET_FOOTER_FIELD_SEPARATOR = "|"
# Page bottom to lowest grid content; leaves room for the footer line above y=0.
_FOOTER_LINE_BASELINE_Y = 0.4 * inch
_WORKSHEET_FOOTER_GRID_LIFT = 0.3 * inch  # add to bottom margin to lift grid

# Answer lines beside each clock: text after the underline, and PostScript font per word.
# Size is max(base + bump, base * scale) where ``base`` is the blank line’s ``font_size``.
_ANSWER_BLANK_HOURS_TEXT = "heures"
_ANSWER_BLANK_MINUTES_TEXT = "minutes"
_ANSWER_BLANK_HOURS_WORD_FONT_NAME = "Helvetica-Bold"
_ANSWER_BLANK_MINUTES_WORD_FONT_NAME = "Helvetica-Bold"
_ANSWER_BLANK_WORD_BUMP_PT = 2.5
_ANSWER_BLANK_WORD_SCALE = 1.0
# Latin text in ``_plain_line`` (sun/moon tails, ASCII fallbacks). ``None`` = use ``font_name`` from
# ``_draw_answer_blanks``. The ``______ h ______`` line uses the same base/bold fonts as heures/minutes.
_ANSWER_BLANK_PLAIN_FONT_NAME: str | None = None
# Distance between consecutive answer-line baselines = ``font_size * 1.25 *`` this factor.
# Larger values spread the five lines apart (try 0.55–0.95); smaller packs them tighter.
_ANSWER_BLANK_LINE_STEP_MULT = 1.75
# Horizontal placement: left edge of answer text is ``clock_cx + clock_r *`` this (past face + outer ring).
_ANSWER_BLANK_PAST_FACE_R_MULT = 1.26
# Extra horizontal offset in **points** after radial + column padding; increase to move lines right, away from the clock.
_ANSWER_BLANK_GAP_FROM_CLOCK_PT = 10.0
# Extra lines below heures/minutes (digital-style and day/night); UTF symbols for PDF.
_ANSWER_BLANK_SUN_SYMBOL = "\U0001f323"  # U+1F323 (needs emoji TTF; see _emoji_draw_font_name)
_ANSWER_BLANK_MOON_SYMBOL = "\u263d"  # ☽
# If no Unicode TTF is available, sun/moon lines use these instead of missing-glyph squares.
_ANSWER_BLANK_SUN_FALLBACK = "(jour)"
_ANSWER_BLANK_MOON_FALLBACK = "(nuit)"

# Long tick: outer tip sits this many points inside the face circle (r).
_FACE_CIRCLE_INSET_PT = 1.25
# Radial length of each long tick = radius * this fraction (smaller = shorter).
_MAJOR_TICK_LENGTH_FRAC = 0.1
# Stroke width of long (5-minute) ticks, in points.
_MAJOR_TICK_LINEWIDTH_PT = 1.5

# Short (1-min) tick: same outer-radius rule as the long tick (see
# _tick_outer_radius). When this equals _FACE_CIRCLE_INSET_PT, long and short
# ticks **share the same outer arc** (same distance from the face circle).
_MINOR_OUTER_CIRCLE_INSET_PT = _FACE_CIRCLE_INSET_PT
# Radial length of each short tick = radius * this fraction (mirrors long ticks).
_MINOR_TICK_LENGTH_FRAC = 0.05
# Stroke width of short ticks, in points.
_MINOR_TICK_LINEWIDTH_PT = 0.4

# Hour numbers (1–12) sit on a ring this many **points** **inward** (toward the
# center) from the **inner** end of the long (5-min) tick (`major_inner`), i.e.
# ``hour_r = major_inner - this``. **Smaller** = closer to the long ticks; **0**
# = on the same radius as the inner end of the long tick.
_HOUR_INWARD_FROM_MAJOR_INNER_PT = 6.0
# Hour numbers 1–12: PostScript font name (bold by default).
_HOUR_FONT_NAME = "Helvetica-Bold"
# Size in points = ``radius * _HOUR_FONT_SIZE_FRAC``, clamped to min/max.
_HOUR_FONT_SIZE_FRAC = 0.20
_HOUR_FONT_MIN_PT = 6.0
_HOUR_FONT_MAX_PT = 18.0

# Outer minute labels (0, 5, 10, …, 55): same sizing pattern as the hour numbers.
_OUTER_MINUTE_FONT_NAME = "Helvetica-Bold"
_OUTER_MINUTE_FONT_SIZE_FRAC = 0.1
_OUTER_MINUTE_FONT_MIN_PT = 7.0
_OUTER_MINUTE_FONT_MAX_PT = 7.0

# Clock hands: tip distance from center = ``radius * length_frac``; stroke in points.
_HOUR_HAND_LENGTH_FRAC = 0.4
_MINUTE_HAND_LENGTH_FRAC = 0.65
_HOUR_HAND_LINEWIDTH_PT = 3.5
_MINUTE_HAND_LINEWIDTH_PT = 1.75
# Hand arrows: depth (along the hand) and half-width at base, as fractions of **that** hand’s length.
_HOUR_HAND_ARROW_DEPTH_FRAC = 0.2
_HOUR_HAND_ARROW_HALF_WIDTH_FRAC = 0.2
_MINUTE_HAND_ARROW_DEPTH_FRAC = 0.2
_MINUTE_HAND_ARROW_HALF_WIDTH_FRAC = 0.075

# Center pivot dot (filled circle): ``min(radius * frac, max_pt)`` in points.
_CENTER_DOT_RADIUS_FRAC = 0.06
_CENTER_DOT_RADIUS_MAX_PT = 3.5


def _angle_to_xy(
    r: float, theta: float, cx: float, cy: float
) -> tuple[float, float]:
    """
    Theta: 0 at 12:00, increases clockwise. Y-axis up (reportlab).
    """
    return cx + r * math.sin(theta), cy + r * math.cos(theta)


def _draw_hand_with_arrow(
    c: canvas.Canvas,
    cx: float,
    cy: float,
    hand_len: float,
    tip_x: float,
    tip_y: float,
    *,
    depth_frac: float,
    half_width_frac: float,
) -> None:
    """
    Shaft from pivot to the base of a filled triangular arrow, tip at (tip_x, tip_y).
    Uses the current canvas stroke width for the shaft. ``hand_len`` is the
    intended hand length (used for arrow sizing, same as minute hand logic).
    """
    dx, dy = tip_x - cx, tip_y - cy
    d = math.hypot(dx, dy)
    if d < 0.5:
        return
    ux, uy = dx / d, dy / d
    a_len = min(
        max(1.0, hand_len * depth_frac),
        hand_len * 0.45,
    )
    half_w = max(0.4, hand_len * half_width_frac)
    bx = tip_x - ux * a_len
    by = tip_y - uy * a_len
    c.line(cx, cy, bx, by)
    px, py = -uy, ux
    p1x, p1y = bx + px * half_w, by + py * half_w
    p2x, p2y = bx - px * half_w, by - py * half_w
    path = c.beginPath()
    path.moveTo(tip_x, tip_y)
    path.lineTo(p1x, p1y)
    path.lineTo(p2x, p2y)
    path.close()
    c.setFillColorRGB(0, 0, 0)
    c.setStrokeColorRGB(0, 0, 0)
    c.drawPath(path, fill=1, stroke=0)


def _tick_outer_radius(radius: float, circle_inset_pt: float) -> float:
    """
    Radius from center to the **outer** (rim-ward) end of a tick, using the
    same rule for major and minor: ``circle_inset_pt`` in from the face edge,
    with the same small-radius floor.
    """
    return max(
        radius - circle_inset_pt,
        0.55 * radius,
    )


def _draw_clock_face(
    c: canvas.Canvas,
    cx: float,
    cy: float,
    radius: float,
    time: ClockTime,
    *,
    show_minutes_numbers: bool = True,
    show_minutes_ticks: bool = True,
) -> None:
    c.setLineWidth(1.0)
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)
    c.circle(cx, cy, radius, stroke=1, fill=0)

    # 12 long ticks (every 5 minutes / on the hour) + 4 short ticks in between
    major_outer = _tick_outer_radius(radius, _FACE_CIRCLE_INSET_PT)
    tick_span = max(1.5, radius * _MAJOR_TICK_LENGTH_FRAC)
    tick_span = min(tick_span, major_outer * 0.45)
    major_inner = major_outer - tick_span
    major_inner = min(max(major_inner, radius * 0.55), major_outer * 0.95)
    if major_inner >= major_outer:
        major_inner = max(0.4 * radius, major_outer * 0.86)
    # Same outer circle construction as the long tick; only length differs
    minor_outer = _tick_outer_radius(radius, _MINOR_OUTER_CIRCLE_INSET_PT)
    m_span = max(0.8, radius * _MINOR_TICK_LENGTH_FRAC)
    m_span = min(m_span, minor_outer * 0.5)
    minor_inner = minor_outer - m_span
    minor_inner = min(max(minor_inner, 0.35 * radius), minor_outer * 0.95)
    if minor_inner >= minor_outer:
        minor_inner = max(0.3 * radius, minor_outer * 0.9)
    for m in range(60):
        t = 2.0 * math.pi * (m / 60.0)
        if m % 5 == 0:
            c.setLineWidth(_MAJOR_TICK_LINEWIDTH_PT)
            x0, y0 = _angle_to_xy(major_inner, t, cx, cy)
            x1, y1 = _angle_to_xy(major_outer, t, cx, cy)
        else:
            if not show_minutes_ticks:
                continue
            c.setLineWidth(_MINOR_TICK_LINEWIDTH_PT)
            x0, y0 = _angle_to_xy(minor_inner, t, cx, cy)
            x1, y1 = _angle_to_xy(minor_outer, t, cx, cy)
        c.line(x0, y0, x1, y1)
    c.setLineWidth(1.0)

    # Inner ring: all hour numbers 1–12 (radial position vs long-tick base)
    hour_r = max(
        major_inner - _HOUR_INWARD_FROM_MAJOR_INNER_PT,
        0.32 * radius,
    )
    h_font = max(
        _HOUR_FONT_MIN_PT,
        min(_HOUR_FONT_MAX_PT, radius * _HOUR_FONT_SIZE_FRAC),
    )
    c.setFont(_safe_font_name(_HOUR_FONT_NAME), _font_size_pt(h_font))
    v_nudge = h_font * 0.32
    for h in range(1, 13):
        ang = 0.0 if h == 12 else 2.0 * math.pi * (h / 12.0)
        lx, ly = _angle_to_xy(hour_r, ang, cx, cy)
        c.drawCentredString(lx, ly - v_nudge, str(h))

    # Outer ring: minutes 0, 5, 10, …, 55 (just outside the face)
    if show_minutes_numbers:
        m_outer_r = radius * 1.12
        m_font = max(
            _OUTER_MINUTE_FONT_MIN_PT,
            min(
                _OUTER_MINUTE_FONT_MAX_PT,
                radius * _OUTER_MINUTE_FONT_SIZE_FRAC,
            ),
        )
        c.setFont(_safe_font_name(_OUTER_MINUTE_FONT_NAME), _font_size_pt(m_font))
        m_nudge = m_font * 0.3
        for minute in range(0, 60, 5):
            t = 2.0 * math.pi * (minute / 60.0)
            lx, ly = _angle_to_xy(m_outer_r, t, cx, cy)
            label = "0" if minute == 0 else str(minute)
            c.drawCentredString(lx, ly - m_nudge, label)

    tm = minute_hand_angle_radians(time.minute)
    th = hour_hand_angle_radians(time.hour, time.minute)
    m_len = radius * _MINUTE_HAND_LENGTH_FRAC
    h_len = radius * _HOUR_HAND_LENGTH_FRAC

    # Hour hand: shaft + arrow at the tip (same geometry as minute hand)
    c.setLineWidth(_HOUR_HAND_LINEWIDTH_PT)
    hx, hy = _angle_to_xy(h_len, th, cx, cy)
    _draw_hand_with_arrow(
        c,
        cx,
        cy,
        h_len,
        hx,
        hy,
        depth_frac=_HOUR_HAND_ARROW_DEPTH_FRAC,
        half_width_frac=_HOUR_HAND_ARROW_HALF_WIDTH_FRAC,
    )

    c.setLineWidth(_MINUTE_HAND_LINEWIDTH_PT)
    mx, my = _angle_to_xy(m_len, tm, cx, cy)
    _draw_hand_with_arrow(
        c,
        cx,
        cy,
        m_len,
        mx,
        my,
        depth_frac=_MINUTE_HAND_ARROW_DEPTH_FRAC,
        half_width_frac=_MINUTE_HAND_ARROW_HALF_WIDTH_FRAC,
    )

    # Center dot
    c.setLineWidth(1.0)
    c.setFillColorRGB(0, 0, 0)
    dot_r = min(
        radius * _CENTER_DOT_RADIUS_FRAC,
        _CENTER_DOT_RADIUS_MAX_PT,
    )
    c.circle(cx, cy, dot_r, stroke=0, fill=1)


def _draw_answer_blanks(
    c: canvas.Canvas,
    x_left: float,
    y_center: float,
    font_name: str = "Helvetica",
    font_size: float = 10.0,
) -> None:
    """Five lines to the right of a clock: heures/minutes, then h-style and sun/moon blanks."""
    c.setFillColorRGB(0, 0, 0)
    blank = "______"
    sep = "  "
    label_size = max(
        font_size + _ANSWER_BLANK_WORD_BUMP_PT,
        font_size * _ANSWER_BLANK_WORD_SCALE,
    )

    base_lead = font_size * 1.25
    step = base_lead * _ANSWER_BLANK_LINE_STEP_MULT
    y_heures = y_center + 2.0 * step
    y_minutes = y_center + step
    y_h_form = y_center
    y_sun = y_center - step
    y_moon = y_center - 2.0 * step

    def _one_line(y: float, label: str, label_font: str) -> None:
        fn = _safe_font_name(font_name)
        fs = _font_size_pt(font_size)
        c.setFont(fn, fs)
        c.drawString(x_left, y, blank)
        w_b = _string_width(blank, font_name, font_size)
        w_s = _string_width(sep, font_name, font_size)
        c.setFont(_safe_font_name(label_font), _font_size_pt(label_size))
        c.drawString(x_left + w_b + w_s, y, label)

    def _h_form_line(y: float) -> None:
        """``______`` + ``h`` + ``______`` with same base/bold/sizing as heures/minutes."""
        fn = _safe_font_name(font_name)
        fs = _font_size_pt(font_size)
        w_b = _string_width(blank, font_name, font_size)
        w_s = _string_width(sep, font_name, font_size)
        mid_font = _ANSWER_BLANK_HOURS_WORD_FONT_NAME
        mid_fs = _font_size_pt(label_size)
        w_h = _string_width("h", mid_font, label_size)

        c.setFont(fn, fs)
        c.drawString(x_left, y, blank)
        x_h = x_left + w_b + w_s
        c.setFont(_safe_font_name(mid_font), mid_fs)
        c.drawString(x_h, y, "h")
        x_b2 = x_h + w_h + w_s
        c.setFont(fn, fs)
        c.drawString(x_b2, y, blank)

    def _plain_line(y: float, text: str, *, needs_unicode: bool = False) -> None:
        fs = _font_size_pt(font_size)
        plain = _ANSWER_BLANK_PLAIN_FONT_NAME or font_name
        latin = _safe_font_name(plain)
        if not needs_unicode:
            c.setFont(latin, fs)
            c.drawString(x_left, y, text)
            return

        uni = _unicode_draw_font_name()
        body_fn = uni or latin

        # Sun as emoji (astral code point): emoji font for glyph, regular uni (or Latin) for the tail.
        if text.startswith(_ANSWER_BLANK_SUN_SYMBOL) and _uses_astral_unicode(
            _ANSWER_BLANK_SUN_SYMBOL
        ):
            rest = text[len(_ANSWER_BLANK_SUN_SYMBOL) :]
            emoji_fn = _emoji_draw_font_name()
            if emoji_fn:
                c.setFont(emoji_fn, fs)
                c.drawString(x_left, y, _ANSWER_BLANK_SUN_SYMBOL)
                w0 = stringWidth(_ANSWER_BLANK_SUN_SYMBOL, emoji_fn, fs)
                c.setFont(body_fn, fs)
                c.drawString(x_left + w0, y, rest)
                return
            text = _ANSWER_BLANK_SUN_FALLBACK + rest

        if uni:
            c.setFont(body_fn, fs)
        else:
            text = text.replace(_ANSWER_BLANK_MOON_SYMBOL, _ANSWER_BLANK_MOON_FALLBACK)
            c.setFont(latin, fs)
        c.drawString(x_left, y, text)

    _one_line(y_heures, _ANSWER_BLANK_HOURS_TEXT, _ANSWER_BLANK_HOURS_WORD_FONT_NAME)
    _one_line(y_minutes, _ANSWER_BLANK_MINUTES_TEXT, _ANSWER_BLANK_MINUTES_WORD_FONT_NAME)
    _h_form_line(y_h_form)
    _plain_line(
        y_sun,
        f"{_ANSWER_BLANK_SUN_SYMBOL} {blank} : {blank}",
        needs_unicode=True,
    )
    _plain_line(
        y_moon,
        f"{_ANSWER_BLANK_MOON_SYMBOL} {blank} : {blank}",
        needs_unicode=True,
    )


def _footer_step_label(minutes_mode_value: str) -> str:
    """
    EXACT, HALF, QUARTER, FIVES for the footer STEP: field.
    """
    m = (minutes_mode_value or "fives").strip().lower()
    if m == "quarter":
        return "QUARTER"
    return m.upper()


def _footer_line(
    show_minutes_ticks: bool,
    show_minutes_numbers: bool,
    step_label: str,
    page: int,
    total_pages: int,
) -> str:
    t = "YES" if show_minutes_ticks else "NO"
    n = "YES" if show_minutes_numbers else "NO"
    parts = [
        f"MINUTE-TICKS: {t}",
        f"MINUTE-NUMS: {n}",
        f"STEP: {step_label}",
        f"PAGE {page} of {total_pages}",
    ]
    return f" {_WORKSHEET_FOOTER_FIELD_SEPARATOR} ".join(parts)


def _random_times(
    n: int,
    minute_values: list[int],
    rng: random.Random,
) -> list[ClockTime]:
    minutes = sorted(set(minute_values))
    if not minutes:
        raise ValueError("minute_values must be non-empty")
    # All valid (hour, minute) pairs for this mode — sample without replacement.
    pool: list[ClockTime] = [
        ClockTime(h, m) for h in range(1, 13) for m in minutes
    ]
    if n > len(pool):
        raise ValueError(
            f"Cannot show {n} different times: this minutes mode only allows "
            f"{len(pool)} distinct (hour, minute) pair(s)."
        )
    rng.shuffle(pool)
    return pool[:n]


def build_clock_worksheet_pdf(
    max_problems: int,
    minute_values: list[int],
    rng: random.Random | None = None,
    *,
    show_minutes_numbers: bool = True,
    show_minutes_ticks: bool = True,
    minutes_mode: str = "fives",
    pages: int = 1,
) -> bytes:
    """
    US Letter worksheet(s) in two columns; answer blanks to the right of each clock.

    ``pages`` is how many such pages to put in one PDF, each with a new random
    set of non-duplicate times. Count per page is bounded by ``MAX_CLOCKS_PER_PAGE``.
    """
    r = rng or random.Random()
    n = min(MAX_CLOCKS_PER_PAGE, max(1, int(max_problems)))
    total_pages = max(1, min(MAX_PDF_PAGES, int(pages)))

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("Analog clock practice")

    inner_w = PAGE_W - 2 * MARGIN
    inner_h = PAGE_H - 2 * MARGIN
    title_h = 0.4 * inch
    rows = int(math.ceil(n / COLUMNS))
    col_w = inner_w / COLUMNS
    # Reserve title; lift bottom of grid so the footer does not overlap clocks
    grid_top = MARGIN + inner_h - title_h
    grid_bottom = MARGIN + _WORKSHEET_FOOTER_GRID_LIFT
    grid_h = grid_top - grid_bottom
    cell_h = grid_h / rows if rows else grid_h

    step = _footer_step_label(minutes_mode)

    for page_index in range(total_pages):
        if page_index > 0:
            c.showPage()
        times = _random_times(n, minute_values, r)

        c.setFont(
        _safe_font_name(_WORKSHEET_HEADER_FONT_NAME),
        _font_size_pt(_WORKSHEET_HEADER_FONT_SIZE_PT),
    )
        c.drawCentredString(
            PAGE_W / 2,
            PAGE_H - MARGIN - 0.2 * inch,
            _WORKSHEET_HEADER_TEXT,
        )

        for i, t in enumerate(times):
            row, col = divmod(i, COLUMNS)
            x0 = MARGIN + col * col_w
            # cell center y (top row is row 0)
            cell_cy = grid_top - (row + 0.5) * cell_h
            # Clock in left part of each column; answers on the right
            # Slightly smaller face so inner hours + outer minute ring fit left of the answer blanks
            clock_r = min(col_w * 0.18, cell_h * 0.35, 0.85 * inch)
            pad_x = col_w * 0.04
            clock_cx = x0 + pad_x + clock_r
            _draw_clock_face(
                c,
                clock_cx,
                cell_cy,
                clock_r,
                t,
                show_minutes_numbers=show_minutes_numbers,
                show_minutes_ticks=show_minutes_ticks,
            )
            # Start answers past outer minute labels and padding (see _ANSWER_BLANK_* layout constants).
            text_x = (
                clock_cx
                + clock_r * _ANSWER_BLANK_PAST_FACE_R_MULT
                + max(0.08 * inch, col_w * 0.02)
                + _ANSWER_BLANK_GAP_FROM_CLOCK_PT
            )
            _draw_answer_blanks(
                c, text_x, cell_cy, font_size=max(8.0, min(11.0, cell_h * 0.1))
            )

        c.setFont(
            _safe_font_name(_WORKSHEET_FOOTER_FONT_NAME),
            _font_size_pt(_WORKSHEET_FOOTER_FONT_SIZE_PT),
        )
        c.drawCentredString(
            PAGE_W / 2,
            _FOOTER_LINE_BASELINE_Y,
            _footer_line(
                show_minutes_ticks,
                show_minutes_numbers,
                step,
                page_index + 1,
                total_pages,
            ),
        )

    c.save()
    data = buf.getvalue()
    buf.close()
    return data


def write_clock_worksheet_pdf(
    out: str | Path | BinaryIO,
    max_problems: int,
    minute_values: list[int],
    rng: random.Random | None = None,
    *,
    show_minutes_numbers: bool = True,
    show_minutes_ticks: bool = True,
    minutes_mode: str = "fives",
    pages: int = 1,
) -> None:
    data = build_clock_worksheet_pdf(
        max_problems,
        minute_values,
        rng=rng,
        show_minutes_numbers=show_minutes_numbers,
        show_minutes_ticks=show_minutes_ticks,
        minutes_mode=minutes_mode,
        pages=pages,
    )
    if isinstance(out, (str, Path)):
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_bytes(data)
    else:
        out.write(data)
