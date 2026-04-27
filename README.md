# designlint-py

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**HTML/CSS accessibility and design linter** for contrast, touch targets, heading hierarchy, form labels, and leaked secrets. Stdlib-only -- no parser dependencies.

Python port of [@mukundakatta/designlint](https://github.com/MukundaKatta/designlint). The JS sibling has the broader ruleset (responsive images, viewport meta, etc.); this Python port focuses on the spec's five rule families and uses the standard library's `html.parser` for HTML walking.

## Install

```bash
pip install designlint-py
```

## Usage

```python
from designlint import lint

html = """
<html>
  <body>
    <p style="color: #ccc; background-color: #fff">low contrast</p>
    <a style="display: inline-block; width: 20px; height: 20px;">tap</a>
    <h1>Title</h1>
    <h3>Skipped a level</h3>
    <input type="text">
    <pre>sk-ant-1234567890abcdef1234567890abcdef</pre>
  </body>
</html>
"""

findings = lint(html)
for f in findings:
    print(f.line, f.severity, f.rule_id, f.message)
```

Each finding is a dataclass:

```python
Finding(
    rule_id="color-contrast",
    severity="error",
    message="Contrast ratio 1.61:1 is below WCAG AA minimum of 4.5:1.",
    line=4,
    snippet='<p style="color: #ccc; background-color: #fff">',
)
```

## Rules

| Rule id | Severity | Checks |
|---|---|---|
| `color-contrast` | error | Inline `color` vs `background-color` against WCAG 2.1 AA (4.5:1 normal, 3:1 large). |
| `touch-target-size` | warning | Interactive elements (`a`, `button`, `input[type=button/submit]`) below 24x24 CSS pixels. |
| `heading-hierarchy` | warning | First heading must be `h1`; no skipping levels (e.g. `h1` -> `h3`). |
| `form-label` | error | `input` / `select` / `textarea` without an associated `<label for>` or `aria-label`. |
| `leaked-secret` | error | Provider-shaped API keys (OpenAI, Anthropic, GitHub, AWS, Slack, Stripe, Google AI) in any text content or attribute value. |

## API

* `lint(html_string) -> list[Finding]` -- run the full ruleset.
* `Finding(rule_id, severity, message, line, snippet)` -- result dataclass.
* `parse_color(value) -> RGBA | None`, `contrast_ratio(fg, bg) -> float`, `parse_css_size(value) -> float | None` -- helpers exported for reuse.

## API differences from the JS sibling

* Stdlib-only: uses Python's `html.parser` instead of `parse5` + `css-tree`.
  Selector matching for `<style>` blocks is therefore omitted; only inline
  `style=...` attributes contribute to contrast/size analysis.
* Returns a flat `list[Finding]` instead of `{ issues, score, summary }` --
  matches the spec's `lint(html_string) -> list[Finding]` shape. Compute a
  score yourself if you need one.
* Rule set is the spec's five families. The JS port has additional rules
  (responsive images, viewport meta, link rel-noopener) that aren't in scope
  here.

See the JS sibling's [README](https://github.com/MukundaKatta/designlint) for
the broader rationale.
