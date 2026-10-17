# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from ryoshoku_ocr.config import PROJECT_ROOT
from support import write_config


@pytest.mark.parametrize('save_file', [False, True])
def test_manual_ocr_returns_structured_confidence_json_without_publication(tmp_path, save_file):
    source = tmp_path / 'menu.pdf'
    source.write_bytes(b'%PDF-fixture')
    output = tmp_path / 'result.json'
    settings = write_config(tmp_path / 'config.toml', data_dir=tmp_path / 'data',
                            public_dir=tmp_path / 'public', model_dir=tmp_path / 'models',
                            model_size='small', ocr_threads=3)
    fixture = Path(__file__).parent / 'fixtures/contract.json'
    # Replace only costly inference. CLI parsing, TOML loading, normalization,
    # confidence details and JSON serialization run through production code.
    code = '''
import json, sys
from pathlib import Path
from unittest.mock import patch
raw = json.loads(Path(sys.argv[3]).read_text())[0]['raw']
def infer(pdf, config, *args, **kwargs):
    assert pdf.read_bytes() == b'%PDF-fixture'
    assert config.model_size == 'small'
    assert config.ocr_threads == 3
    return raw
argv = ['ryoshoku_api', '--config', sys.argv[1], 'ocr', sys.argv[2]] + sys.argv[4:]
with patch('ryoshoku_ocr.service.run_ocr', infer):
    from ryoshoku_api.__main__ import main
    sys.argv = argv
    sys.exit(main())
'''
    command = [sys.executable, '-c', code, str(settings), str(source), str(fixture)]
    if save_file:
        command += ['--output', str(output)]
    result = subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    if save_file:
        assert result.stdout == ''
        menu = json.loads(output.read_text())
    else:
        assert not output.exists()
        menu = json.loads(result.stdout)
    assert (menu['startDate'], menu['endDate']) == ('2026-09-30', '2026-10-04')
    assert menu['sourceSha256'] == hashlib.sha256(b'%PDF-fixture').hexdigest()
    assert menu['fetchedAt'].endswith('Z')
    assert menu['days'][0]['lunch']['lines'][0]['confidence'] == .72
    assert [issue['code'] for issue in menu['days'][0]['lunch']['issues']] == ['needs_review', 'low_confidence']
    assert not (tmp_path / 'data').exists()
    assert not (tmp_path / 'public').exists()
