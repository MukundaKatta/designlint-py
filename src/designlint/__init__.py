"""designlint -- accessibility and design linter for HTML/CSS.

Python port of @mukundakatta/designlint, focused on the spec's five rule
families (contrast, touch targets, headings, form labels, leaked secrets)
using only the standard library.

Public surface:

    from designlint import lint, Finding
    from designlint import parse_color, contrast_ratio, parse_css_size
"""

from .core import Finding, lint
from .utils import contrast_ratio, parse_color, parse_css_size, relative_luminance

__version__ = "0.1.0"
VERSION = __version__

__all__ = [
    "VERSION",
    "Finding",
    "contrast_ratio",
    "lint",
    "parse_color",
    "parse_css_size",
    "relative_luminance",
]
