# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Preview generated public files without fetching, OCR, or publication."""
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

log = logging.getLogger('api.http')


def create_server(config, *, host=None, port=None):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, head=False):
            name = unquote(urlsplit(self.path).path)
            parts = PurePosixPath(name).parts
            if '..' in parts or any(p.startswith('.') for p in parts if p != '/'):
                self.send_error(404)
                return
            relative = name.lstrip('/') or 'index.html'
            allowed = relative in ('index.html', 'page.mjs', 'menu.mjs', 'kondate.pdf', 'kondate.png', 'kondate.json', 'state.json', 'latest.pdf') or relative.startswith('archive/') and PurePosixPath(relative).suffix in ('.pdf', '.json')
            if not allowed:
                self.send_error(404)
                return
            try:
                while True:
                    root = config.public_dir.resolve()
                    path = root / relative
                    if not path.resolve().is_relative_to(root):
                        self.send_error(404)
                        return
                    try:
                        payload = path.read_bytes()
                    except FileNotFoundError:
                        # Cleanup may remove a resolved generation before the file opens.
                        if config.public_dir.resolve() != root:
                            continue
                        raise
                    break
            except FileNotFoundError:
                self.send_error(404)
                return
            except OSError:
                self.send_error(503)
                return
            self.send_response(200)
            content_type = mimetypes.guess_type(relative)[0] or 'application/octet-stream'
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            if not head:
                self.wfile.write(payload)

        def do_GET(self):
            self.respond()

        def do_HEAD(self):
            self.respond(head=True)

        def log_message(self, fmt, *args):
            log.info(fmt, *args)

    return ThreadingHTTPServer((config.host if host is None else host, config.port if port is None else port), Handler)


def serve(config):
    with create_server(config) as server:
        log.info('Serving static files at http://%s:%d/', config.host, server.server_port)
        server.serve_forever()
