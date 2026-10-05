#!/usr/bin/env python3
"""Reset local data and recreate the seeded demonstration workspace."""
from __future__ import annotations

import shutil
from pathlib import Path

import server

for folder in (server.UPLOAD_DIR, server.RENDER_DIR, server.CONVERSION_DIR, server.TMP_DIR):
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)

server.PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
server.CONVERSION_TMP_DIR.mkdir(parents=True, exist_ok=True)
server.STORE_PATH.unlink(missing_ok=True)
server.init_store()
print(f"Données de démonstration recréées dans {Path(server.DATA_DIR).resolve()}")
