# knct-ryoshoku-api

It is totally crazy that the dorm cafeteria menu at KNCT is just a PDF! So we built a project to extract it into structured JSON using OCR.

## Features

- KNCT updates the PDF for the next week over the weekend, but we keep the current PDF until Monday!
- Want to view it as a PNG instead of a PDF? No problem, enjoy a 300 DPI dorm menu image at `kondate.png`.
- Need structured JSON? You got it! It is powered by GitHub Actions, so feel free to use it however you like with zero restrictions. Just send a `GET` request to `kondate.json`. We even included accuracy info for you. Enjoy!

## Requirements

- Python 3.11 ~ 3.13 or later
- uv 0.12 or later

## Running Locally

```sh
uv sync --frozen --dev

# publish creates a `public` directory for publishing and bundles the PDF, images, and JSON
uv run python -m ryoshoku_api publish

# serve simply serves the `public` directory as-is
uv run python -m ryoshoku_api serve
```

For advanced users, the following commands are also available:

```sh
# To run OCR on a PDF manually, do the following. The model will be downloaded automatically
uv run python -m ryoshoku_api ocr input.pdf --output menu.json

# From fetching the official PDF to running necessary OCR and generating public output
uv run python -m ryoshoku_api update

# Import old cache (migration only)
uv run python -m ryoshoku_api import-cache ../knct-ryoshoku-cache

# Clean Python cache
uv run python -m ryoshoku_api clean

# Pre-install the OCR model with this command
uv run python -m ryoshoku_api prepare
```

## JSON Scheme

See [schema.json](schema.json).

## Testing and Development

```sh
uv run pytest -q
node --test tests/*.test.mjs
uv run python scripts/benchmark.py
uv run python -m ryoshoku_api clean
```

## Licences

The source code is licensed under AGPL-3.0-only ([LICENSE](LICENSE)). Rights to the original PDF belong to their respective owners.