"""The published decision must follow the registered gate and literal uniqueness rule."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import h67_publish_site


def test_historical_green_board_cannot_reappear():
    card = json.loads((ROOT / 'evidence/h67_runcard.json').read_text())
    status = json.loads((ROOT / 'registry/current_site_status.json').read_text())
    assert status['status'] == 'STOP'
    overlap = card['uniqueness_vs_registry']['final_dots']['max_dot_overlap_within_3px_all_68_rasters_literal']
    assert overlap > .70
    for prefix in ('', 'docs/'):
        text = h67_publish_site.board(prefix, card)
        assert 'DO NOT SUBMIT' in text and 'verdict NEGATIVE' in text
        assert 'PROMOTE TO CROSS-LANE SELECTOR' not in text
        assert '100% portal-legal' not in text
    for page in (ROOT / 'docs/index.html', ROOT / 'docs/executive-summary.html',
                 ROOT / 'index.html', ROOT / 'executive-summary.html'):
        page_text = page.read_text()
        # The current renderer now removes all historical marker boards on STOP.
        # The archival board function above still must be safe when inspected alone.
        assert 'DO NOT SUBMIT' in page_text
        assert 'STOP' in page_text
        assert 'PROMOTE TO CROSS-LANE SELECTOR' not in page_text
