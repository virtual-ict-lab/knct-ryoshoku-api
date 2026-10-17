# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import copy
import hashlib
import json
from pathlib import Path
from datetime import datetime
import pytest
from support import pdf_bytes
from ryoshoku_api.config import Config
from ryoshoku_api.archive import Archive, select_menus
from ryoshoku_api.publish import publish

FIX = Path(__file__).parent / 'fixtures'
RAW = json.loads((FIX / 'contract.json').read_text())[0]['raw']

def cfg(tmp_path):
    return Config(data_dir=tmp_path / 'data', public_dir=tmp_path / 'public')

def raw_for(start, end, columns=7):
    value = copy.deepcopy(RAW)
    value['headerText'] = f'{start}～{end}'
    value['columns'] = columns
    value['cells'] = [copy.deepcopy(c) for c in RAW['cells'] if c['column'] < columns]
    if columns > 5:
        for column in range(5, columns):
            for meal in ('breakfast','lunch','dinner'):
                cell = copy.deepcopy(RAW['cells'][1]); cell.update(column=column, meal=meal)
                value['cells'].append(cell)
    return value

def ingest(archive, data, start='2026/10/12', end='2026/10/18', raw=None):
    return archive.ingest(data, raw=raw or raw_for(start,end))

def test_new_revision_and_official_rollback_reuse_original_ocr(tmp_path):
    archive=Archive(cfg(tmp_path))
    first=ingest(archive,b'%PDF-original')
    revised=ingest(archive,b'%PDF-revised')
    assert first['seq']==1 and revised['seq']==2
    # Previously seen PDF must be selected again without inference.
    original=archive.ingest(b'%PDF-original')
    assert original['sha256']==first['sha256']
    state=archive.load()
    selected=select_menus(state['menus'], '2026-10-17')
    assert selected['current']['sha256']==first['sha256']
    assert len(state['menus'])==2
    assert sum(e['preferred'] for e in state['menus'])==1

def test_publish_keeps_current_until_jst_monday_even_when_source_unchanged(tmp_path):
    config=cfg(tmp_path); archive=Archive(config)
    current=ingest(archive,pdf_bytes(b'%PDF-current'))
    upcoming=ingest(archive,pdf_bytes(b'%PDF-next'), '2026/10/19','2026/10/25')
    publish(config, instant=datetime.fromisoformat('2026-10-18T14:59:59+00:00'))
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-current')
    sunday=json.loads((config.public_dir/'kondate.json').read_text())
    assert sunday['current']['sourceSha256']==current['sha256']
    assert sunday['upcoming']['sourceSha256']==upcoming['sha256']
    assert len(sunday['weeks'])==2
    publish(config, instant=datetime.fromisoformat('2026-10-18T15:07:00+00:00'))
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-next')
    monday=json.loads((config.public_dir/'kondate.json').read_text())
    assert monday['current']['startDate']=='2026-10-19'
    assert monday['publishedForDate']=='2026-10-19'

def test_missing_current_is_explicit_and_does_not_serve_stale_or_future_pdf(tmp_path):
    config=cfg(tmp_path);archive=Archive(config)
    ingest(archive,pdf_bytes(b'%PDF-current'))
    publish(config,today='2026-10-17')
    publish(config,today='2026-10-26')
    assert not (config.public_dir/'kondate.pdf').exists()
    assert json.loads((config.public_dir/'kondate.json').read_text())['current'] is None

def test_invalid_ocr_cannot_change_archive_or_published_files(tmp_path):
    config=cfg(tmp_path);archive=Archive(config)
    ingest(archive,pdf_bytes(b'%PDF-current'));publish(config,today='2026-10-17')
    before=(config.data_dir/'state.json').read_bytes()
    with pytest.raises(ValueError): archive.ingest(b'%PDF-invalid',raw={})
    assert (config.data_dir/'state.json').read_bytes()==before
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-current')
    assert len(archive.load()['menus'])==1

def test_broken_snapshot_cannot_replace_published_generation(tmp_path):
    config=cfg(tmp_path);archive=Archive(config)
    entry=ingest(archive,pdf_bytes(b'%PDF-current'));publish(config,today='2026-10-17')
    before=(config.public_dir/'kondate.json').read_bytes()
    (config.data_dir/'snapshots'/entry['sha256']/'menu.json').write_text('{}')
    with pytest.raises(ValueError): publish(config,today='2026-10-17')
    assert (config.public_dir/'kondate.json').read_bytes()==before
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-current')

def test_legacy_import_reads_printed_periods_keeps_urls_and_is_repeatable(tmp_path):
    config=cfg(tmp_path);archive=Archive(config)
    legacy=FIX/'legacy'
    archive.import_cache(legacy)
    state=archive.load()
    assert len(state['menus'])==8
    entry=next(e for e in state['menus'] if e['seq']==7)
    assert entry['start_date']=='2026-10-12'
    assert entry['path']=='archive/2026/0007_2026-08-10_2026-08-16.pdf'
    assert archive.snapshot(entry['sha256']).joinpath('source.pdf').read_bytes()==(legacy/entry['path']).read_bytes()
    archive.import_cache(legacy)
    assert len(archive.load()['menus'])==8


def test_repeat_import_does_not_reactivate_stale_legacy_preferences(tmp_path):
    archive=Archive(cfg(tmp_path));legacy=FIX/'legacy'
    archive.import_cache(legacy)
    revision=ingest(archive,b'%PDF-new-correction')
    archive.import_cache(legacy)
    state=archive.load()
    assert select_menus(state['menus'],'2026-10-17')['current']['sha256']==revision['sha256']
    assert state['latest_pdf_hash']==revision['sha256']


def test_incomplete_unreferenced_snapshot_is_repaired_on_retry(tmp_path):
    config=cfg(tmp_path);archive=Archive(config)
    data=b'%PDF-retry';digest=hashlib.sha256(data).hexdigest()
    directory=archive.snapshot(digest);directory.mkdir(parents=True)
    (directory/'source.pdf').write_bytes(b'%PD')
    entry=ingest(archive,data)
    assert archive.menu(entry)['sourceSha256']==digest
    assert (directory/'source.pdf').read_bytes()==data


def test_publication_uses_one_complete_generation_and_recovers_old_backup(tmp_path):
    config=cfg(tmp_path);archive=Archive(config)
    entry=ingest(archive,pdf_bytes(b'%PDF-current'));publish(config,today='2026-10-17')
    assert config.public_dir.is_symlink()
    old=config.public_dir.resolve()
    ingest(archive,pdf_bytes(b'%PDF-next'),'2026/10/19','2026/10/25')
    publish(config,today='2026-10-19')
    assert (old/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-current')
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-next')
