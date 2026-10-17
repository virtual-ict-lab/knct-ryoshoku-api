# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Version 1 menu contract and OCR-to-menu formatting, independent of Discord."""
import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

MEALS = ('breakfast', 'lunch', 'dinner')
DISPLAY_CONFIDENCE = .5
REVIEW_CONFIDENCE = .85


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def confidence_text(value):
    # Match Number.toFixed: preserve the actual binary float and round ties up.
    return format(Decimal.from_float(float(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')


def normalize_text(text):
    text = unicodedata.normalize('NFKC', text).replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub('[\u200b-\u200d\ufeff]', '', text)
    return '\n'.join(line for part in text.split('\n') if (line := re.sub(r'[\t ]+', ' ', part).strip()))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strings(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def valid_date(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'Invalid date')
    return date.fromisoformat(value)


def valid_confidence(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def line_issues(lines):
    if not lines:
        return [{'code': 'empty_result', 'lineIndex': None, 'confidence': None}]
    return [
        {'code': 'low_confidence' if line['confidence'] < DISPLAY_CONFIDENCE else 'needs_review',
         'lineIndex': index, 'confidence': line['confidence']}
        for index, line in enumerate(lines) if line['confidence'] < REVIEW_CONFIDENCE
    ]


def build_meal(raw_lines):
    lines = [
        {'text': normalize_text(line['text']), 'rawText': line['text'],
         'confidence': line['confidence'], 'included': line['confidence'] >= DISPLAY_CONFIDENCE}
        for line in raw_lines
    ]
    issues = line_issues(lines)
    warnings = []
    for issue in issues:
        if issue['code'] == 'empty_result':
            warnings.append('読み取り結果が空です（未提供または認識できなかった可能性があります）')
        else:
            label = '低信頼度のため表示省略' if issue['code'] == 'low_confidence' else 'OCR要確認'
            warnings.append(f"{label} ({confidence_text(issue['confidence'])}): {lines[issue['lineIndex']]['rawText']}")
    return {
        'rawText': '\n'.join(line['rawText'] for line in lines),
        'text': normalize_text('\n'.join(line['rawText'] for line in lines if line['included'])),
        'warnings': warnings, 'lines': lines, 'issues': issues,
    }


def validate_meal(value):
    require(isinstance(value, dict) and isinstance(value.get('text'), str) and isinstance(value.get('rawText'), str) and strings(value.get('warnings')), 'Invalid meal')
    # Legacy v1 snapshots are accepted for offline migration from saved raw OCR.
    if 'lines' not in value and 'issues' not in value:
        return
    lines, issues = value.get('lines'), value.get('issues')
    require(isinstance(lines, list) and isinstance(issues, list), 'Invalid meal lines or issues')
    for line in lines:
        require(isinstance(line, dict) and isinstance(line.get('text'), str) and isinstance(line.get('rawText'), str), 'Invalid menu line text')
        require(valid_confidence(line.get('confidence')), 'Invalid menu line confidence')
        require(type(line.get('included')) is bool and line['included'] == (line['confidence'] >= DISPLAY_CONFIDENCE), 'Invalid menu line inclusion')
        require(line['text'] == normalize_text(line['rawText']), 'Menu line text does not match rawText')
    for issue in issues:
        require(isinstance(issue, dict) and issue.get('code') in ('low_confidence', 'needs_review', 'empty_result'), 'Invalid issue code')
        if issue['code'] == 'empty_result':
            require('lineIndex' in issue and issue['lineIndex'] is None and 'confidence' in issue and issue['confidence'] is None, 'Invalid empty-result issue')
        else:
            require(type(issue.get('lineIndex')) is int and 0 <= issue['lineIndex'] < len(lines), 'Invalid issue lineIndex')
            require(valid_confidence(issue.get('confidence')), 'Invalid issue confidence')
    require(issues == line_issues(lines), 'Issues do not match OCR lines')
    require(len(value['warnings']) == len(issues), 'Warnings do not match issues')
    require(value['rawText'] == '\n'.join(line['rawText'] for line in lines), 'Meal rawText does not match lines')
    require(value['text'] == normalize_text('\n'.join(line['rawText'] for line in lines if line['included'])), 'Meal text does not match included lines')


def validate_raw(raw):
    require(isinstance(raw, dict) and type(raw.get('schemaVersion')) is int and raw['schemaVersion'] == 1, 'Invalid raw schemaVersion')
    require(isinstance(raw.get('engine'), str) and raw['engine'], 'Invalid OCR engine')
    require(isinstance(raw.get('headerText'), str), 'Invalid headerText')
    require(type(raw.get('columns')) is int and 1 <= raw['columns'] <= 7, 'Invalid day columns')
    require(isinstance(raw.get('cells'), list), 'Invalid cells')
    for cell in raw['cells']:
        require(isinstance(cell, dict) and type(cell.get('column')) is int and cell['column'] >= 0 and cell.get('meal') in MEALS, 'Invalid cell')
        def numbers(value, length=None):
            return isinstance(value, (list, tuple)) and (length is None or len(value) == length) and all(type(n) in (int, float) and math.isfinite(n) for n in value)
        require(numbers(cell.get('bbox'), 4), 'Invalid cell bbox')
        require(isinstance(cell.get('lines'), list), 'Invalid OCR lines')
        for line in cell['lines']:
            require(isinstance(line, dict) and isinstance(line.get('text'), str), 'Invalid OCR text')
            score = line.get('confidence')
            require(valid_confidence(score), 'Invalid confidence')
            require(isinstance(line.get('box'), list) and all(numbers(p, 2) for p in line['box']), 'Invalid line box')
    return raw


def validate_menu(menu):
    require(isinstance(menu, dict) and type(menu.get('schemaVersion')) is int and menu['schemaVersion'] == 1, 'Invalid menu schemaVersion')
    require(isinstance(menu.get('engine'), str), 'Invalid engine')
    require(isinstance(menu.get('sourceSha256'), str) and re.fullmatch('[a-f0-9]{64}', menu['sourceSha256']), 'Invalid sourceSha256')
    timestamp = menu.get('fetchedAt')
    require(isinstance(timestamp, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z', timestamp), 'Invalid fetchedAt')
    instant = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    require(instant.tzinfo is not None, 'Invalid fetchedAt timezone')
    start, end = valid_date(menu.get('startDate')), valid_date(menu.get('endDate'))
    days = menu.get('days')
    require(isinstance(days, list) and 1 <= len(days) <= 7 and start + timedelta(days=len(days)-1) == end, 'Invalid menu date range')
    require(strings(menu.get('warnings')), 'Invalid warnings')
    for offset, day in enumerate(days):
        require(isinstance(day, dict) and valid_date(day.get('date')) == start + timedelta(days=offset), 'Invalid day date')
        for meal in MEALS:
            validate_meal(day.get(meal))
    return menu


def validate_cache(cache):
    require(isinstance(cache, dict) and type(cache.get('schemaVersion')) is int and cache['schemaVersion'] == 1, 'Invalid cache schemaVersion')
    require(isinstance(cache.get('weeks'), list), 'Invalid weeks')
    for menu in cache['weeks']:
        validate_menu(menu)
    return cache


def build_menu(raw, source_sha256, fetched_at):
    raw = validate_raw(raw)
    header = re.sub(r'\s', '', normalize_text(raw['headerText']))
    header = re.sub(r'(\d{4})年(\d{1,2})月(\d{1,2})日', r'\1/\2/\3', header)
    header = re.sub(r'\([月火水木金土日]\)', '', header)
    match = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})[~〜～―-]+(\d{4})[/-](\d{1,2})[/-](\d{1,2})', header)
    require(match is not None, 'Could not read the menu date range from the PDF')
    parts = [int(n) for n in match.groups()]
    start, end = date(*parts[:3]), date(*parts[3:])
    require(start + timedelta(days=raw['columns']-1) == end, 'PDF date range does not match the number of day columns')
    require(len(raw['cells']) == raw['columns'] * 3, 'Menu cells are missing')
    days, warnings = [], []
    for column in range(raw['columns']):
        day = {'date': (start + timedelta(days=column)).isoformat()}
        for meal in MEALS:
            cells = [c for c in raw['cells'] if c['column'] == column and c['meal'] == meal]
            require(len(cells) == 1, 'Menu cells are duplicated or missing')
            day[meal] = build_meal(cells[0]['lines'])
            if day[meal]['issues']:
                warnings.append(f"{day['date']} {meal}: {len(day[meal]['issues'])}行の認識を確認してください")
        days.append(day)
    require(any(day[meal]['text'] for day in days for meal in MEALS), 'No dish names could be read from the menu')
    return validate_menu(dict(schemaVersion=1, engine=raw['engine'], sourceSha256=source_sha256, fetchedAt=fetched_at, startDate=start.isoformat(), endDate=end.isoformat(), days=days, warnings=warnings))
