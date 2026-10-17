# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

from PIL import Image
import pytest
import ryoshoku_ocr.engine as module


def test_ocr_keeps_low_confidence_candidates_and_converts_palette_to_rgb(monkeypatch):
    # Only the external inference is replaced. This pins our engine configuration
    # and input/output protocol, not RapidOCR's neural-network implementation.
    class Inference:
        def __init__(self, params):
            assert params['Global.text_score'] == 0.0
            assert params['EngineConfig.onnxruntime.intra_op_num_threads'] == 4
        def __call__(self, image):
            assert image.mode == 'RGB'
            class Result:
                txts=['青椒肉絲']; scores=[.3]; boxes=[[[0,0],[10,0],[10,5],[0,5]]]
            return Result()
    monkeypatch.setattr(module,'RapidOCR',Inference)
    result=module.OcrEngine(threads=4).read(Image.new('P',(20,20)))
    assert result[0]['text']=='青椒肉絲'
    assert result[0]['confidence']==.3
