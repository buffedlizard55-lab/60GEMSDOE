#!/usr/bin/env python3
"""Read-only artifact audit using the shared validator; never generates a raster.

Writes an evidence receipt and a negative review run card. Historical holdout
and uniqueness results are explicitly marked as inherited, not newly measured.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gems57.gates import format_report  # noqa: E402


def main():
    status = json.loads((ROOT / 'registry/current_site_status.json').read_text())
    sample = ROOT / 'data/official/sample_submission.tif'
    with rasterio.open(sample) as src:
        footprint = np.isfinite(src.read(1)) & (src.read_masks(1) > 0)
    reports = []
    for path in sorted((ROOT / 'docs/downloads').glob('*.tif')):
        try:
            report = format_report(path, sample, footprint=footprint)
            report['path'] = str(path.relative_to(ROOT))
        except Exception as exc:
            report = {'path': str(path.relative_to(ROOT)), 'ok': False,
                      'problems': [f'{type(exc).__name__}: {exc}']}
        reports.append(report)
    artifact = status['research_artifact']
    current = next(r for r in reports if r['path'] == artifact['path'])
    current['pinned_sha256_matches'] = current.get('sha256') == artifact['sha256']
    receipt = {'review_date': '2026-10-11', 'kind': 'LOCAL FORMAT AUDIT, not organizer acceptance',
               'sample': str(sample.relative_to(ROOT)), 'rasters': reports,
               'raster_count': len(reports), 'format_pass_count': sum(r['ok'] for r in reports),
               'new_rasters_created': 0, 'slots_used': 0}
    (ROOT / 'evidence/submission_status_audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    card = {
        'run': 'a856d257-review', 'hypothesis': 'Strike-aligned channel steepness steps across independent drainages indicate unmapped faults.',
        'mechanism': 'Fault-driven base-level changes can generate chi-profile breaks; not every break is tectonic.',
        'named_non_fault_process': 'Lithologic erodibility contacts and playa base-level change.',
        'experiment_count_this_review': 0, 'new_raster_generated': False,
        'holdout_dti': dict(status['latest_holdout'], provenance='Inherited H65-1 evidence; not rerun in this review'),
        'correlation_overlap_vs_registry': dict(status['registry_uniqueness_review'], provenance='Inherited; incomplete scan, not rerun'),
        'raster_role': 'Existing H65-1 research artifact, NOT a new submission',
        'raster_sha256': current.get('sha256'), 'validator_output': current,
        'submission_name': artifact['submission_name'], 'note': artifact['note'],
        'verdict': 'negative', 'download_for_research': True, 'submit_to_competition': False,
        'reason': 'Binding first-test STOP and failed literal uniqueness. No selector promotion, no slot used.'
    }
    (ROOT / 'evidence/review_run_card.json').write_text(json.dumps(card, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'rasters'}, indent=2))
    if not current['ok'] or not current['pinned_sha256_matches']:
        raise SystemExit('Active research artifact failed validation or hash pin')


if __name__ == '__main__':
    main()
