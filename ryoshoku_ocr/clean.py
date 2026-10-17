# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Remove project caches without touching producer data or models."""
import shutil
from pathlib import Path


def clean(root, config):
    protected_names = {'.git', '.venv', '.models', 'data', 'public'}
    protected_paths = (config.data_dir.resolve(), config.model_dir.resolve())
    if hasattr(config, "public_dir"):
        protected_paths += (config.public_dir.resolve(),)
    removed = 0

    def visit(directory):
        nonlocal removed
        for path in directory.iterdir():
            if path.is_symlink() or path.name in protected_names:
                continue
            resolved = path.resolve()
            if any(resolved == p or resolved.is_relative_to(p) or p.is_relative_to(resolved) for p in protected_paths):
                continue
            if path.is_dir() and path.name in ('__pycache__', '.pytest_cache'):
                shutil.rmtree(path)
                removed += 1
            elif path.is_dir():
                visit(path)

    visit(Path(root))
    return removed
