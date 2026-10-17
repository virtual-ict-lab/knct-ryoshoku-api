# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""PDF -> raw OCR JSON. Stdout is a machine-readable protocol; logs use stderr."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys
import traceback
import pdfplumber
from .layout import detect_layout
from .engine import OcrEngine


def transcribe_pdf(path, engine, dpi=240, debug_dir=None):
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 1:
            raise ValueError('Expected a single-page weekly menu PDF')
        page = pdf.pages[0]
        layout = detect_layout(page)
        header = layout.header_text
        if not header or '202' not in header:
            image = page.crop((0,0,page.width,layout.header_bottom)).to_image(resolution=dpi).original
            header = '\n'.join(line['text'] for line in engine.read(image))
        cells = []
        for cell in layout.cells:
            image = page.crop(cell.bbox).to_image(resolution=dpi).original.convert('RGB')
            lines = engine.read(image)
            cells.append(dict(column=cell.column, meal=cell.meal, bbox=cell.bbox, lines=lines))
            if debug_dir:
                target = Path(debug_dir); target.mkdir(parents=True, exist_ok=True)
                image.save(target / f'{cell.column}-{cell.meal}.png')
            print(f'Processed cell column={cell.column+1}/{layout.columns} meal={cell.meal} lines={len(lines)}', file=sys.stderr, flush=True)
        return dict(schemaVersion=1, engine=engine.name, headerText=header, columns=layout.columns, cells=cells)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--debug-dir', type=Path)
    parser.add_argument('--model-size', choices=['small','medium'], default='medium')
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    try:
        with redirect_stdout(sys.stderr):
            engine = OcrEngine(args.model_size, args.model_dir, threads=args.threads)
            result = transcribe_pdf(args.pdf, engine, debug_dir=args.debug_dir)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception as exc:
        print(f'OCR failed: {exc}', file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
