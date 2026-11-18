"""Publication strips private notebook content without changing public routes."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.public_dashboard_snapshot import public_html


def test_nested_private_section_is_removed_without_removing_following_public_content():
    text='''<main><section id="daily-holdings-checklist"><h3>Private</h3>
<section><p>***1234 987 shares</p></section></section>
<section id="research"><p>Public BTC review</p></section></main>'''
    public=public_html(text)
    assert '987 shares' not in public and '***1234' not in public
    assert 'id="daily-holdings-checklist"' in public
    assert '<section id="research"><p>Public BTC review</p></section>' in public


def test_other_account_linked_share_snapshot_blocks_publication():
    with pytest.raises(ValueError,match='Account-linked'):
        public_html('<p>***5678 123 shares</p>')


def test_owner_rotation_is_not_generic_earnings_content():
    text='<p class="sub">October 19 rotation completed · private fills</p><p>Public earnings evidence</p>'
    assert public_html(text)=='<p>Public earnings evidence</p>'
