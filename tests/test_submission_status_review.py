"""Regressions for contradictory promotion banners and literal uniqueness bypass."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stopped_renderer_removes_banners_from_old_and_new_html(tmp_path, monkeypatch):
    builder = load('build_site')
    monkeypatch.setattr(builder, 'read', lambda *a: {'status': 'STOP'})
    path = tmp_path / 'index.html'
    banner = '<!-- H67-STATUS:BEGIN -->PROMOTE<!-- H67-STATUS:END -->'
    path.write_text('<body>' + banner + '</body>')
    new = '<body>' + banner + 'DO NOT SUBMIT</body>'
    rendered = builder.preserve_status_blocks(path, new)
    assert rendered == '<body>DO NOT SUBMIT</body>'
    assert builder.preserve_status_blocks(path, rendered) == rendered


@pytest.mark.parametrize('record', [None, {}, [], {'verdict': 'UNKNOWN'}, {'verdict': 'INCONCLUSIVE'}])
def test_active_lane_without_affirmative_evidence_fails_closed(tmp_path, record):
    (tmp_path / 'registry').mkdir()
    (tmp_path / 'evidence').mkdir()
    state = {'status': 'ACTIVE', 'active_lane': 'channel-steepness',
             'latest_first_test': {'result': 'PROCEED', 'evidence': 'evidence/current.json'}}
    (tmp_path / 'registry/current_site_status.json').write_text(json.dumps(state))
    if record is not None:
        (tmp_path / 'evidence/current.json').write_text(json.dumps(record))
    assert load('stop_guard').lane_is_stopped(tmp_path, 'test')


@pytest.mark.parametrize('overlap,rho,complete,expected', [
    (0.70, 0.90, True, True), (0.70001, 0, True, False),
    (0.998675, 0.1106, True, False), (0.2, 0.90001, True, False),
    (0.2, -0.90001, True, False), (0.2, 0.3, False, False),
    (float('nan'), 0, True, False), (0, float('nan'), True, False),
    (0, 0, None, False),
])
def test_literal_uniqueness_thresholds(overlap, rho, complete, expected):
    assert load('selector').literal_uniqueness(overlap, rho, complete) is expected


def test_published_h67_cards_do_not_override_failed_literal_gate():
    paths = [ROOT / 'submission_card.json', ROOT / 'evidence/h67_runcard.json']
    paths += list((ROOT / 'docs/downloads').glob('*dbafa4373009*-runcard.json'))
    assert len(paths) == 3
    for path in paths:
        card = json.loads(path.read_text())
        assert card['verdict'] == 'negative'
        assert card['selector_and_portal_decision']['promote_to_cross_lane_selector'] is False
        assert card['uniqueness_vs_registry']['final_dots']['literal_tool_verdict_unique'] is False


def test_review_artifact_is_existing_not_new_or_promoted():
    card = json.loads((ROOT / 'evidence/review_run_card.json').read_text())
    assert card['new_raster_generated'] is False
    assert card['experiment_count_this_review'] == 0
    assert card['verdict'] == 'negative'
    assert card['submit_to_competition'] is False
    assert card['validator_output']['ok'] is True
    assert card['validator_output']['pinned_sha256_matches'] is True
    assert len(card['note']) <= 140


def test_current_front_pages_have_no_historic_promotion_banners():
    for rel in ('docs/index.html', 'docs/executive-summary.html', 'index.html', 'executive-summary.html'):
        text = (ROOT / rel).read_text()
        assert 'H67-STATUS:BEGIN' not in text
        assert 'H66-STATUS:BEGIN' not in text
        assert 'DO NOT SUBMIT' in text


def test_historical_publishers_cannot_restore_promote_while_stopped():
    import subprocess
    for script in ('h67_publish_site.py', 'h67_runcard.py', 'selector.py'):
        proc = subprocess.run([sys.executable, str(ROOT / 'scripts' / script)],
                              cwd=ROOT, capture_output=True, text=True, timeout=30)
        assert proc.returncode == 2, (script, proc.stderr)
        assert 'STOP GUARD' in proc.stdout
