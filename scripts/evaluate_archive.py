# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Run OCR on a locally supplied PDF directory; no school documents are bundled."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ryoshoku_ocr.engine import OcrEngine
from ryoshoku_ocr.worker import transcribe_pdf

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('pdf_dir', type=Path, help='Directory containing your local PDF inputs')
parser.add_argument('--output', type=Path, default=ROOT / 'data/evaluation')
args = parser.parse_args()
inputs = sorted(args.pdf_dir.glob('*.pdf'))
if not inputs:
    parser.error('No PDF files found in the supplied directory')
args.output.mkdir(parents=True, exist_ok=True)
engine = OcrEngine('medium', ROOT / '.models')
for path in inputs:
    start = time.monotonic()
    raw = transcribe_pdf(path, engine, debug_dir=args.output / path.stem)
    (args.output / (path.stem + '.raw.json')).write_text(json.dumps(raw, ensure_ascii=False, indent=2))
    print(path.name, 'columns', raw['columns'], 'seconds', round(time.monotonic()-start, 2), flush=True)
