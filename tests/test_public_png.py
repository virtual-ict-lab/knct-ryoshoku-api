# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

from io import BytesIO
from urllib.error import HTTPError
from urllib.request import urlopen

from PIL import Image
from pdfplumber.utils.exceptions import PdfminerException
import pytest

from ryoshoku_api.archive import Archive
from ryoshoku_api.publish import publish
from ryoshoku_api.server import create_server
from support import pdf_bytes, running
from test_archive import cfg, ingest


def test_png_is_full_page_300_dpi_and_switches_with_current_pdf(tmp_path):
    config = cfg(tmp_path)
    archive = Archive(config)
    current = pdf_bytes(b'current', rgb=(1, 0, 0))
    upcoming = pdf_bytes(b'next', rgb=(0, 0, 1))
    ingest(archive, current)
    ingest(archive, upcoming, '2026/10/19', '2026/10/25')
    publish(config, today='2026-10-18')
    old_generation = config.public_dir.resolve()
    with running(create_server(config, port=0)) as base:
        with urlopen(base + '/kondate.png') as response:
            assert response.headers.get_content_type() == 'image/png'
            with Image.open(BytesIO(response.read())) as image:
                assert image.format == 'PNG'
                assert image.size == (300, 150)
                assert image.info['dpi'] == pytest.approx((300, 300), abs=.01)
                assert image.convert('RGB').getpixel((150, 75)) == (255, 0, 0)
        assert (config.public_dir / 'kondate.pdf').read_bytes() == current
        publish(config, today='2026-10-19')
        with urlopen(base + '/kondate.png') as response:
            with Image.open(BytesIO(response.read())) as image:
                assert image.convert('RGB').getpixel((150, 75)) == (0, 0, 255)
        assert (config.public_dir / 'kondate.pdf').read_bytes() == upcoming
        with Image.open(old_generation / 'kondate.png') as image:
            assert image.convert('RGB').getpixel((150, 75)) == (255, 0, 0)


def test_png_and_pdf_are_both_absent_when_current_menu_is_missing(tmp_path):
    config = cfg(tmp_path)
    ingest(Archive(config), pdf_bytes())
    publish(config, today='2026-10-17')
    assert (config.public_dir / 'kondate.png').is_file()
    publish(config, today='2026-10-26')
    with running(create_server(config, port=0)) as base:
        for name in ('kondate.pdf', 'kondate.png'):
            assert not (config.public_dir / name).exists()
            with pytest.raises(HTTPError) as error:
                urlopen(base + '/' + name)
            assert error.value.code == 404


def test_pdf_render_failure_preserves_previous_pdf_png_and_json(tmp_path):
    config = cfg(tmp_path)
    archive = Archive(config)
    ingest(archive, pdf_bytes())
    publish(config, today='2026-10-17')
    before = {name: (config.public_dir / name).read_bytes()
              for name in ('kondate.pdf', 'kondate.png', 'kondate.json')}
    ingest(archive, b'%PDF-broken')
    with pytest.raises(PdfminerException):
        publish(config, today='2026-10-17')
    for name, payload in before.items():
        assert (config.public_dir / name).read_bytes() == payload
