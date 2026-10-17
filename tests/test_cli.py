# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import json
import subprocess
import sys
from pathlib import Path
from ryoshoku_ocr.config import PROJECT_ROOT
import pytest

RAW = json.loads((Path(__file__).parent / 'fixtures/contract.json').read_text())[0]['raw']


def test_ocr_timeout_terminates_inference(tmp_path, monkeypatch):
    from ryoshoku_ocr.service import run_ocr
    from ryoshoku_ocr.config import Config
    # Replace only the external worker process with a sleeping executable.
    worker = tmp_path / 'sleeping-python'
    worker.write_text('#!/bin/sh\nexec sleep 30\n'); worker.chmod(0o700)
    monkeypatch.setattr('ryoshoku_ocr.service.sys.executable', str(worker))
    with pytest.raises(subprocess.TimeoutExpired):
        run_ocr(tmp_path / 'pdf', Config(data_dir=tmp_path, ocr_timeout_seconds=.05), tmp_path / 'cells')





def test_archive_verification_outputs_consumer_compatible_utc_timestamp(tmp_path):
    raw_dir = tmp_path / 'raw'; raw_dir.mkdir()
    pdf_dir = tmp_path / 'pdf'; pdf_dir.mkdir()
    (raw_dir / 'sample.raw.json').write_text(json.dumps(RAW))
    (pdf_dir / 'sample.pdf').write_bytes(b'%PDF-fixture')
    result = subprocess.run([sys.executable, 'scripts/verify_archive.py', str(raw_dir), str(pdf_dir)], cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    menu = json.loads((raw_dir / 'verified-cache/menus.json').read_text())['weeks'][0]
    assert menu['fetchedAt'].endswith('Z')
