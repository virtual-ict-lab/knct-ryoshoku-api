# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

from contextlib import contextmanager
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from ryoshoku_api.config import Config


def write_config(path, **settings):
    path.write_text(''.join(f'{key} = {json.dumps(str(value) if isinstance(value, Path) else value)}\n'
                            for key, value in settings.items()))
    return path


def pdf_bytes(label=b'fixture', *, rgb=(1, 0, 0)):
    """A valid 1 x 0.5 inch PDF with a solid color and a distinct revision label."""
    drawing = ('%s %s %s rg 0 0 72 36 re f\n' % rgb).encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 36] /Resources << >> /Contents 4 0 R >>',
               b'<< /Length ' + str(len(drawing)).encode() + b' >>\nstream\n' + drawing + b'endstream']
    data = b'%PDF-1.7\n%' + label + b'\n'
    offsets = []
    for number, value in enumerate(objects, 1):
        offsets.append(len(data))
        data += f'{number} 0 obj\n'.encode() + value + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 5\n0000000000 65535 f \n'
    data += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    data += f'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return data


@contextmanager
def running(server):
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

@contextmanager
def pdf_source(payload=b'%PDF-1.7\nfixture', status=200):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status); self.end_headers(); self.wfile.write(payload)
        def log_message(self, *args): pass
    with running(ThreadingHTTPServer(('127.0.0.1', 0), Handler)) as url:
        yield url

def config(tmp_path, **kwargs):
    return Config(data_dir=tmp_path / 'data', model_dir=tmp_path / 'models', **kwargs)
