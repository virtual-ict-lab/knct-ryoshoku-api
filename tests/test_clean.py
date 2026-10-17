# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path
import pytest
from ryoshoku_ocr.clean import clean
from ryoshoku_ocr.config import Config


def test_clean_preserves_configured_data_models_dependencies_and_symlink_targets(tmp_path):
    outside = tmp_path / 'external'; outside.mkdir()
    root = tmp_path / 'project'; root.mkdir()
    removable = ['ryoshoku_ocr/__pycache__/module.pyc', '.pytest_cache/state']
    retained = ['.venv/__pycache__/keep', 'custom-models/__pycache__/keep', 'custom-data/.pytest_cache/keep', 'config.toml', '.models/legacy.onnx', 'data/menus.json']
    for name in removable + retained:
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('keep')
    (outside / '__pycache__').mkdir(); (outside / '__pycache__/keep').write_text('keep')
    (root / 'external').symlink_to(outside)
    cfg = Config(data_dir=root / 'custom-data', model_dir=root / 'custom-models')
    assert clean(root, cfg) == 2
    assert all(not (root / name).exists() for name in removable)
    assert all((root / name).read_text() == 'keep' for name in retained)
    assert (outside / '__pycache__/keep').read_text() == 'keep'
    assert clean(root, cfg) == 0
