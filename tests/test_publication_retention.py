# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import replace
from pathlib import Path
import threading
from urllib.request import urlopen

import pytest

from ryoshoku_api.archive import Archive
from ryoshoku_api.publish import publish
from ryoshoku_api.server import create_server
from support import pdf_bytes, running
from test_archive import cfg, ingest


@pytest.mark.parametrize('symlink_parent', [False, True])
def test_repeated_publication_retains_only_current_and_previous_owned_generations(tmp_path, symlink_parent):
    config = cfg(tmp_path)
    if symlink_parent:
        parent = tmp_path / 'elsewhere' / 'nested'
        parent.mkdir(parents=True)
        alias = tmp_path / 'alias'
        alias.symlink_to(parent, target_is_directory=True)
        config = replace(config, public_dir=alias / 'public')
    ingest(Archive(config), pdf_bytes())
    publish(config, today='2026-10-17')
    generations = config.public_dir.resolve().parent
    foreign = generations / ('f' * 32)
    foreign.mkdir()
    (foreign / 'keep.txt').write_text('unowned')
    building = generations / '.building-active'
    building.mkdir()
    (building / '.ryoshoku-api').touch()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / '.ryoshoku-api').touch()
    link = generations / ('e' * 32)
    link.symlink_to(outside, target_is_directory=True)
    published = [config.public_dir.resolve()]
    for _ in range(6):
        publish(config, today='2026-10-17')
        published.append(config.public_dir.resolve())
    assert {path for path in published if path.exists()} == set(published[-2:])
    assert (config.public_dir / 'kondate.pdf').read_bytes() == pdf_bytes()
    assert (foreign / 'keep.txt').read_text() == 'unowned'
    assert building.is_dir()
    assert link.is_symlink() and outside.is_dir()


@pytest.mark.parametrize('pause_after_open', [False, True])
def test_http_read_survives_removal_of_its_superseded_generation(tmp_path, monkeypatch, pause_after_open):
    config = cfg(tmp_path)
    archive = Archive(config)
    original_pdf = pdf_bytes(b'original')
    ingest(archive, original_pdf)
    publish(config, today='2026-10-17')
    old = config.public_dir.resolve()
    entered, release = threading.Event(), threading.Event()
    payloads, failures = [], []
    original_open, original_read = Path.open, Path.read_bytes

    def pause(path):
        if path == old / 'kondate.pdf':
            entered.set()
            assert release.wait(5), 'Publication did not release the reader'

    def delayed_open(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        try:
            pause(path)
        except BaseException:
            stream.close()
            raise
        return stream

    def delayed_read(path):
        pause(path)
        return original_read(path)

    monkeypatch.setattr(Path, 'open' if pause_after_open else 'read_bytes',
                        delayed_open if pause_after_open else delayed_read)
    with running(create_server(config, port=0)) as base:
        def request():
            try:
                with urlopen(base + '/kondate.pdf', timeout=5) as response:
                    payloads.append(response.read())
            except Exception as exc:
                failures.append(exc)

        reader = threading.Thread(target=request)
        reader.start()
        try:
            assert entered.wait(3)
            for number in range(3):
                latest_pdf = pdf_bytes(f'revision-{number}'.encode())
                ingest(archive, latest_pdf)
                publish(config, today='2026-10-17')
            assert not old.exists()
        finally:
            release.set()
            reader.join(5)
        assert not reader.is_alive()
    assert not failures
    assert payloads == [original_pdf if pause_after_open else latest_pdf]
