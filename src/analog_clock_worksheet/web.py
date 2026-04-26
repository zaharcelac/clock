"""FastAPI app: form to build a clock worksheet and download the PDF."""

from __future__ import annotations

import random
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from string import Template

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from analog_clock_worksheet import __version__
from analog_clock_worksheet.public_url import worksheet_public_url
from analog_clock_worksheet.minutes_mode import MinutesMode, allowed_minutes
from analog_clock_worksheet.output_paths import clock_pdf_basename, ensure_clock_pdf_path
from analog_clock_worksheet.pdf_gen import (
    MAX_CLOCKS_PER_PAGE,
    MAX_PDF_PAGES,
    build_clock_worksheet_pdf,
)

app = FastAPI(
    title="Analog clock worksheet",
    version=__version__,
    description="Generate US Letter PDFs with random analog clock times.",
)

_INDEX_HTML = Path(__file__).resolve().parent / "templates" / "index.html"


@lru_cache(maxsize=1)
def _index_template() -> Template:
    # string.Template: $version, $max_pages (avoids str.format vs CSS `{` clashes).
    return Template(_INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _index_template().substitute(
        version=__version__,
        max_pages=MAX_PDF_PAGES,
    )


def _form_on(v: str) -> bool:
    return str(v).strip() not in ("0", "false", "False", "off", "no", "")


@app.post("/worksheet")
def worksheet(
    request: Request,
    max_problems: int = Form(6, ge=1, le=MAX_CLOCKS_PER_PAGE),
    pages: int = Form(1, ge=1, le=MAX_PDF_PAGES),
    minutes: str = Form("fives"),
    show_minutes_numbers: str = Form("1"),
    show_minutes_ticks: str = Form("1"),
    answer_24h_rows: str = Form("1"),
    seed: str | None = Form(None),
) -> StreamingResponse:
    mode = MinutesMode.from_str(minutes)
    minute_values = list(allowed_minutes(mode))
    rng: random.Random | None = None
    if seed is not None and str(seed).strip() != "":
        try:
            rng = random.Random(int(str(seed).strip()))
        except ValueError:
            rng = random.Random()
    try:
        data = build_clock_worksheet_pdf(
            max_problems,
            minute_values,
            rng=rng,
            show_minutes_numbers=_form_on(show_minutes_numbers),
            show_minutes_ticks=_form_on(show_minutes_ticks),
            minutes_mode=minutes,
            pages=pages,
            footer_app_url=worksheet_public_url(request),
            answer_24h_rows=_form_on(answer_24h_rows),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    when = datetime.now()
    name = clock_pdf_basename(when=when)
    out_path = ensure_clock_pdf_path(when=when)
    out_path.write_bytes(data)
    buf = BytesIO(data)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
        },
    )
