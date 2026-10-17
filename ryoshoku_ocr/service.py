# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Bounded PDF download and OCR worker invocations."""
import json
import logging
import os
import subprocess
import sys
from .config import PROJECT_ROOT
from .menu import validate_raw
from .processes import run_process

log = logging.getLogger('menu.update')


def worker_environment():
    return {**os.environ, 'PYTHONPATH': str(PROJECT_ROOT)}


def download_pdf(config, stop=None):
    log.info('Downloading menu PDF')
    # Isolate the complete network operation (including DNS, headers and body)
    # so trickling responses cannot extend a socket timeout indefinitely.
    try:
        return run_process([
            sys.executable, '-m', 'ryoshoku_ocr.download', config.pdf_url,
            '--timeout', str(config.fetch_timeout_seconds),
        ], cwd=PROJECT_ROOT, env=worker_environment(),
            timeout=config.fetch_timeout_seconds, stop=stop)
    except subprocess.CalledProcessError as error:
        raise RuntimeError('PDF download failed') from error


def run_ocr(pdf, config, debug_dir=None, stop=None):
    log.info('Starting OCR model=%s', config.model_size)
    command = [
        sys.executable, '-m', 'ryoshoku_ocr.worker', str(pdf),
        '--model-size', config.model_size, '--model-dir', str(config.model_dir),
        '--threads', str(config.ocr_threads),
    ]
    if debug_dir is not None:
        command += ['--debug-dir', str(debug_dir)]
    output = run_process(command, cwd=PROJECT_ROOT, env=worker_environment(),
        timeout=config.ocr_timeout_seconds, stop=stop)
    return validate_raw(json.loads(output))

