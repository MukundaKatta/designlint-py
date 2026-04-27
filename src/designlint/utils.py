"""Color, contrast, and CSS-size helpers.

Ported from @mukundakatta/designlint/dist/utils.js. WCAG 2.1 luminance
calculation and alpha compositing match the JS implementation byte-for-byte
on the test inputs.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RGBA:
    """Parsed CSS color. Components are 0-255 ints, alpha is 0.0-1.0."""

    r: int
    g: int
    b: int
    a: float = 1.0


# 140 CSS named colors, mirroring the JS sibling.
_NAMED_COLORS: dict[str, str] = {
    "aliceblue": "#f0f8ff", "antiquewhite": "#faebd7", "aqua": "#00ffff",
    "aquamarine": "#7fffd4", "azure": "#f0ffff", "beige": "#f5f5dc",
    "bisque": "#ffe4c4", "black": "#000000", "blanchedalmond": "#ffebcd",
    "blue": "#0000ff", "blueviolet": "#8a2be2", "brown": "#a52a2a",
    "burlywood": "#deb887", "cadetblue": "#5f9ea0", "chartreuse": "#7fff00",
    "chocolate": "#d2691e", "coral": "#ff7f50", "cornflowerblue": "#6495ed",
    "cornsilk": "#fff8dc", "crimson": "#dc143c", "cyan": "#00ffff",
    "darkblue": "#00008b", "darkcyan": "#008b8b", "darkgoldenrod": "#b8860b",
    "darkgray": "#a9a9a9", "darkgreen": "#006400", "darkgrey": "#a9a9a9",
    "darkkhaki": "#bdb76b", "darkmagenta": "#8b008b", "darkolivegreen": "#556b2f",
    "darkorange": "#ff8c00", "darkorchid": "#9932cc", "darkred": "#8b0000",
    "darksalmon": "#e9967a", "darkseagreen": "#8fbc8f", "darkslateblue": "#483d8b",
    "darkslategray": "#2f4f4f", "darkslategrey": "#2f4f4f", "darkturquoise": "#00ced1",
    "darkviolet": "#9400d3", "deeppink": "#ff1493", "deepskyblue": "#00bfff",
    "dimgray": "#696969", "dimgrey": "#696969", "dodgerblue": "#1e90ff",
    "firebrick": "#b22222", "floralwhite": "#fffaf0", "forestgreen": "#228b22",
    "fuchsia": "#ff00ff", "gainsboro": "#dcdcdc", "ghostwhite": "#f8f8ff",
    "gold": "#ffd700", "goldenrod": "#daa520", "gray": "#808080",
    "green": "#008000", "greenyellow": "#adff2f", "grey": "#808080",
    "honeydew": "#f0fff0", "hotpink": "#ff69b4", "indianred": "#cd5c5c",
    "indigo": "#4b0082", "ivory": "#fffff0", "khaki": "#f0e68c",
    "lavender": "#e6e6fa", "lavenderblush": "#fff0f5", "lawngreen": "#7cfc00",
    "lemonchiffon": "#fffacd", "lightblue": "#add8e6", "lightcoral": "#f08080",
    "lightcyan": "#e0ffff", "lightgoldenrodyellow": "#fafad2",
    "lightgray": "#d3d3d3", "lightgreen": "#90ee90", "lightgrey": "#d3d3d3",
    "lightpink": "#ffb6c1", "lightsalmon": "#ffa07a", "lightseagreen": "#20b2aa",
    "lightskyblue": "#87cefa", "lightslategray": "#778899",
    "lightslategrey": "#778899", "lightsteelblue": "#b0c4de",
    "lightyellow": "#ffffe0", "lime": "#00ff00", "limegreen": "#32cd32",
    "linen": "#faf0e6", "magenta": "#ff00ff", "maroon": "#800000",
    "mediumaquamarine": "#66cdaa", "mediumblue": "#0000cd",
    "mediumorchid": "#ba55d3", "mediumpurple": "#9370db",
    "mediumseagreen": "#3cb371", "mediumslateblue": "#7b68ee",
    "mediumspringgreen": "#00fa9a", "mediumturquoise": "#48d1cc",
    "mediumvioletred": "#c71585", "midnightblue": "#191970",
    "mintcream": "#f5fffa", "mistyrose": "#ffe4e1", "moccasin": "#ffe4b5",
    "navajowhite": "#ffdead", "navy": "#000080", "oldlace": "#fdf5e6",
    "olive": "#808000", "olivedrab": "#6b8e23", "orange": "#ffa500",
    "orangered": "#ff4500", "orchid": "#da70d6", "palegoldenrod": "#eee8aa",
    "palegreen": "#98fb98", "paleturquoise": "#afeeee",
    "palevioletred": "#db7093", "papayawhip": "#ffefd5", "peachpuff": "#ffdab9",
    "peru": "#cd853f", "pink": "#ffc0cb", "plum": "#dda0dd",
    "powderblue": "#b0e0e6", "purple": "#800080", "rebeccapurple": "#663399",
    "red": "#ff0000", "rosybrown": "#bc8f8f", "royalblue": "#4169e1",
    "saddlebrown": "#8b4513", "salmon": "#fa8072", "sandybrown": "#f4a460",
    "seagreen": "#2e8b57", "seashell": "#fff5ee", "sienna": "#a0522d",
    "silver": "#c0c0c0", "skyblue": "#87ceeb", "slateblue": "#6a5acd",
    "slategray": "#708090", "slategrey": "#708090", "snow": "#fffafa",
    "springgreen": "#00ff7f", "steelblue": "#4682b4", "tan": "#d2b48c",
    "teal": "#008080", "thistle": "#d8bfd8", "tomato": "#ff6347",
    "turquoise": "#40e0d0", "violet": "#ee82ee", "wheat": "#f5deb3",
    "white": "#ffffff", "whitesmoke": "#f5f5f5", "yellow": "#ffff00",
    "yellowgreen": "#9acd32",
}


def _hex_to_rgba(hex_value: str) -> Optional[RGBA]:
    cleaned = hex_value.lstrip("#")
    try:
        if len(cleaned) == 3:
            r, g, b = (int(c * 2, 16) for c in cleaned)
            return RGBA(r, g, b, 1.0)
        if len(cleaned) == 4:
            r, g, b, a8 = (int(c * 2, 16) for c in cleaned)
            return RGBA(r, g, b, a8 / 255)
        if len(cleaned) == 6:
            r = int(cleaned[0:2], 16)
            g = int(cleaned[2:4], 16)
            b = int(cleaned[4:6], 16)
            return RGBA(r, g, b, 1.0)
        if len(cleaned) == 8:
            r = int(cleaned[0:2], 16)
            g = int(cleaned[2:4], 16)
            b = int(cleaned[4:6], 16)
            a8 = int(cleaned[6:8], 16)
            return RGBA(r, g, b, a8 / 255)
    except ValueError:
        return None
    return None


_RGB_RE = re.compile(
    r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.%]+))?\s*\)",
    re.IGNORECASE,
)
_HSL_RE = re.compile(
    r"hsla?\(\s*([\d.]+)(deg|rad|turn)?[,\s]+([\d.]+)%[,\s]+([\d.]+)%(?:[,/\s]+([\d.%]+))?\s*\)",
    re.IGNORECASE,
)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _parse_alpha(token: Optional[str]) -> float:
    if not token:
        return 1.0
    token = token.strip()
    try:
        if token.endswith("%"):
            return _clamp(float(token[:-1]) / 100.0, 0.0, 1.0)
        return _clamp(float(token), 0.0, 1.0)
    except ValueError:
        return 1.0


def _parse_rgb_string(value: str) -> Optional[RGBA]:
    m = _RGB_RE.search(value)
    if not m:
        return None
    try:
        r = int(_clamp(float(m.group(1)), 0, 255))
        g = int(_clamp(float(m.group(2)), 0, 255))
        b = int(_clamp(float(m.group(3)), 0, 255))
    except ValueError:
        return None
    return RGBA(r, g, b, _parse_alpha(m.group(4)))


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    c = (1 - abs(2 * l - 1)) * s
    hp = h / 60.0
    x = c * (1 - abs((hp % 2) - 1))
    if hp < 1:
        r1, g1, b1 = c, x, 0.0
    elif hp < 2:
        r1, g1, b1 = x, c, 0.0
    elif hp < 3:
        r1, g1, b1 = 0.0, c, x
    elif hp < 4:
        r1, g1, b1 = 0.0, x, c
    elif hp < 5:
        r1, g1, b1 = x, 0.0, c
    else:
        r1, g1, b1 = c, 0.0, x
    m = l - c / 2
    return (
        round((r1 + m) * 255),
        round((g1 + m) * 255),
        round((b1 + m) * 255),
    )


def _parse_hsl_string(value: str) -> Optional[RGBA]:
    m = _HSL_RE.search(value)
    if not m:
        return None
    try:
        h = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2)
    if unit == "rad":
        h = h * 180 / math.pi
    elif unit == "turn":
        h = h * 360
    h = ((h % 360) + 360) % 360
    try:
        s = _clamp(float(m.group(3)) / 100.0, 0.0, 1.0)
        l = _clamp(float(m.group(4)) / 100.0, 0.0, 1.0)
    except ValueError:
        return None
    r, g, b = _hsl_to_rgb(h, s, l)
    return RGBA(r, g, b, _parse_alpha(m.group(5)))


def parse_color(value: str) -> Optional[RGBA]:
    """Parse a CSS color value into RGBA, or return None if unrecognized.

    Supports: hex (3/4/6/8), rgb()/rgba(), hsl()/hsla(), 140 named colors,
    and ``transparent``. Mirrors the JS sibling's behavior.
    """
    if not isinstance(value, str):
        return None
    trimmed = value.strip().lower()
    if trimmed == "transparent":
        return RGBA(0, 0, 0, 0.0)
    if trimmed in _NAMED_COLORS:
        return _hex_to_rgba(_NAMED_COLORS[trimmed])
    if trimmed.startswith("#"):
        return _hex_to_rgba(trimmed)
    if trimmed.startswith("rgb"):
        return _parse_rgb_string(trimmed)
    if trimmed.startswith("hsl"):
        return _parse_hsl_string(trimmed)
    return None


def relative_luminance(color: RGBA) -> float:
    """WCAG 2.1 relative luminance, ignoring alpha."""

    def channel(c: float) -> float:
        cs = c / 255.0
        return cs / 12.92 if cs <= 0.03928 else ((cs + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b)


def _compose_onto(fg: RGBA, bg: RGBA) -> RGBA:
    """Alpha-compose ``fg`` over an opaque ``bg`` so contrast reflects what
    the user actually sees."""
    a = fg.a
    if a >= 1.0:
        return fg
    return RGBA(
        round(fg.r * a + bg.r * (1 - a)),
        round(fg.g * a + bg.g * (1 - a)),
        round(fg.b * a + bg.b * (1 - a)),
        1.0,
    )


def contrast_ratio(fg: RGBA, bg: RGBA) -> float:
    """WCAG 2.1 contrast ratio between ``fg`` (composed onto ``bg``) and ``bg``."""
    composed = _compose_onto(fg, bg)
    l1 = relative_luminance(composed)
    l2 = relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


_SIZE_RE = re.compile(r"^(-?[\d.]+)(px|rem|em|pt|pc|in|cm|mm|vw|vh|vmin|vmax|%)?$", re.IGNORECASE)


def parse_css_size(value: str) -> Optional[float]:
    """Parse a CSS size into approximate pixels.

    Returns ``None`` for values that need layout context (``%``, ``vw``,
    ``vh``, ``vmin``, ``vmax``). ``rem``/``em`` assume a 16px root.
    """
    if not isinstance(value, str):
        return None
    m = _SIZE_RE.match(value.strip())
    if not m:
        return None
    try:
        num = float(m.group(1))
    except ValueError:
        return None
    if not math.isfinite(num):
        return None
    unit = (m.group(2) or "px").lower()
    if unit == "px":
        return num
    if unit in ("rem", "em"):
        return num * 16
    if unit == "pt":
        return num * 4 / 3
    if unit == "pc":
        return num * 16
    if unit == "in":
        return num * 96
    if unit == "cm":
        return num * 96 / 2.54
    if unit == "mm":
        return num * 96 / 25.4
    return None


def parse_inline_style(style: str) -> dict[str, str]:
    """Parse an inline ``style="..."`` string into a lowercased property map.

    No CSS AST -- this is the simple split-on-`;` fallback the JS sibling uses
    when css-tree rejects the input. It's enough for inline styles, which is
    all we need for designlint-py.
    """
    out: dict[str, str] = {}
    if not style:
        return out
    for pair in style.split(";"):
        if ":" not in pair:
            continue
        prop, _, val = pair.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        if prop:
            out[prop] = val
    return out
