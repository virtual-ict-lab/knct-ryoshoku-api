# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import replace
import json

import pytest

from ryoshoku_api.archive import Archive
from ryoshoku_api.publish import publish
from support import pdf_bytes
from test_archive import cfg, ingest, raw_for


@pytest.mark.parametrize('same_pdf', [False, True])
def test_successful_ingestion_updates_source_in_saved_and_published_metadata(tmp_path, same_pdf):
    config = replace(cfg(tmp_path), pdf_url='https://old.example/menu.pdf')
    archive = Archive(config)
    first = ingest(archive, pdf_bytes(b'original'))
    processed_at = archive.menu(first)['fetchedAt']
    changed = replace(config, pdf_url='https://new.example/menu.pdf')
    incoming = pdf_bytes(b'original' if same_pdf else b'new-source')
    updated = Archive(changed)
    updated.ingest(incoming, raw=None if same_pdf else raw_for('2026/10/12', '2026/10/18'))
    publish(changed, today='2026-10-17')
    assert updated.load()['source_url'] == 'https://new.example/menu.pdf'
    assert json.loads((changed.public_dir / 'state.json').read_text())['source_url'] == 'https://new.example/menu.pdf'
    assert json.loads((changed.public_dir / 'kondate.json').read_text())['sourceUrl'] == 'https://new.example/menu.pdf'
    assert len(updated.load()['menus']) == (1 if same_pdf else 2)
    assert updated.menu(first)['fetchedAt'] == processed_at


def test_failed_ingestion_keeps_previous_source_metadata_and_publication(tmp_path):
    config = replace(cfg(tmp_path), pdf_url='https://old.example/menu.pdf')
    archive = Archive(config)
    ingest(archive, pdf_bytes())
    publish(config, today='2026-10-17')
    before = archive.path.read_bytes()
    changed = replace(config, pdf_url='https://new.example/menu.pdf')
    with pytest.raises(ValueError):
        Archive(changed).ingest(pdf_bytes(b'bad-ocr'), raw={})
    assert archive.path.read_bytes() == before
    publish(changed, today='2026-10-17')
    assert json.loads((changed.public_dir / 'kondate.json').read_text())['sourceUrl'] == 'https://old.example/menu.pdf'
