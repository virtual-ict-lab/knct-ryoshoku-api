# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Find menu cells using PDF rules, never fixed pixels or equal-width columns."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Cell:
    column: int
    meal: str
    bbox: tuple[float, float, float, float]

@dataclass(frozen=True)
class Layout:
    columns: int
    header_text: str
    cells: list[Cell]
    header_bottom: float


def clustered(values, tolerance=1.0):
    groups = []
    for value in sorted(values):
        if groups and abs(value - groups[-1][-1]) <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(g) / len(g) for g in groups]


def detect_layout(page) -> Layout:
    vertical, horizontal = [], []
    for shape in page.rects + page.lines:
        width, height = shape['x1'] - shape['x0'], shape['bottom'] - shape['top']
        if width <= 1 and height > page.height * .33:
            vertical.append((shape['x0'] + shape['x1']) / 2)
        if height <= 1 and width > page.width * .6:
            horizontal.append((shape['top'] + shape['bottom']) / 2)
    xs, ys = clustered(vertical), clustered(horizontal)
    if len(xs) < 4 or len(ys) < 8:
        raise ValueError('Unsupported menu grid: insufficient rules (scanned PDFs need a layout adapter)')
    # The first narrow column contains meal labels, not a date.
    if xs[1] - xs[0] > (xs[-1] - xs[0]) * .05:
        raise ValueError('Unsupported menu grid: missing meal-label column')
    xs = xs[1:]
    columns = len(xs) - 1
    if not 1 <= columns <= 7 or any(b-a < page.width*.04 for a,b in zip(xs,xs[1:])):
        raise ValueError('Unsupported menu grid: invalid date columns')
    cells = []
    for column, (x0, x1) in enumerate(zip(xs, xs[1:])):
        for meal, index in [('breakfast', 2), ('lunch', 4), ('dinner', 6)]:
            if ys[index+1] - ys[index] < 10:
                raise ValueError('Unsupported menu grid: invalid meal row')
            cells.append(Cell(column, meal, (x0+1.8, ys[index]+.5, x1-.5, ys[index+1]-.5)))
    header = page.crop((0, 0, page.width, ys[0])).extract_text() or ''
    return Layout(columns, header, cells, ys[0])
