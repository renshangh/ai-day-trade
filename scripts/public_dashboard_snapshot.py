"""Produce the public HTML shell without changing the local private review."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re


class Sections(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.lines = [0]
        for line in text.splitlines(keepends=True):
            self.lines.append(self.lines[-1] + len(line))
        self.stack = []
        self.ranges = {}

    def char_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == 'section':
            self.stack.append((dict(attrs).get('id'), self.char_offset()))

    def handle_endtag(self, tag):
        if tag == 'section' and self.stack:
            ident, start = self.stack.pop()
            if ident:
                self.ranges[ident] = (start, self.char_offset() + len('</section>'))


def public_html(text):
    parser = Sections(text)
    parser.feed(text)
    key = 'daily-holdings-checklist'
    if key in parser.ranges:
        start, end = parser.ranges[key]
        replacement = ('<section class="session-vwap" id="daily-holdings-checklist">'
                       '<h3 class="rev-h3">Private holdings review</h3>'
                       '<p>Account-specific snapshots remain local. Use the linked-account '
                       'review on your own Trading Desk; GitHub contains the public application '
                       'shell and market research only.</p></section>')
        text = text[:start] + replacement + text[end:]
    # The dated earnings rotation paragraph contains owner transactions, not
    # generic earnings behavior. Do not publish that local notebook entry.
    text = re.sub(r'<p\b[^>]*>October 19 rotation completed.*?</p>', '', text, flags=re.S)
    if re.search(r'\*\*\*\d{3,4}\s+[^<]{0,40}\bshares\b', text):
        raise ValueError('Account-linked share snapshot remains; review before publication')
    return re.sub(r'(?m)^[\t ]+$', '', text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    args = p.parse_args()
    if args.source.resolve() == args.destination.resolve():
        p.error('Use a separate output file; preserve the local review')
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(public_html(args.source.read_text()))


if __name__ == '__main__':
    main()
