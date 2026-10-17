# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Exercise real PDF parsing using original, generated geometry, not school assets."""
import io
import pdfplumber
import pytest
from ryoshoku_ocr.layout import detect_layout


def sample_pdf(columns, *, unequal_widths=False, offset=0):
    """Small, self-contained vector PDF with menu rules and an ASCII date header."""
    page_height = 595
    left, label_end, right = 17 + offset, 24 + offset, 804
    weights = list(range(8, 8 + columns)) if unequal_widths else [1] * columns
    xs = [left, label_end]
    running = label_end
    for weight in weights:
        running += (right - label_end) * weight / sum(weights)
        xs.append(running)
    ys = [43, 50, 57, 180, 247, 303, 325, 426, 493, 560]
    commands = ['0 g']
    for x in xs:
        commands.append(f'{x:.3f} {page_height-ys[-1]} .24 {ys[-1]-ys[0]} re f')
    for y in ys:
        commands.append(f'{left} {page_height-y-.24} {right-left} .24 re f')
    commands.append('BT /F1 8 Tf 20 568 Td (Period:2026/10/12~2026/10/18) Tj ET')
    stream = '\n'.join(commands).encode('ascii')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
        f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    data = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f'{number} 0 obj\n'.encode() + body + b'\nendobj\n')
    xref = len(data)
    data.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for position in offsets[1:]:
        data.extend(f'{position:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return io.BytesIO(data)


@pytest.mark.parametrize('columns,unequal,offset', [(7,False,0),(5,False,0),(7,True,0),(5,True,8)])
def test_cells_follow_rules_in_five_and_seven_day_pdfs(columns, unequal, offset):
    with pdfplumber.open(sample_pdf(columns, unequal_widths=unequal, offset=offset)) as pdf:
        layout = detect_layout(pdf.pages[0])
        assert layout.columns == columns
        assert len(layout.cells) == columns * 3
        assert {c.meal for c in layout.cells} == {'breakfast','lunch','dinner'}
        for c in layout.cells:
            assert c.bbox[0] < c.bbox[2] and c.bbox[1] < c.bbox[3]
        assert '2026/10/12' in layout.header_text
        assert layout.cells[0].bbox[0] == pytest.approx(25.92 + offset)
        assert layout.cells[0].bbox[1] == pytest.approx(57.62)
        assert layout.cells[-1].bbox[2] == pytest.approx(803.62)


def test_rejects_page_without_menu_grid():
    class Empty:
        width=841; height=595; rects=[]; lines=[]
    with pytest.raises(ValueError,match='grid'):
        detect_layout(Empty())
