# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from support import running, config

def test_download_deadline_covers_trickling_body(tmp_path):
    import time
    from ryoshoku_ocr.service import download_pdf
    import subprocess
    class Trickle(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers()
            try:
                for byte in b'%PDF-' + b'x' * 100:
                    self.wfile.write(bytes([byte])); self.wfile.flush(); time.sleep(.02)
            except (BrokenPipeError, ConnectionResetError): pass
        def log_message(self, *args): pass
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Trickle)) as url:
        start = time.monotonic()
        with pytest.raises((TimeoutError, subprocess.TimeoutExpired)):
            download_pdf(config(tmp_path, pdf_url=url, fetch_timeout_seconds=.15))
        assert time.monotonic() - start < .45
