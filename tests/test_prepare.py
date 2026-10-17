# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
import ryoshoku_ocr.prepare as module


def test_prepares_the_selected_engine_with_a_real_rgb_test_image(monkeypatch, tmp_path):
    class Engine:
        name = 'PP-OCRv6-small'

        def __init__(self, size, model_dir, *, threads):
            assert size == 'small'
            assert model_dir == tmp_path
            assert threads == 4

        def read(self, image):
            assert image.mode == 'RGB'
            assert image.getextrema()[0] == (0, 255)
            return [dict(text='RYOSHOKU', confidence=.99)]

    monkeypatch.setattr(module, 'OcrEngine', Engine)
    assert module.prepare_models('small', tmp_path, threads=4) == 'PP-OCRv6-small'


def test_empty_ocr_output_does_not_report_success(monkeypatch, tmp_path):
    class Engine:
        def __init__(self, size, model_dir, *, threads):
            pass

        def read(self, image):
            return []

    monkeypatch.setattr(module, 'OcrEngine', Engine)
    with pytest.raises(RuntimeError, match='recognize'):
        module.prepare_models('medium', tmp_path)
