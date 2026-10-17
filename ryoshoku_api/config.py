# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Configuration for the standalone menu API."""
from dataclasses import dataclass, fields
from pathlib import Path
import os
from ryoshoku_ocr.config import Config as OcrConfig, PROJECT_ROOT, read_settings


@dataclass(frozen=True)
class Config(OcrConfig):
    public_dir: Path = PROJECT_ROOT / 'public'

    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.public_dir, (str, Path)):
            raise ValueError('public_dir must be a path string')
        output = Path(os.path.abspath(PROJECT_ROOT / Path(self.public_dir).expanduser()))
        object.__setattr__(self, 'public_dir', output)
        for protected in (self.data_dir, self.model_dir, PROJECT_ROOT):
            if output == protected or protected.is_relative_to(output):
                raise ValueError('public_dir must not contain data, models or project source')
        if output.is_relative_to(self.data_dir) or output.is_relative_to(self.model_dir):
            raise ValueError('public_dir must be separate from data and models')


def load_config(path=None):
    settings = read_settings(path)
    unknown = set(settings) - {field.name for field in fields(Config)}
    if unknown:
        raise ValueError('Unknown config.toml settings: ' + ', '.join(sorted(unknown)))
    return Config(**settings)
