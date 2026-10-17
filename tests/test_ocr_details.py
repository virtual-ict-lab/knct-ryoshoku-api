# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import copy
import json
from pathlib import Path

import pytest
from support import pdf_bytes

from ryoshoku_ocr.menu import build_menu, validate_menu
from ryoshoku_api.archive import Archive
from ryoshoku_api.publish import publish
from test_archive import cfg, ingest


CASE = json.loads((Path(__file__).parent / 'fixtures/contract.json').read_text())[0]


@pytest.mark.parametrize(('score', 'included', 'code'), [
    (0, False, 'low_confidence'),
    (.49999, False, 'low_confidence'),
    (.5, True, 'needs_review'),
    (.84999, True, 'needs_review'),
    (.85, True, None),
    (1, True, None),
])
def test_line_details_expose_scores_and_filter_boundaries(score, included, code):
    raw = copy.deepcopy(CASE['raw'])
    raw['cells'][1]['lines'] = [{'text': ' 牛乳（２００ｍｌ） ', 'confidence': score, 'box': []}]
    menu = build_menu(raw, 'a' * 64, '2026-10-17T00:00:00.000Z')
    meal = menu['days'][0]['lunch']
    assert meal['lines'] == [{
        'text': '牛乳(200ml)', 'rawText': ' 牛乳（２００ｍｌ） ',
        'confidence': score, 'included': included,
    }]
    assert meal['text'] == ('牛乳(200ml)' if included else '')
    assert meal['rawText'] == ' 牛乳（２００ｍｌ） '
    assert meal['issues'] == ([{'code': code, 'lineIndex': 0, 'confidence': score}] if code else [])
    assert len(meal['warnings']) == len(meal['issues'])


def test_issue_indices_reference_original_lines_including_omitted_lines():
    raw = copy.deepcopy(CASE['raw'])
    raw['cells'][1]['lines'] = [
        {'text': 'ごはん', 'confidence': .99921, 'box': []},
        {'text': '8', 'confidence': .12, 'box': []},
        {'text': '野菜ｻﾗﾀﾞ', 'confidence': .72, 'box': []},
    ]
    meal = build_menu(raw, 'a' * 64, '2026-10-17T00:00:00.000Z')['days'][0]['lunch']
    assert meal['lines'][0]['confidence'] == .99921
    assert meal['lines'][2]['text'] == '野菜サラダ'
    assert meal['text'] == 'ごはん\n野菜サラダ'
    assert meal['issues'] == [
        {'code': 'low_confidence', 'lineIndex': 1, 'confidence': .12},
        {'code': 'needs_review', 'lineIndex': 2, 'confidence': .72},
    ]
    assert meal['warnings'] == ['低信頼度のため表示省略 (0.12): 8', 'OCR要確認 (0.72): 野菜ｻﾗﾀﾞ']


def test_empty_meal_has_machine_readable_issue_without_invented_score():
    meal = build_menu(CASE['raw'], 'a' * 64, '2026-10-17T00:00:00.000Z')['days'][0]['breakfast']
    assert meal['lines'] == []
    assert meal['issues'] == [{'code': 'empty_result', 'lineIndex': None, 'confidence': None}]
    assert meal['warnings'] == ['読み取り結果が空です（未提供または認識できなかった可能性があります）']


@pytest.mark.parametrize(('target', 'field', 'value'), [
    ('line', 'confidence', -.1), ('line', 'confidence', 1.1),
    ('line', 'confidence', float('nan')), ('line', 'confidence', True),
    ('line', 'included', 1), ('line', 'included', False),
    ('line', 'text', None), ('line', 'rawText', None),
    ('issue', 'code', 'unknown'), ('issue', 'code', 'low_confidence'),
    ('issue', 'lineIndex', -1), ('issue', 'lineIndex', 1),
    ('issue', 'lineIndex', True), ('issue', 'confidence', .71),
    ('issue', 'confidence', None),
    ('meal', 'lines', None), ('meal', 'issues', None),
    ('meal', 'issues', []),
])
def test_validation_rejects_malformed_or_inconsistent_details(target, field, value):
    menu = copy.deepcopy(CASE['menu'])
    meal = menu['days'][0]['lunch']
    meal.update(text='牛乳', rawText='牛乳', warnings=['OCR要確認 (0.72): 牛乳'],
                lines=[{'text': '牛乳', 'rawText': '牛乳', 'confidence': .72, 'included': True}],
                issues=[{'code': 'needs_review', 'lineIndex': 0, 'confidence': .72}])
    subject = {'meal': meal, 'line': meal['lines'][0], 'issue': meal['issues'][0]}[target]
    subject[field] = value
    with pytest.raises(ValueError):
        validate_menu(menu)


def test_legacy_menus_remain_valid_but_partial_details_are_rejected():
    assert validate_menu(copy.deepcopy(CASE['menu'])) == CASE['menu']
    for field in ('lines', 'issues'):
        menu = copy.deepcopy(CASE['menu'])
        menu['days'][0]['lunch'][field] = []
        with pytest.raises(ValueError):
            validate_menu(menu)


def test_publish_upgrades_saved_ocr_without_changing_source_or_processing_time(tmp_path):
    config = cfg(tmp_path)
    archive = Archive(config)
    entry = ingest(archive, pdf_bytes(b'%PDF-existing'))
    directory = archive.snapshot(entry['sha256'])
    path = directory / 'menu.json'
    legacy = json.loads(path.read_text())
    for day in legacy['days']:
        for name in ('breakfast', 'lunch', 'dinner'):
            day[name].pop('lines', None)
            day[name].pop('issues', None)
    path.write_text(json.dumps(legacy, ensure_ascii=False))
    raw_before = (directory / 'raw.json').read_bytes()
    state_before = archive.path.read_bytes()

    publish(config, today='2026-10-17')

    api = json.loads((config.public_dir / 'kondate.json').read_text())
    menu = api['weeks'][0]
    assert menu['days'][0]['lunch']['issues'] == [
        {'code': 'needs_review', 'lineIndex': 0, 'confidence': .72},
        {'code': 'low_confidence', 'lineIndex': 1, 'confidence': .26},
    ]
    assert menu['fetchedAt'] == legacy['fetchedAt']
    assert menu['warnings'] == legacy['warnings']
    assert (directory / 'raw.json').read_bytes() == raw_before
    assert (directory / 'source.pdf').read_bytes() == pdf_bytes(b'%PDF-existing')
    assert archive.path.read_bytes() == state_before
    saved = path.read_bytes()
    assert json.loads(saved) == menu
    assert json.loads((config.public_dir / api['current']['json']).read_text()) == menu
    mtime = path.stat().st_mtime_ns
    publish(config, today='2026-10-17')
    assert path.read_bytes() == saved
    assert path.stat().st_mtime_ns == mtime


def test_invalid_raw_cannot_replace_legacy_snapshot_or_current_publication(tmp_path):
    config = cfg(tmp_path)
    archive = Archive(config)
    entry = ingest(archive, pdf_bytes(b'%PDF-existing'))
    publish(config, today='2026-10-17')
    before = (config.public_dir / 'kondate.json').read_bytes()
    directory = archive.snapshot(entry['sha256'])
    path = directory / 'menu.json'
    legacy = json.loads(path.read_text())
    for day in legacy['days']:
        for name in ('breakfast', 'lunch', 'dinner'):
            day[name].pop('lines', None)
            day[name].pop('issues', None)
    path.write_text(json.dumps(legacy, ensure_ascii=False))
    legacy_bytes = path.read_bytes()
    raw = json.loads((directory / 'raw.json').read_text())
    raw['headerText'] = '2026/10/19～2026/10/25'
    (directory / 'raw.json').write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        publish(config, today='2026-10-17')
    assert path.read_bytes() == legacy_bytes
    assert (config.public_dir / 'kondate.json').read_bytes() == before
