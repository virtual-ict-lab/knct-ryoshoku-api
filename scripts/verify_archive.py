# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Rebuild a verified cache from saved raw OCR JSON and source PDFs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ryoshoku_ocr.menu import build_menu, utc_now
from ryoshoku_ocr.store import MenuStore

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('raw_directory', type=Path)
parser.add_argument('pdf_directory', type=Path)
args = parser.parse_args()
store = MenuStore(args.raw_directory / 'verified-cache')
for path in sorted(args.raw_directory.glob('*.raw.json')):
    pdf = args.pdf_directory / path.name.replace('.raw.json', '.pdf')
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    menu = build_menu(json.loads(path.read_text(encoding='utf-8')), digest, utc_now())
    store.save(menu)
    print(f"{path.name}: {menu['startDate']}..{menu['endDate']}, {len(menu['days'])} days, {len(menu['warnings'])} warnings")
