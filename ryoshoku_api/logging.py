# SPDX-FileCopyrightText: 2026 mothue
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from datetime import datetime, timedelta, timezone


class JstFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return datetime.fromtimestamp(record.created, timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
