# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Durable revision history and official-version selection."""
from contextlib import contextmanager
import copy
import fcntl
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import uuid
from ryoshoku_ocr.menu import MEALS, build_menu, require, utc_now, valid_date, validate_menu
from ryoshoku_ocr.service import run_ocr
from ryoshoku_ocr.store import atomic_json
from .period import pdf_period


def select_menus(menus, today):
    valid_date(today)
    revisions = sorted(menus, key=lambda e: (not e['preferred'], -e['seq']))
    current = next((e for e in revisions if e['start_date'] <= today <= e['end_date']), None)
    future = sorted((e for e in revisions if e['start_date'] > today), key=lambda e: e['start_date'])
    return {'current': current, 'upcoming': next(iter(future), None)}


def archive_path(value):
    path = PurePosixPath(value)
    require(not path.is_absolute() and '..' not in path.parts and path.parts[0] == 'archive' and path.suffix == '.pdf', 'Invalid archive path')
    return path


class Archive:
    def __init__(self, config):
        self.config = config
        self.path = config.data_dir / 'state.json'

    @contextmanager
    def lock(self):
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        with (self.config.data_dir / '.update.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield

    def snapshot(self, digest):
        require(isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest), 'Invalid PDF hash')
        return self.config.data_dir / 'snapshots' / digest

    def load(self):
        try:
            state = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'schemaVersion': 1, 'source_url': self.config.pdf_url, 'latest_pdf_hash': None, 'menus': []}
        require(isinstance(state, dict) and state.get('schemaVersion') == 1 and isinstance(state.get('menus'), list), 'Invalid archive state')
        seen = set()
        for entry in state['menus']:
            require(isinstance(entry, dict) and type(entry.get('seq')) is int and entry['seq'] > 0, 'Invalid archive sequence')
            require(entry['seq'] not in seen, 'Duplicate archive sequence')
            seen.add(entry['seq'])
            start, end = valid_date(entry.get('start_date')), valid_date(entry.get('end_date'))
            require(0 <= (end-start).days <= 6 and type(entry.get('preferred')) is bool, 'Invalid archive period or preference')
            self.snapshot(entry.get('sha256'))
            archive_path(entry['path'])
        return state

    def menu(self, entry):
        directory = self.snapshot(entry['sha256'])
        source = (directory / 'source.pdf').read_bytes()
        require(hashlib.sha256(source).hexdigest() == entry['sha256'], 'Snapshot PDF hash mismatch')
        path = directory / 'menu.json'
        menu = validate_menu(json.loads(path.read_text(encoding='utf-8')))
        require(menu['sourceSha256'] == entry['sha256'] and (menu['startDate'], menu['endDate']) == (entry['start_date'], entry['end_date']), 'Snapshot menu does not match PDF period')
        if any('lines' not in day[meal] for day in menu['days'] for meal in MEALS):
            # Add machine-readable details without inference or changing the
            # original processing timestamp. Publish only fully validated data.
            raw = json.loads((directory / 'raw.json').read_text(encoding='utf-8'))
            menu = build_menu(raw, entry['sha256'], menu['fetchedAt'])
            require((menu['startDate'], menu['endDate']) == (entry['start_date'], entry['end_date']), 'Saved OCR does not match PDF period')
            atomic_json(path, menu)
        return menu

    def install_snapshot(self, digest, directory):
        directory = Path(directory)
        source = (directory / 'source.pdf').read_bytes()
        require(hashlib.sha256(source).hexdigest() == digest, 'Snapshot PDF hash mismatch')
        target = self.snapshot(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        referenced = any(e['sha256'] == digest for e in self.load()['menus'])
        if target.exists() and referenced:
            require((target / 'source.pdf').read_bytes() == source, 'Existing snapshot is corrupt')
            for name in ('raw.json', 'menu.json'):
                if (directory / name).exists() and not (target / name).exists():
                    atomic_json(target / name, json.loads((directory / name).read_text(encoding='utf-8')))
            return
        incoming = target.with_name('.' + digest + '-' + uuid.uuid4().hex)
        orphan = target.with_name('.' + digest + '-orphan-' + uuid.uuid4().hex)
        try:
            shutil.copytree(directory, incoming)
            if target.exists():
                target.rename(orphan)
            try:
                incoming.rename(target)
            except BaseException:
                if orphan.exists():
                    orphan.rename(target)
                raise
        finally:
            if incoming.exists():
                shutil.rmtree(incoming)
            if orphan.exists() and target.exists():
                shutil.rmtree(orphan)

    def _save_source(self, digest, data):
        directory = self.snapshot(digest)
        if (directory / 'source.pdf').exists() and (directory / 'source.pdf').read_bytes() == data:
            return
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.ocr-', dir=self.config.data_dir) as temporary:
            staging = Path(temporary)
            (staging / 'source.pdf').write_bytes(data)
            self.install_snapshot(digest, staging)

    def ingest(self, data, *, raw=None, ocr=None, stop=None):
        require(data.startswith(b'%PDF-'), 'Response is not a PDF')
        digest = hashlib.sha256(data).hexdigest()
        state = self.load()
        previous = copy.deepcopy(state)
        existing = next((e for e in state['menus'] if e['sha256'] == digest), None)
        if existing is None:
            self.config.data_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.ocr-', dir=self.config.data_dir) as temporary:
                directory = Path(temporary)
                source = directory / 'source.pdf'
                source.write_bytes(data)
                if raw is None:
                    raw = ocr(source, self.config, directory / 'cells') if ocr else run_ocr(source, self.config, directory / 'cells', stop=stop)
                menu = build_menu(raw, digest, utc_now())
                atomic_json(directory / 'raw.json', raw)
                atomic_json(directory / 'menu.json', menu)
                seq = max((e['seq'] for e in state['menus']), default=0) + 1
                existing = dict(seq=seq, start_date=menu['startDate'], end_date=menu['endDate'], path=f"archive/{menu['startDate'][:4]}/{seq:04d}_{menu['startDate']}_{menu['endDate']}.pdf", sha256=digest, preferred=True)
                self.install_snapshot(digest, directory)
            state['menus'].append(existing)
        else:
            self._save_source(digest, data)
        for entry in state['menus']:
            if (entry['start_date'], entry['end_date']) == (existing['start_date'], existing['end_date']):
                entry['preferred'] = entry['sha256'] == digest
        state['source_url'] = self.config.pdf_url
        state['latest_pdf_hash'] = digest
        if previous != state:
            state['updated_at'] = utc_now()
            atomic_json(self.path, state)
        return existing

    def transcribe_pending(self, *, ocr=None, stop=None):
        state = self.load()
        for entry in state['menus']:
            directory = self.snapshot(entry['sha256'])
            if (directory / 'menu.json').exists():
                self.menu(entry)
                continue
            source = directory / 'source.pdf'
            require(hashlib.sha256(source.read_bytes()).hexdigest() == entry['sha256'], 'Snapshot PDF hash mismatch')
            if (directory / 'raw.json').exists():
                raw = json.loads((directory / 'raw.json').read_text(encoding='utf-8'))
            else:
                raw = ocr(source, self.config, directory / 'cells') if ocr else run_ocr(source, self.config, directory / 'cells', stop=stop)
            menu = build_menu(raw, entry['sha256'], utc_now())
            require((menu['startDate'],menu['endDate']) == (entry['start_date'],entry['end_date']), 'OCR disagrees with printed period')
            atomic_json(directory / 'raw.json', raw)
            atomic_json(directory / 'menu.json', menu)

    def import_cache(self, source):
        source = Path(source).resolve()
        previous = json.loads((source / 'state.json').read_text(encoding='utf-8'))
        incoming = []
        for path in sorted((source / 'archive').glob('*/*.pdf')):
            require(path.resolve().is_relative_to(source), 'Archive escapes import directory')
            match = re.fullmatch(r'(\d{4,})_.*\.pdf', path.name)
            require(match is not None, 'Invalid legacy archive filename')
            data = path.read_bytes()
            start, end = pdf_period(data)
            incoming.append((dict(seq=int(match[1]), start_date=start, end_date=end, path=path.relative_to(source).as_posix(), sha256=hashlib.sha256(data).hexdigest(), preferred=False), data))
        require(bool(incoming), 'No archive PDFs found')
        state = self.load()
        existing_preferences = {(e['start_date'], e['end_date']): e['sha256'] for e in state['menus'] if e['preferred']}
        existing_latest = state.get('latest_pdf_hash')
        existing_updated = state.get('updated_at')
        for entry, data in incoming:
            duplicate = next((e for e in state['menus'] if e['sha256'] == entry['sha256']), None)
            if duplicate is not None:
                continue
            require(not any(e['seq'] == entry['seq'] or e['path'] == entry['path'] for e in state['menus']), 'Import conflicts with existing archive')
            state['menus'].append(entry)
            self._save_source(entry['sha256'], data)
        preferred = {(e.get('start_date'), e.get('end_date')): e.get('sha256') for e in previous.get('menus', []) if e.get('preferred')}
        preferred.update(existing_preferences)
        for entry in state['menus']:
            period = (entry['start_date'], entry['end_date'])
            candidates = [e for e in state['menus'] if (e['start_date'], e['end_date']) == period]
            selected = next((e for e in candidates if e['sha256'] == preferred.get(period)), max(candidates, key=lambda e:e['seq']))
            entry['preferred'] = entry['sha256'] == selected['sha256']
        latest = existing_latest or previous.get('latest_pdf_hash') or previous.get('latest_hash')
        require(any(e['sha256'] == latest for e in state['menus']), 'Latest legacy PDF is not archived')
        state.update(latest_pdf_hash=latest, updated_at=existing_updated or previous.get('updated_at', utc_now()))
        atomic_json(self.path, state)
        return len(incoming)
