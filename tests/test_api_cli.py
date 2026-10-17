# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen
import pytest
from support import pdf_bytes, write_config
from ryoshoku_ocr.config import PROJECT_ROOT
from test_archive import cfg, ingest
from ryoshoku_api.archive import Archive
from support import running


@pytest.mark.parametrize('termination', [signal.SIGTERM, signal.SIGINT])
def test_serve_only_reads_static_files_without_fetching_or_creating_data(tmp_path, termination):
    public = tmp_path / 'public'
    public.mkdir()
    payload = b'{"publishedForDate":"2020-01-01","weeks":[]}'
    (public / 'kondate.json').write_bytes(payload)
    requests = []

    class Source(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(503)
            self.end_headers()

        def log_message(self, *args):
            pass

    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Source)) as source:
        settings = write_config(tmp_path / 'config.toml', data_dir=tmp_path / 'data',
                                public_dir=public, model_dir=tmp_path / 'models',
                                pdf_url=source, host='127.0.0.1', port=port)
        process = subprocess.Popen([sys.executable, '-m', 'ryoshoku_api', '--config', str(settings), 'serve'],
                                   cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while True:
                assert process.poll() is None, 'static server exited before serving'
                try:
                    with urlopen(f'http://127.0.0.1:{port}/kondate.json', timeout=.2) as response:
                        assert response.read() == payload
                    break
                except (URLError, TimeoutError):
                    assert time.monotonic() < deadline, 'static server did not start'
                    time.sleep(.02)
            # Allow the old startup downloader to reach the controlled source.
            time.sleep(.2)
            assert requests == []
            assert not (tmp_path / 'data').exists()
            assert not (tmp_path / 'models').exists()
            assert (public / 'kondate.json').read_bytes() == payload
            process.send_signal(termination)
            process.wait(timeout=4)
            assert process.returncode == 130
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


def test_publish_cli_works_offline_and_exits_nonzero_on_missing_history(tmp_path):
    config=cfg(tmp_path)
    settings=write_config(tmp_path/'config.toml',data_dir=config.data_dir,public_dir=config.public_dir,pdf_url='http://127.0.0.1:1/unreachable')
    command=[sys.executable,'-m','ryoshoku_api','--config',str(settings),'publish','--date','2026-10-17']
    missing=subprocess.run(command,cwd=PROJECT_ROOT,capture_output=True,text=True)
    assert missing.returncode==1
    assert missing.stdout==''
    ingest(Archive(config),pdf_bytes(b'%PDF-current'))
    ready=subprocess.run(command,cwd=PROJECT_ROOT,capture_output=True,text=True)
    assert ready.returncode==0,ready.stderr
    assert json.loads(ready.stdout)['publishedForDate']=='2026-10-17'
    assert (config.public_dir/'kondate.pdf').read_bytes()==pdf_bytes(b'%PDF-current')


def test_sigterm_reaps_ocr_worker_for_one_shot_cli_update(tmp_path):
    import signal
    import time
    worker=tmp_path/'worker.py';pidfile=tmp_path/'pid'
    worker.write_text('import os,time\nfrom pathlib import Path\nPath('+repr(str(pidfile))+').write_text(str(os.getpid()))\ntime.sleep(30)\n')
    pdf=tmp_path/'source.pdf';pdf.write_bytes(b'%PDF-test')
    code='''
import sys,subprocess
from unittest.mock import patch
from ryoshoku_api.__main__ import main
original=subprocess.Popen
worker=sys.argv[1]
def popen(args,**kwargs):
    if 'ryoshoku_ocr.worker' in args:args=[sys.executable,worker]
    return original(args,**kwargs)
sys.argv=['ryoshoku_api','--config',sys.argv[2],'update']
with patch('subprocess.Popen',popen):sys.exit(main())
'''
    settings=write_config(tmp_path/'config.toml',data_dir=tmp_path/'data',public_dir=tmp_path/'public',pdf_url=pdf.as_uri())
    parent=subprocess.Popen([sys.executable,'-c',code,str(worker),str(settings)],cwd=PROJECT_ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    pid=None
    try:
        deadline=time.monotonic()+5
        while not pidfile.exists():
            assert parent.poll() is None
            assert time.monotonic()<deadline
            time.sleep(.01)
        pid=int(pidfile.read_text());parent.terminate();parent.wait(timeout=4)
        with pytest.raises(ProcessLookupError):os.kill(pid,0)
    finally:
        if parent.poll() is None:parent.kill();parent.wait()
        if pid is not None:
            try:os.kill(pid,signal.SIGKILL)
            except ProcessLookupError:pass
