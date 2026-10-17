# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Atomic JSON publication and a bounded history of weekly menus."""
import json
import os
import tempfile
from pathlib import Path
from .menu import validate_cache, validate_menu


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False, allow_nan=False, indent=2)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class MenuStore:
    def __init__(self, directory):
        self.path = Path(directory) / 'menus.json'

    def load(self):
        try:
            return validate_cache(json.loads(self.path.read_text(encoding='utf-8')))
        except FileNotFoundError:
            return {'schemaVersion': 1, 'weeks': []}

    def save(self, menu):
        validate_menu(menu)
        weeks = [week for week in self.load()['weeks'] if (week['startDate'], week['endDate']) != (menu['startDate'], menu['endDate'])]
        weeks.append(menu)
        weeks.sort(key=lambda week: week['fetchedAt'], reverse=True)
        atomic_json(self.path, {'schemaVersion': 1, 'weeks': weeks[:32]})
