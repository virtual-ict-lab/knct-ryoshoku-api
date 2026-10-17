# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Check license headers on handwritten source and configuration files."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ('ryoshoku_api', 'ryoshoku_ocr', 'scripts', 'tests', 'site', '.github')
COMMENT_PREFIXES = {
    '.py': '#', '.mjs': '//', '.js': '//', '.html': '<!--',
    '.toml': '#', '.yml': '#', '.yaml': '#',
}


def test_handwritten_source_and_config_files_have_spdx_headers():
    # Keep generated lockfiles, JSON data and third-party PDFs outside this scope.
    paths = list(ROOT.iterdir())
    for directory in SOURCE_DIRS:
        paths.extend((ROOT / directory).rglob('*'))
    missing = []
    for path in sorted(paths):
        if not path.is_file() or (path.suffix not in COMMENT_PREFIXES and path.name != '.gitignore'):
            continue
        prefix = COMMENT_PREFIXES.get(path.suffix, '#')
        header = path.read_text(encoding='utf-8').splitlines()[:8]
        expected = (
            f'{prefix} SPDX-FileCopyrightText: 2026 mothue',
            f'{prefix} SPDX-License-Identifier: AGPL-3.0-only',
        )
        if not all(any(line.strip().startswith(value) for line in header) for value in expected):
            missing.append(str(path.relative_to(ROOT)))
    assert not missing, 'Missing SPDX headers: ' + ', '.join(missing)
