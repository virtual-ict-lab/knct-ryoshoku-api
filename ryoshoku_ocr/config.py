# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Producer configuration. All relative paths belong to the Python project."""
import math
from dataclasses import dataclass
from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PDF_URL = 'https://www.kagawa-nct.ac.jp/dormitoryE/kondate.pdf'


@dataclass(frozen=True)
class Config:
    data_dir: Path = PROJECT_ROOT / 'data'
    model_dir: Path = PROJECT_ROOT / '.models'
    pdf_url: str = PDF_URL
    model_size: str = 'medium'
    fetch_timeout_seconds: float = 30
    ocr_timeout_seconds: float = 600
    ocr_threads: int = 2
    host: str = '127.0.0.1'
    port: int = 3333

    def __post_init__(self):
        for name in ('data_dir', 'model_dir'):
            if not isinstance(getattr(self, name), (str, Path)):
                raise ValueError(f'{name} must be a path string')
            path = Path(getattr(self, name)).expanduser()
            object.__setattr__(self, name, (PROJECT_ROOT / path).resolve())
        if self.model_size not in ('small', 'medium'):
            raise ValueError('model_size must be small or medium')
        for name in ('fetch_timeout_seconds', 'ocr_timeout_seconds'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be positive')
        if type(self.port) is not int or not 0 <= self.port <= 65535:
            raise ValueError('port must be an integer between 0 and 65535')
        if type(self.ocr_threads) is not int or self.ocr_threads <= 0:
            raise ValueError('ocr_threads must be a positive integer')
        for name in ('host', 'pdf_url'):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f'{name} must be a nonempty string')


def read_settings(path=None):
    source = Path(path) if path is not None else PROJECT_ROOT / 'config.toml'
    try:
        with source.open('rb') as stream:
            return tomllib.load(stream)
    except FileNotFoundError:
        if path is not None:
            raise
        return {}
