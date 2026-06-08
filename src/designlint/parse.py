"""HTML walker built on Python's stdlib ``html.parser``.

We need a tree (or a simulated tree) so heading-hierarchy and form-label
rules can ask structural questions ("did this heading skip a level?",
"is this input nested inside a label?"). The standard library only gives us
a SAX-style event stream, so this module turns that into a list of typed
``Element`` records with parent + child indices and a 1-based source line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional


@dataclass
class Element:
    """One HTML element in the parsed tree."""

    tag: str
    attrs: dict[str, str]
    line: int
    # Direct text content (whitespace-stripped concatenation of text nodes
    # that sit immediately under this element). Good enough for heading text
    # and label text; full innerText would require recursion which the rules
    # here don't need.
    text: str = ""
    parent: Optional["Element"] = None
    children: List["Element"] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Result of :func:`parse_html`."""

    elements: List[Element]  # depth-first order
    raw: str


# Tags that never have closing tags. Mirrors the HTML5 void-element list.
_VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class _Walker(HTMLParser):
    def __init__(self, raw: str) -> None:
        # ``convert_charrefs=True`` decodes character references in text
        # nodes so secret/heading scanning sees the rendered text rather
        # than raw entities.
        super().__init__(convert_charrefs=True)
        self.raw = raw
        self.elements: List[Element] = []
        self._stack: List[Element] = []

    # -- helpers ----------------------------------------------------------

    def _line(self) -> int:
        # getpos returns (line, col); line is 1-based.
        return self.getpos()[0]

    def _push(self, el: Element) -> None:
        if self._stack:
            parent = self._stack[-1]
            el.parent = parent
            parent.children.append(el)
        self.elements.append(el)
        self._stack.append(el)

    def _pop(self, tag: str) -> None:
        # Pop until we close the matching tag (tolerates unclosed tags).
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                del self._stack[i:]
                return

    # -- HTMLParser callbacks --------------------------------------------

    def handle_starttag(self, tag, attrs):  # type: ignore[override]
        el = Element(
            tag=tag.lower(),
            attrs={(k or "").lower(): (v if v is not None else "") for k, v in attrs},
            line=self._line(),
        )
        if tag.lower() in _VOID:
            # Void elements don't open a scope; record + return.
            if self._stack:
                el.parent = self._stack[-1]
                self._stack[-1].children.append(el)
            self.elements.append(el)
            return
        self._push(el)

    def handle_startendtag(self, tag, attrs):  # type: ignore[override]
        # `<br/>` style. Treat as a self-closing element.
        el = Element(
            tag=tag.lower(),
            attrs={(k or "").lower(): (v if v is not None else "") for k, v in attrs},
            line=self._line(),
        )
        if self._stack:
            el.parent = self._stack[-1]
            self._stack[-1].children.append(el)
        self.elements.append(el)

    def handle_endtag(self, tag):  # type: ignore[override]
        self._pop(tag.lower())

    def handle_data(self, data):  # type: ignore[override]
        if not self._stack:
            return
        # Append stripped text to the innermost open element.
        cur = self._stack[-1]
        stripped = data.strip()
        if stripped:
            cur.text = (cur.text + " " + stripped).strip() if cur.text else stripped


def parse_html(html: str) -> ParsedDocument:
    """Parse ``html`` into a :class:`ParsedDocument`.

    Tag names are lowercased, attribute keys are lowercased. Void elements
    follow the HTML5 list. Unclosed tags are tolerated.
    """
    w = _Walker(html)
    w.feed(html)
    w.close()
    return ParsedDocument(elements=w.elements, raw=html)


def render_open_tag(el: Element, max_len: int = 80) -> str:
    """Best-effort ``<tag attr="...">`` snippet for finding messages."""
    if el.attrs:
        attrs = " ".join(
            f'{k}="{v.replace(chr(34), "&quot;")}"' for k, v in el.attrs.items()
        )
        s = f"<{el.tag} {attrs}>"
    else:
        s = f"<{el.tag}>"
    return s if len(s) <= max_len else s[: max_len - 3] + "..."
