"""Shared checks for rendered member copy, never private source quotations."""
import re
from html.parser import HTMLParser

FORBIDDEN_TERMS = (
    'not supplied', 'undecided', 'eligible', "Writer's", 'cohort',
    'SYNTHETIC', 'saved review', 'Execution and effect apart', 'stage starts',
)
FIELD_NAME_PATTERN = r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b'
RAW_FLOAT_PATTERN = r'(?<![\w.])[-+]?\d+\.\d{3,}(?:[eE][-+]?\d+)?(?![\w.])'
DECIMAL_RATE_PATTERN = r'(?<![\w.])\d+\.\d+\s*%'


class MemberText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.excluded = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('head', 'style', 'script', 'template', 'title'):
            self.excluded += 1

    def handle_endtag(self, tag):
        if tag in ('head', 'style', 'script', 'template', 'title'):
            self.excluded -= 1

    def handle_data(self, data):
        if not self.excluded:
            self.parts.append(data)


def member_text(markup):
    parser = MemberText()
    parser.feed(markup)
    return ' '.join(' '.join(parser.parts).split())


def assert_member_copy(markup, label='member copy', extra_terms=()):
    text = member_text(markup)
    for term in (*FORBIDDEN_TERMS, *extra_terms):
        assert term.casefold() not in text.casefold(), (label, term, text)
    for pattern in (FIELD_NAME_PATTERN, RAW_FLOAT_PATTERN, DECIMAL_RATE_PATTERN):
        match = re.search(pattern, text, re.I)
        assert match is None, (label, match.group() if match else pattern, text)
    return text


def self_check():
    """Prove the checker catches each rule and ignores hidden implementation text."""
    for bad in (*FORBIDDEN_TERMS, 'reply_rate', '1.234', '21.428571%', '21.4%', '-0.123456', '1.234e-05'):
        for surface in ('This week', 'Conversations', 'Achievements', 'drawer', 'call', 'community'):
            try:
                assert_member_copy(f'<p>{bad}</p>', surface)
            except AssertionError:
                pass
            else:
                raise AssertionError((surface, 'Checker missed', bad))
    assert_member_copy('<head><title>SYNTHETIC</title></head><p data-key="reply_rate">21%</p>')


if __name__ == '__main__':
    from analytics_fixture import ROOT, rendered_ui
    assert (ROOT / 'website/node_modules').is_dir(), 'Rendered proof needs website/node_modules.'
    self_check()
    assert_member_copy((ROOT / 'references/chat-report-example.md').read_text(), 'Maya chat report')
    rendered_ui()
    print('PASS forbidden terms: all three tabs, open details, both drawers, calls and community; SYNTHETIC, saved review, raw floats and decimal rates rejected.')
