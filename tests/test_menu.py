# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import copy
import json
from pathlib import Path
import pytest
from ryoshoku_ocr.menu import build_menu, validate_cache

# Golden output captured from the original TypeScript implementation.
CASES = json.loads((Path(__file__).parent / 'fixtures/contract.json').read_text())

@pytest.mark.parametrize('case', CASES)
def test_matches_original_typescript_formatting(case):
    menu = build_menu(case['raw'], 'a' * 64, '2026-10-17T00:00:00.000Z')
    # New fields are additive; keep the independently captured legacy contract.
    for day in menu['days']:
        for meal in ('breakfast', 'lunch', 'dinner'):
            del day[meal]['lines']
            del day[meal]['issues']
    assert menu == case['menu']

@pytest.mark.parametrize('mutation', ['date', 'missing', 'duplicate', 'confidence', 'empty'])
def test_rejects_invalid_or_unreadable_menu(mutation):
    raw = copy.deepcopy(CASES[0]['raw'])
    if mutation == 'date': raw['headerText'] = '2026年2月30日～2026年3月6日'
    if mutation == 'missing': raw['cells'].pop()
    if mutation == 'duplicate': raw['cells'][-1] = raw['cells'][-2]
    if mutation == 'confidence': raw['cells'][1]['lines'][0]['confidence'] = float('nan')
    if mutation == 'empty':
        for cell in raw['cells']: cell['lines'] = []
    with pytest.raises(ValueError):
        build_menu(raw, 'a' * 64, '2026-10-17T00:00:00.000Z')

def test_cache_validation_rejects_unknown_versions_and_invalid_week():
    assert validate_cache({'schemaVersion': 1, 'weeks': [CASES[0]['menu']]})['weeks']
    for value in [{'schemaVersion': 2, 'weeks': []}, {'schemaVersion': 1, 'weeks': [{}]}]:
        with pytest.raises(ValueError): validate_cache(value)


def test_cache_rejects_timestamp_not_supported_by_consumer():
    menu = copy.deepcopy(CASES[0]['menu'])
    menu['fetchedAt'] = '2026-10-17T00:00:00+00:00'
    with pytest.raises(ValueError):
        validate_cache({'schemaVersion': 1, 'weeks': [menu]})


def test_warning_confidence_rounding_matches_javascript_exact_ties():
    raw = copy.deepcopy(CASES[0]['raw'])
    raw['cells'][1]['lines'][0]['confidence'] = .625
    menu = build_menu(raw, 'a' * 64, '2026-10-17T00:00:00.000Z')
    assert menu['days'][0]['lunch']['warnings'][0].startswith('OCR要確認 (0.63):')
