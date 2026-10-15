# -*- coding: utf-8 -*-
"""小さな共通の関数（ハッシュ、git）。"""
from pathlib import Path
import hashlib


def _sha256(path):
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def _git(*a):
    import subprocess
    try:
        r = subprocess.run(["git", *a], capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else None
    except OSError:
        return None
