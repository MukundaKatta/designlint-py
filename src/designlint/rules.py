"""Rule implementations for designlint-py.

Each rule is a function that takes the :class:`ParsedDocument` and returns a
list of :class:`Finding`s. The rules cover the spec's five families:

  * color-contrast
  * touch-target-size
  * heading-hierarchy
  * form-label
  * leaked-secret

Each rule has a stable ``rule_id`` and severity. Severity isn't configurable
from this entry point -- it tracks the JS sibling's defaults.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional

from .parse import Element, ParsedDocument, render_open_tag
from .utils import (
    RGBA,
    contrast_ratio,
    parse_color,
    parse_css_size,
    parse_inline_style,
    relative_luminance,
)


@dataclass
class Finding:
    """One lint finding."""

    rule_id: str
    severity: str  # "error" | "warning" | "info"
    message: str
    line: int = 1
    snippet: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effective_color(el: Element, doc: ParsedDocument) -> tuple[Optional[RGBA], Optional[RGBA]]:
    """Walk up the parent chain pulling the nearest color/background-color
    declarations from inline styles. Returns (fg, bg).

    We deliberately limit ourselves to inline styles -- the spec calls for
    stdlib only, and selector-matching against `<style>` blocks would
    require a real CSS parser. Inline styles cover the bulk of contrast
    issues in linted templates and demos.
    """
    fg: Optional[RGBA] = None
    bg: Optional[RGBA] = None
    cur: Optional[Element] = el
    while cur is not None:
        style = parse_inline_style(cur.attrs.get("style", ""))
        if fg is None and "color" in style:
            fg = parse_color(style["color"])
        if bg is None and "background-color" in style:
            bg = parse_color(style["background-color"])
        if bg is None and "background" in style:
            # Best-effort: extract the first color-shaped token from a shorthand.
            bg = _first_color_token(style["background"])
        if fg is not None and bg is not None:
            break
        cur = cur.parent
    return fg, bg


def _first_color_token(value: str) -> Optional[RGBA]:
    """Extract a color from a `background:` shorthand."""
    # rgb()/rgba()/hsl()/hsla()
    m = re.search(r"(?:rgba?|hsla?)\([^)]+\)", value, re.IGNORECASE)
    if m:
        return parse_color(m.group(0))
    # hex
    m = re.search(r"#[0-9a-fA-F]{3,8}\b", value)
    if m:
        return parse_color(m.group(0))
    # named
    m = re.search(r"\b[a-zA-Z]+\b", value)
    if m:
        return parse_color(m.group(0))
    return None


def _font_size_pixels(el: Element) -> Optional[float]:
    """Read the nearest inline ``font-size`` and convert to pixels."""
    cur: Optional[Element] = el
    while cur is not None:
        style = parse_inline_style(cur.attrs.get("style", ""))
        if "font-size" in style:
            return parse_css_size(style["font-size"])
        cur = cur.parent
    return None


def _is_large_text(el: Element) -> bool:
    """WCAG large-text threshold: >= 18pt (24px), or >= 14pt (18.66px) bold."""
    px = _font_size_pixels(el) or 16.0
    style = parse_inline_style(el.attrs.get("style", ""))
    weight = style.get("font-weight", "")
    bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 700)
    if px >= 24:
        return True
    if bold and px >= 18.66:
        return True
    # Inherited weight via parent
    cur = el.parent
    while cur is not None:
        cs = parse_inline_style(cur.attrs.get("style", ""))
        w = cs.get("font-weight", "")
        if w in ("bold", "bolder") or (w.isdigit() and int(w) >= 700):
            if px >= 18.66:
                return True
            break
        cur = cur.parent
    return False


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def color_contrast(doc: ParsedDocument) -> List[Finding]:
    """Flag inline color/background-color pairs below WCAG AA contrast."""
    out: List[Finding] = []
    for el in doc.elements:
        # Only consider elements that themselves declare color or contain text.
        own_style = parse_inline_style(el.attrs.get("style", ""))
        if "color" not in own_style:
            continue
        if not el.text:
            # Element with color: but no direct text -- could still apply to
            # children, but we only flag when text is present (less noisy).
            continue
        fg, bg = _effective_color(el, doc)
        if fg is None:
            continue
        # If no background found, assume white -- matches what most browsers
        # render and avoids false-negatives on common templates.
        if bg is None:
            bg = RGBA(255, 255, 255, 1.0)
        # Skip transparent backgrounds we couldn't resolve.
        if bg.a == 0:
            bg = RGBA(255, 255, 255, 1.0)
        ratio = contrast_ratio(fg, bg)
        threshold = 3.0 if _is_large_text(el) else 4.5
        if ratio + 1e-9 < threshold:
            out.append(
                Finding(
                    rule_id="color-contrast",
                    severity="error",
                    message=(
                        f"Contrast ratio {ratio:.2f}:1 is below WCAG AA minimum "
                        f"of {threshold}:1."
                    ),
                    line=el.line,
                    snippet=render_open_tag(el),
                )
            )
    return out


_INTERACTIVE_TAGS = {"a", "button"}
_INTERACTIVE_INPUT_TYPES = {"button", "submit", "reset", "image"}


def touch_target_size(doc: ParsedDocument) -> List[Finding]:
    """Flag interactive elements smaller than 24x24 CSS pixels.

    WCAG 2.2 SC 2.5.8 (Target Size Minimum) is 24x24; we use that.
    """
    out: List[Finding] = []
    for el in doc.elements:
        is_interactive = el.tag in _INTERACTIVE_TAGS
        if el.tag == "input":
            t = el.attrs.get("type", "").lower()
            is_interactive = t in _INTERACTIVE_INPUT_TYPES
        if not is_interactive:
            continue
        style = parse_inline_style(el.attrs.get("style", ""))
        # Need both width + height for a useful check.
        w = parse_css_size(style.get("width", "")) if "width" in style else None
        h = parse_css_size(style.get("height", "")) if "height" in style else None
        if w is None or h is None:
            continue
        if w < 24 or h < 24:
            out.append(
                Finding(
                    rule_id="touch-target-size",
                    severity="warning",
                    message=(
                        f"Interactive <{el.tag}> is {w:g}x{h:g}px; "
                        f"WCAG 2.2 minimum target size is 24x24px."
                    ),
                    line=el.line,
                    snippet=render_open_tag(el),
                )
            )
    return out


_HEADING_RE = re.compile(r"^h[1-6]$")


def heading_hierarchy(doc: ParsedDocument) -> List[Finding]:
    """Flag missing h1 and skipped heading levels."""
    out: List[Finding] = []
    headings = [el for el in doc.elements if _HEADING_RE.match(el.tag)]
    if not headings:
        return out
    if headings[0].tag != "h1":
        out.append(
            Finding(
                rule_id="heading-hierarchy",
                severity="warning",
                message=f"First heading is <{headings[0].tag}>; expected <h1>.",
                line=headings[0].line,
                snippet=render_open_tag(headings[0]),
            )
        )
    prev = int(headings[0].tag[1])
    for h in headings[1:]:
        cur = int(h.tag[1])
        if cur > prev + 1:
            out.append(
                Finding(
                    rule_id="heading-hierarchy",
                    severity="warning",
                    message=(
                        f"Heading level jumps from h{prev} to h{cur}. "
                        "Don't skip levels -- it breaks screen-reader navigation."
                    ),
                    line=h.line,
                    snippet=render_open_tag(h),
                )
            )
        prev = cur
    return out


_LABELLED_INPUT_TYPES_TO_SKIP = {"hidden", "button", "submit", "reset", "image"}


def form_label(doc: ParsedDocument) -> List[Finding]:
    """Flag form controls without an accessible label."""
    out: List[Finding] = []
    # Index labels by their `for` attr.
    label_targets: set[str] = set()
    for el in doc.elements:
        if el.tag == "label":
            for_id = el.attrs.get("for", "").strip()
            if for_id:
                label_targets.add(for_id)
    for el in doc.elements:
        if el.tag not in ("input", "select", "textarea"):
            continue
        if el.tag == "input":
            t = el.attrs.get("type", "text").lower()
            if t in _LABELLED_INPUT_TYPES_TO_SKIP:
                continue
        # Acceptable label sources:
        if el.attrs.get("aria-label", "").strip():
            continue
        if el.attrs.get("aria-labelledby", "").strip():
            continue
        # Wrapped in a <label>?
        wrapped_in_label = False
        cur = el.parent
        while cur is not None:
            if cur.tag == "label":
                wrapped_in_label = True
                break
            cur = cur.parent
        if wrapped_in_label:
            continue
        # `id` is referenced by a `<label for>`?
        own_id = el.attrs.get("id", "").strip()
        if own_id and own_id in label_targets:
            continue
        # Implicit `title` is okay-ish but warn-worthy; rule still fires.
        out.append(
            Finding(
                rule_id="form-label",
                severity="error",
                message=f"<{el.tag}> has no associated label or aria-label.",
                line=el.line,
                snippet=render_open_tag(el),
            )
        )
    return out


# Provider-shaped API key patterns. Mirrors the JS sibling's secret families
# (openai, anthropic, github, slack, aws, stripe, google AI). Trimmed list
# keeps false-positives manageable; users can post-process if they need more.
# Order matters: more-specific provider patterns (e.g. ``sk-ant-...``) come
# before the generic OpenAI ``sk-...`` so we don't mislabel an Anthropic key
# as OpenAI just because the looser pattern also matches it.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-|svcacct-|admin-|live-)?[A-Za-z0-9_-]{20,}\b")),
    ("Google AI API key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("GitHub personal token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("Slack bot token", re.compile(r"\bxox[abp]-[0-9]+-[0-9]+-[A-Za-z0-9]+\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Stripe secret key", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b")),
]


def leaked_secret(doc: ParsedDocument) -> List[Finding]:
    """Scan visible text and attribute values for provider-shaped API keys.

    Walking the raw HTML once would miss attribute-only tokens (e.g.
    ``data-key="sk-..."``); we walk both element text and attribute values
    to catch each surface.
    """
    out: List[Finding] = []
    seen_at_line: set[tuple[int, str]] = set()
    for el in doc.elements:
        # Attribute values
        for k, v in el.attrs.items():
            if not v:
                continue
            for label, pat in _SECRET_PATTERNS:
                if pat.search(v):
                    key = (el.line, label)
                    if key in seen_at_line:
                        continue
                    seen_at_line.add(key)
                    out.append(
                        Finding(
                            rule_id="leaked-secret",
                            severity="error",
                            message=(
                                f"Possible hardcoded {label} in attribute "
                                f"{k!r} of <{el.tag}>."
                            ),
                            line=el.line,
                            snippet=render_open_tag(el),
                        )
                    )
                    break
        # Text content
        if el.text:
            for label, pat in _SECRET_PATTERNS:
                if pat.search(el.text):
                    key = (el.line, label)
                    if key in seen_at_line:
                        continue
                    seen_at_line.add(key)
                    out.append(
                        Finding(
                            rule_id="leaked-secret",
                            severity="error",
                            message=f"Possible hardcoded {label} in <{el.tag}> text.",
                            line=el.line,
                            snippet=render_open_tag(el),
                        )
                    )
                    break
    return out


ALL_RULES = (
    color_contrast,
    touch_target_size,
    heading_hierarchy,
    form_label,
    leaked_secret,
)
