# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Acquisition and publication are independent, so rollover survives outages."""
import logging
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
from ryoshoku_ocr.store import atomic_json
from ryoshoku_ocr.service import download_pdf
from .archive import Archive
from .publish import publish

log = logging.getLogger('api.update')


def update(config, *, ocr=None, stop=None, today=None):
    archive = Archive(config)
    with archive.lock():
        before = archive.load()
        try:
            data = download_pdf(config, stop)
            archive.ingest(data, ocr=ocr, stop=stop)
            archive.transcribe_pending(ocr=ocr, stop=stop)
        except Exception:
            if stop is None or not stop.is_set():
                try:
                    publish(config, today=today)
                except (OSError, ValueError):
                    log.warning('Could not rebuild from cached data; keeping previous publication')
            raise
        api = publish(config, today=today)
        changed = before != archive.load()
        log.info('Menu published changed=%s date=%s weeks=%d', changed, api['publishedForDate'], len(api['weeks']))
        return {'changed': changed, 'publishedForDate': api['publishedForDate'], 'weeks': len(api['weeks'])}


def import_cache(config, source, *, ocr=None, stop=None, today=None):
    archive = Archive(config)
    with archive.lock():
        # Imported metadata remains private until every PDF has valid OCR and
        # an entire static generation has been built successfully.
        with tempfile.TemporaryDirectory(prefix='.import-', dir=config.data_dir.parent) as temporary:
            root = Path(temporary)
            staged_config = replace(config, data_dir=root / 'data', public_dir=root / 'public')
            shutil.copytree(config.data_dir, staged_config.data_dir,
                            ignore=shutil.ignore_patterns('.update.lock', 'cells'))
            staged = Archive(staged_config)
            count = staged.import_cache(source)
            staged.transcribe_pending(ocr=ocr, stop=stop)
            publish(staged_config, today=today)
            state = staged.load()
            for entry in state['menus']:
                archive.install_snapshot(entry['sha256'], staged.snapshot(entry['sha256']))
            atomic_json(archive.path, state)
        api = publish(config, today=today)
    return {'imported': count, 'publishedForDate': api['publishedForDate'], 'weeks': len(api['weeks'])}
