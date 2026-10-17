# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import pytest

from ryoshoku_api.config import load_config
from ryoshoku_ocr.config import PROJECT_ROOT


def test_toml_settings_are_typed_and_paths_use_project_root(tmp_path, monkeypatch):
    path = tmp_path / 'settings.toml'
    path.write_text('''
data_dir = "custom-data"
public_dir = "custom-public"
model_dir = "custom-models"
pdf_url = "https://example.org/menu.pdf"
model_size = "small"
ocr_threads = 4
fetch_timeout_seconds = 12.5
ocr_timeout_seconds = 90
host = "0.0.0.0"
port = 8080
''')
    monkeypatch.chdir(tmp_path)
    config = load_config(path)
    assert config.data_dir == PROJECT_ROOT / 'custom-data'
    assert config.public_dir == PROJECT_ROOT / 'custom-public'
    assert config.model_dir == PROJECT_ROOT / 'custom-models'
    assert config.pdf_url == 'https://example.org/menu.pdf'
    assert config.model_size == 'small'
    assert config.ocr_threads == 4
    assert config.fetch_timeout_seconds == 12.5
    assert config.ocr_timeout_seconds == 90
    assert (config.host, config.port) == ('0.0.0.0', 8080)


def test_omitted_settings_use_defaults_and_ignore_old_environment(tmp_path, monkeypatch):
    path = tmp_path / 'settings.toml'
    path.write_text('port = 4444\n')
    monkeypatch.setenv('HTTP_PORT', '9999')
    monkeypatch.setenv('DATA_DIR', '/old-env-data')
    config = load_config(path)
    assert config.port == 4444
    assert config.data_dir == PROJECT_ROOT / 'data'
    assert config.public_dir == PROJECT_ROOT / 'public'
    assert config.model_size == 'medium'
    assert config.ocr_threads == 2


def test_default_config_is_found_from_another_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config.port == 3333
    assert config.data_dir == PROJECT_ROOT / 'data'
    assert config.public_dir == PROJECT_ROOT / 'public'


def test_missing_default_config_uses_defaults_but_explicit_missing_path_fails(tmp_path, monkeypatch):
    monkeypatch.setattr('ryoshoku_ocr.config.PROJECT_ROOT', tmp_path)
    assert load_config().port == 3333
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / 'missing.toml')


@pytest.mark.parametrize('setting', [
    'port = "8080"', 'port = true', 'port = -1', 'port = 65536',
    'ocr_threads = 0', 'ocr_threads = true', 'ocr_threads = 2.5',
    'model_size = "bad"', 'fetch_timeout_seconds = nan',
    'ocr_timeout_seconds = -1', 'ocr_timeout_seconds = true',
    'data_dir = 123', 'public_dir = 123', 'public_dir = "."',
    'host = ""', 'pdf_url = ""', 'porrt = 8080',
])
def test_invalid_toml_configuration_fails_before_running_commands(tmp_path, setting):
    path = tmp_path / 'invalid.toml'
    path.write_text(setting)
    with pytest.raises(ValueError):
        load_config(path)
