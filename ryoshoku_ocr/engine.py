# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""OCR only: return text, coordinates, and recognition confidence without parsing."""
from pathlib import Path
import numpy as np
from rapidocr import RapidOCR, ModelType

class OcrEngine:
    def __init__(self, size='medium', model_dir=None, *, threads=2):
        if size not in ('small', 'medium'):
            raise ValueError('OCR model size must be small or medium')
        model = ModelType.MEDIUM if size == 'medium' else ModelType.SMALL
        params = {
            'Global.use_cls': False,
            'Global.text_score': 0.0,
            'Global.log_level': 'warning',
            'Det.model_type': model, 'Rec.model_type': model,
            'EngineConfig.onnxruntime.intra_op_num_threads': threads,
            'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        }
        if model_dir:
            params['Global.model_root_dir'] = str(Path(model_dir).resolve())
        self.engine = RapidOCR(params=params)
        self.name = f'PP-OCRv6-{size}'

    def read(self, image):
        # Palette PNGs otherwise become palette indices in RapidOCR's loader.
        result = self.engine(image.convert('RGB'))
        if result.txts is None:
            return []
        return [dict(text=text, confidence=float(score), box=np.asarray(box).tolist())
                for text, score, box in zip(result.txts, result.scores, result.boxes)]
