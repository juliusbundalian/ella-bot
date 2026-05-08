"""Speech module for E.L.L.A."""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_SRC_PACKAGE_DIR = _PACKAGE_DIR.parent.parent / "src" / "ella_bot" / "speech"

if _SRC_PACKAGE_DIR.exists():
	__path__.append(str(_SRC_PACKAGE_DIR))
