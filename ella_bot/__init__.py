"""E.L.L.A. package."""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_SRC_PACKAGE_DIR = _PACKAGE_DIR.parent / "src" / "ella_bot"

if _SRC_PACKAGE_DIR.exists():
	__path__.append(str(_SRC_PACKAGE_DIR))
