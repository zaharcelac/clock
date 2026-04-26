"""Default paths and filenames for generated PDFs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path("output")


def clock_pdf_basename(when: datetime | None = None) -> str:
    """e.g. clock_2026-04-25_14-30-00.pdf (local time)."""
    if when is None:
        when = datetime.now()
    return when.strftime("clock_%Y-%m-%d_%H-%M-%S.pdf")


def ensure_clock_pdf_path(
    output_dir: str | Path | None = None,
    when: datetime | None = None,
) -> Path:
    """
    Return path `output/clock_YYYY-MM-DD_HH-MM-SS.pdf` (under ``output`` by default),
    with parent directory created.
    """
    base = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    path = base / clock_pdf_basename(when=when)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
