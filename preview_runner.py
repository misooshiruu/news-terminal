"""Minimal server runner for preview sandbox - uses system python + inline deps."""
import sys
import os

# Add the project's venv site-packages to path
venv_sp = os.path.join(os.path.dirname(__file__), "venv", "lib", "python3.9", "site-packages")
if os.path.exists(venv_sp):
    sys.path.insert(0, venv_sp)

# Also try /tmp copy
tmp_sp = "/tmp/mt-venv/lib/python3.9/site-packages"
if os.path.exists(tmp_sp):
    sys.path.insert(0, tmp_sp)

os.chdir(os.path.dirname(__file__) or ".")

import uvicorn
uvicorn.run("src.main:app", host="0.0.0.0", port=8000, log_level="info", loop="asyncio", http="h11")
