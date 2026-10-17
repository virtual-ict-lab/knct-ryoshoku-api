# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

"""PDF download worker. The parent enforces a deadline over the entire request."""
import argparse
import sys
from urllib.request import Request, urlopen

MAX_PDF_BYTES = 15 * 1024 * 1024


def download(url, timeout):
    request = Request(url, headers={'User-Agent': 'KNCT-RyoshokuData/1.0'})
    with urlopen(request, timeout=timeout) as response:
        if int(response.headers.get('Content-Length', 0)) > MAX_PDF_BYTES:
            raise ValueError('PDF is too large')
        chunks, size = [], 0
        while chunk := response.read(64 * 1024):
            size += len(chunk)
            if size > MAX_PDF_BYTES:
                raise ValueError('PDF is too large')
            chunks.append(chunk)
    data = b''.join(chunks)
    if not data.startswith(b'%PDF-'):
        raise ValueError('Response is not a PDF')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--timeout', type=float, required=True)
    args = parser.parse_args()
    sys.stdout.buffer.write(download(args.url, args.timeout))
