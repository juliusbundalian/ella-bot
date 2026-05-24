from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring root formatting once."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return logging.getLogger(name)
