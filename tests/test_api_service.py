# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import json
import subprocess
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen
from urllib.error import HTTPError
import pytest
from support import pdf_bytes
from ryoshoku_api.archive import Archive
from ryoshoku_api.service import update, import_cache
from ryoshoku_api.publish import publish
from ryoshoku_api.server import create_server
from test_archive import cfg, ingest, raw_for, FIX
from support import running, pdf_source


def test_unchanged_pdf_republishes_for_new_day_without_ocr(tmp_path):
    config=cfg(tmp_path); archive=Archive(config)
    with pdf_source(pdf_bytes(b'%PDF-next')) as url:
        from dataclasses import replace
        config=replace(config,pdf_url=url)
        result=update(config,ocr=lambda *_:raw_for('2026/10/19','2026/10/25'),today='2026-10-18')
        assert result['changed']
        assert not (config.public_dir/'kondate.pdf').exists()
        def unexpected(*_): pytest.fail('unchanged PDF must not run OCR')
        assert not update(config,ocr=unexpected,today='2026-10-19')['changed']
        assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-next')


def test_publication_still_switches_from_cache_when_remote_is_down(tmp_path):
    from dataclasses import replace
    config=cfg(tmp_path); archive=Archive(config)
    ingest(archive,pdf_bytes(b'%PDF-current'));ingest(archive,pdf_bytes(b'%PDF-next'),'2026/10/19','2026/10/25')
    publish(config,today='2026-10-18')
    with pdf_source(status=503) as url:
        with pytest.raises(RuntimeError):update(replace(config,pdf_url=url),today='2026-10-19')
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-next')


def test_http_only_serves_generated_public_files_and_does_not_run_ocr(tmp_path):
    config=cfg(tmp_path);archive=Archive(config)
    with running(create_server(config,port=0)) as url:
        with pytest.raises(HTTPError) as exc:urlopen(url+'/kondate.json')
        assert exc.value.code==404
        entry=ingest(archive,pdf_bytes(b'%PDF-current'));publish(config,today='2026-10-17')
        with urlopen(url+'/kondate.pdf') as response:
            assert response.headers.get_content_type()=='application/pdf'
            assert response.read()==pdf_bytes(b'%PDF-current')
        with urlopen(url+'/kondate.json') as response:
            assert response.headers.get_content_type()=='application/json'
            assert json.load(response)['current']['sourceSha256']==entry['sha256']
        for path in ['/data/state.json','/../data/state.json','/%2e%2e/data/state.json','/.ryoshoku-api','/archive/../../data/state.json']:
            with pytest.raises(HTTPError) as exc:urlopen(url+path)
            assert exc.value.code==404
        assert len(archive.load()['menus'])==1


def test_local_http_serves_old_publication_during_ocr(tmp_path):
    from dataclasses import replace
    config=cfg(tmp_path);archive=Archive(config)
    ingest(archive,pdf_bytes(b'%PDF-current'));publish(config,today='2026-10-17')
    entered,release=threading.Event(),threading.Event()
    failures=[]
    def ocr(*_):
        entered.set();assert release.wait(5)
        return raw_for('2026/10/19','2026/10/25')
    with pdf_source(pdf_bytes(b'%PDF-next')) as pdf_url, running(create_server(config,port=0)) as url:
        def work():
            try:update(replace(config,pdf_url=pdf_url),ocr=ocr,today='2026-10-17')
            except Exception as exc:failures.append(exc)
        thread=threading.Thread(target=work);thread.start()
        try:
            assert entered.wait(3)
            with pytest.raises(BlockingIOError):update(replace(config,pdf_url=pdf_url),ocr=ocr)
            with urlopen(url+'/kondate.pdf',timeout=1) as response:assert response.read()==pdf_bytes(b'%PDF-current')
        finally:release.set();thread.join(5)
    assert not failures


def test_failed_initial_import_leaves_destination_state_unmodified(tmp_path):
    import shutil
    source=tmp_path/'legacy';shutil.copytree(FIX/'legacy',source)
    next((source/'archive').glob('*/*.pdf')).write_bytes(b'%PDF-broken')
    config=cfg(tmp_path)
    with pytest.raises(ValueError):Archive(config).import_cache(source)
    assert not (config.data_dir/'state.json').exists()


def test_failed_ocr_during_import_cannot_poison_existing_history_or_publication(tmp_path):
    import hashlib
    import shutil
    source=tmp_path/'new-legacy';path=source/'archive/2026/0009_2026-10-19_2026-10-25.pdf'
    path.parent.mkdir(parents=True)
    pdf=next((FIX/'legacy/archive').glob('*/0008_*.pdf')).read_bytes()
    path.write_bytes(pdf)
    digest=hashlib.sha256(pdf).hexdigest()
    (source/'state.json').write_text(json.dumps({'latest_pdf_hash':digest,'menus':[{'seq':9,'start_date':'2026-10-19','end_date':'2026-10-25','path':path.relative_to(source).as_posix(),'sha256':digest,'preferred':True}]}))
    config=cfg(tmp_path);archive=Archive(config)
    ingest(archive,pdf_bytes(b'%PDF-current'));publish(config,today='2026-10-17')
    before=archive.path.read_bytes()
    def failure(*_):raise RuntimeError('Inference failed')
    with pytest.raises(RuntimeError):import_cache(config,source,ocr=failure,today='2026-10-17')
    assert archive.path.read_bytes()==before
    publish(config,today='2026-10-18')
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-current')
