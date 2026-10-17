# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""Read the actual printed period, including incorrectly named legacy files."""
from datetime import date
from io import BytesIO
import re
import unicodedata
import pdfplumber

TOKEN = r'(\d{4})\s*[年/-]\s*(\d{1,2})\s*[月/-]\s*(\d{1,2})(?!\d)(?:\s*日)?'
PERIOD = re.compile(TOKEN + r'\s*(?:\(\s*[月火水木金土日]\s*\)\s*)?[~〜～―–—-]+\s*' + TOKEN)


def pdf_period(data):
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            text = pdf.pages[0].extract_text() if pdf.pages else ''
    except Exception as error:
        raise ValueError('Could not read the menu PDF') from error
    matches = set(PERIOD.findall(unicodedata.normalize('NFKC', text or '')))
    if len(matches) != 1:
        raise ValueError('Could not uniquely read the menu date range from the PDF')
    parts = [int(value) for value in matches.pop()]
    start, end = date(*parts[:3]), date(*parts[3:])
    if not 0 <= (end-start).days <= 6:
        raise ValueError('Invalid menu date range')
    return start.isoformat(), end.isoformat()
