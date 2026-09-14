#!/bin/bash
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

set -euo pipefail
# The snapshot arrives on stdin; the image's Windows venv remains in place.
tar --no-same-owner -xf - -C /root/.wine/drive_c/dea
exec msys2 -c 'cd /c/dea/l1 && exec make "$@"' dea-wine "$@"
