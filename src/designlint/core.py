"""Public entrypoint for designlint-py."""

from __future__ import annotations

from typing import List

from .parse import parse_html
from .rules import ALL_RULES, Finding


def lint(html_string: str) -> List[Finding]:
    """Run every built-in rule against ``html_string``.

    Returns a flat list of :class:`Finding`s sorted by source line. The spec
    explicitly asks for ``list[Finding]`` (no score / summary wrapper).
    """
    if not isinstance(html_string, str):
        raise TypeError("designlint.lint: html_string must be a str")
    doc = parse_html(html_string)
    findings: List[Finding] = []
    for rule in ALL_RULES:
        findings.extend(rule(doc))
    findings.sort(key=lambda f: (f.line, f.rule_id))
    return findings
