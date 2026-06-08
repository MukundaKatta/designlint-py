"""Tests for designlint.lint and the five rule families."""

from __future__ import annotations

import textwrap

from designlint import (
    Finding,
    contrast_ratio,
    lint,
    parse_color,
    parse_css_size,
    relative_luminance,
)


def _ids(findings: list[Finding]) -> set[str]:
    return {f.rule_id for f in findings}


# ---------------------------------------------------------------------------
# color-contrast
# ---------------------------------------------------------------------------


def test_color_contrast_flags_low_contrast_inline_style():
    html = '<p style="color: #ccc; background-color: #fff">low contrast</p>'
    fs = lint(html)
    assert any(f.rule_id == "color-contrast" for f in fs)


def test_color_contrast_passes_high_contrast():
    html = '<p style="color: #000; background-color: #fff">strong</p>'
    fs = lint(html)
    assert not any(f.rule_id == "color-contrast" for f in fs)


def test_color_contrast_inherits_background_from_ancestor():
    html = (
        '<div style="background-color: #fff">'
        '<p style="color: #ccc">low contrast inherited bg</p>'
        "</div>"
    )
    fs = lint(html)
    assert any(f.rule_id == "color-contrast" for f in fs)


def test_color_contrast_message_includes_ratio():
    html = '<p style="color: #888; background-color: #fff">mid</p>'
    fs = [f for f in lint(html) if f.rule_id == "color-contrast"]
    assert fs and ":1" in fs[0].message


# ---------------------------------------------------------------------------
# touch-target-size
# ---------------------------------------------------------------------------


def test_touch_target_size_flags_tiny_button():
    html = '<button style="width: 16px; height: 16px;">x</button>'
    fs = lint(html)
    ids = _ids(fs)
    assert "touch-target-size" in ids


def test_touch_target_size_passes_24px_button():
    html = '<button style="width: 24px; height: 24px;">ok</button>'
    fs = lint(html)
    assert "touch-target-size" not in _ids(fs)


def test_touch_target_size_skips_non_interactive_elements():
    html = '<div style="width: 10px; height: 10px;">not clickable</div>'
    fs = lint(html)
    assert "touch-target-size" not in _ids(fs)


# ---------------------------------------------------------------------------
# heading-hierarchy
# ---------------------------------------------------------------------------


def test_heading_hierarchy_flags_missing_h1():
    html = "<h2>Hi</h2><h3>Sub</h3>"
    fs = lint(html)
    msgs = [f.message for f in fs if f.rule_id == "heading-hierarchy"]
    assert any("expected <h1>" in m for m in msgs)


def test_heading_hierarchy_flags_skipped_level():
    html = "<h1>Title</h1><h3>Skipped h2</h3>"
    fs = [f for f in lint(html) if f.rule_id == "heading-hierarchy"]
    assert fs and "h1 to h3" in fs[0].message


def test_heading_hierarchy_clean_pass():
    html = "<h1>a</h1><h2>b</h2><h3>c</h3><h2>d</h2>"
    fs = lint(html)
    assert "heading-hierarchy" not in _ids(fs)


# ---------------------------------------------------------------------------
# form-label
# ---------------------------------------------------------------------------


def test_form_label_flags_unlabeled_input():
    html = '<input type="text">'
    fs = lint(html)
    assert "form-label" in _ids(fs)


def test_form_label_passes_with_aria_label():
    html = '<input type="text" aria-label="Email">'
    fs = lint(html)
    assert "form-label" not in _ids(fs)


def test_form_label_passes_with_label_for():
    html = '<label for="e">Email</label><input id="e" type="email">'
    fs = lint(html)
    assert "form-label" not in _ids(fs)


def test_form_label_passes_when_wrapped_in_label():
    html = "<label>Email <input type='email'></label>"
    fs = lint(html)
    assert "form-label" not in _ids(fs)


def test_form_label_skips_button_inputs():
    html = '<input type="submit" value="Go">'
    fs = lint(html)
    assert "form-label" not in _ids(fs)


# ---------------------------------------------------------------------------
# leaked-secret
# ---------------------------------------------------------------------------


def test_leaked_secret_in_text_flagged():
    html = "<pre>sk-ant-1234567890abcdef1234567890abcdef</pre>"
    fs = [f for f in lint(html) if f.rule_id == "leaked-secret"]
    assert fs and "Anthropic" in fs[0].message


def test_leaked_secret_in_attribute_flagged():
    html = '<div data-key="ghp_abcdefghijklmnopqrst1234"></div>'
    fs = [f for f in lint(html) if f.rule_id == "leaked-secret"]
    assert fs and "GitHub" in fs[0].message


def test_leaked_secret_aws_pattern():
    html = "<p>AKIAIOSFODNN7EXAMPLE</p>"
    fs = [f for f in lint(html) if f.rule_id == "leaked-secret"]
    assert fs and "AWS" in fs[0].message


def test_leaked_secret_no_false_positive_on_prose():
    html = "<p>This sentence mentions SK and other prefixes harmlessly.</p>"
    fs = lint(html)
    assert "leaked-secret" not in _ids(fs)


# ---------------------------------------------------------------------------
# Helpers / utils
# ---------------------------------------------------------------------------


def test_parse_color_supports_hex_named_rgb_hsl():
    assert parse_color("#fff") is not None
    assert parse_color("red") is not None
    assert parse_color("rgb(0, 0, 0)") is not None
    assert parse_color("rgba(0,0,0,0.5)").a == 0.5
    assert parse_color("hsl(0, 100%, 50%)") is not None
    assert parse_color("transparent").a == 0
    assert parse_color("not-a-color") is None


def test_parse_color_hsl_matches_rgb_equivalent():
    # hsl(0, 100%, 50%) is pure red; hsl(0, 0%, 100%) is white.
    assert parse_color("hsl(0, 100%, 50%)") == parse_color("#ff0000")
    assert parse_color("hsl(0, 0%, 100%)") == parse_color("#ffffff")
    assert parse_color("hsl(120, 100%, 50%)") == parse_color("#00ff00")


def test_contrast_ratio_black_on_white_is_21():
    fg = parse_color("#000")
    bg = parse_color("#fff")
    assert round(contrast_ratio(fg, bg), 2) == 21.0


def test_contrast_ratio_composites_translucent_foreground():
    # A 50%-opaque black over white composites to mid-grey, so the contrast
    # ratio sits well below the 21:1 of opaque black on white.
    translucent = parse_color("rgba(0, 0, 0, 0.5)")
    white = parse_color("#fff")
    ratio = contrast_ratio(translucent, white)
    assert 1.0 < ratio < 21.0


def test_relative_luminance_white_is_one():
    assert round(relative_luminance(parse_color("#fff")), 4) == 1.0


def test_parse_css_size_pixels_and_rems():
    assert parse_css_size("16px") == 16
    assert parse_css_size("1rem") == 16
    assert parse_css_size("0.5em") == 8
    assert parse_css_size("12pt") == 16
    assert parse_css_size("100%") is None  # needs layout context
    assert parse_css_size("notasize") is None


def test_lint_returns_sorted_by_line():
    html = textwrap.dedent("""
        <html><body>
          <h2>missing h1</h2>
          <input type="text">
          <p style="color: #ccc; background-color: #fff">low</p>
        </body></html>
    """).strip()
    fs = lint(html)
    lines = [f.line for f in fs]
    assert lines == sorted(lines)


def test_lint_rejects_non_string_input():
    import pytest

    with pytest.raises(TypeError):
        lint(123)  # type: ignore[arg-type]
