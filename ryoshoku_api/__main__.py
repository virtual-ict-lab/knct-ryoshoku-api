# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Generate, import and serve static dormitory-menu PDF, PNG and JSON data."""
import argparse
from dataclasses import replace
import hashlib
import json
import logging
import signal
from pathlib import Path
import sys
import tempfile
from .logging import JstFormatter
from ryoshoku_ocr.config import PROJECT_ROOT
from ryoshoku_ocr.menu import build_menu, utc_now
from ryoshoku_ocr.service import run_ocr
from ryoshoku_ocr.store import atomic_json
from .archive import Archive
from .config import load_config
from .publish import publish
from .service import update, import_cache

log = logging.getLogger('api.cli')


def main():
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JstFormatter('%(asctime)s %(levelname)-5s [%(name)s] %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, help='Use a TOML file instead of the project config.toml')
    commands = parser.add_subparsers(dest='command', required=True)
    server = commands.add_parser('serve', help='Preview generated public files without fetching or OCR')
    server.add_argument('--host'); server.add_argument('--port',type=int)
    commands.add_parser('update', help='Fetch, transcribe changed PDFs and rebuild publication')
    ocr = commands.add_parser('ocr', help='OCR a local PDF into structured menu JSON without publishing')
    ocr.add_argument('pdf', type=Path)
    ocr.add_argument('--output', type=Path, help='Save JSON to this file; otherwise write JSON to stdout')
    publication = commands.add_parser('publish', help='Rebuild static public files without network or OCR')
    publication.add_argument('--date', help='Override the JST publication date (YYYY-MM-DD)')
    importer = commands.add_parser('import-cache', help='Import legacy cache history and transcribe it')
    importer.add_argument('directory',type=Path)
    commands.add_parser('prepare', help='Download and verify configured OCR models')
    commands.add_parser('clean', help='Remove Python caches; preserve data, models and generated site')
    args = parser.parse_args()
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    previous_sigterm = signal.signal(signal.SIGTERM, interrupted)
    try:
        config = load_config(args.config)
        if args.command == 'serve':
            from .server import serve
            options = {key:getattr(args,key) for key in ('host','port') if getattr(args,key) is not None}
            serve(replace(config,**options))
        elif args.command == 'update':
            print(json.dumps(update(config),ensure_ascii=False))
        elif args.command == 'ocr':
            data = args.pdf.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            with tempfile.TemporaryDirectory(prefix='ryoshoku-ocr-') as temporary:
                source = Path(temporary) / 'source.pdf'
                source.write_bytes(data)
                raw = run_ocr(source, config)
            menu = build_menu(raw, digest, utc_now())
            if args.output is None:
                print(json.dumps(menu, ensure_ascii=False, allow_nan=False))
            else:
                atomic_json(args.output, menu)
                log.info('Menu JSON saved: %s', args.output)
        elif args.command == 'publish':
            with Archive(config).lock():
                api = publish(config,today=args.date)
            print(json.dumps({'publishedForDate':api['publishedForDate'],'weeks':len(api['weeks']),'current':api['current']},ensure_ascii=False))
        elif args.command == 'import-cache':
            print(json.dumps(import_cache(config,args.directory),ensure_ascii=False))
        elif args.command == 'prepare':
            from ryoshoku_ocr.prepare import prepare_models
            log.info('OCR models ready: %s',prepare_models(config.model_size,config.model_dir,threads=config.ocr_threads))
        elif args.command == 'clean':
            from ryoshoku_ocr.clean import clean
            log.info('Cache cleanup complete removed=%d',clean(PROJECT_ROOT,config))
        return 0
    except KeyboardInterrupt:
        log.info('Command interrupted')
        return 130
    except Exception:
        log.exception('Command failed')
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


if __name__=='__main__':
    sys.exit(main())
