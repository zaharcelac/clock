"""FastAPI app: form to build a clock worksheet and download the PDF."""

from __future__ import annotations

import random
from datetime import datetime
from io import BytesIO
from string import Template

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from analog_clock_worksheet import __version__
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

# string.Template: placeholders are $version / $max_clocks / $max_pages (not str.format, so
# CSS { ... } does not need escaping and cannot be mistaken for a " font-family" field name).
_PAGE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Clock worksheet</title>
  <style>
    :root { font-family: system-ui, sans-serif; }
    body { max-width: 32rem; margin: 2rem auto; padding: 0 1rem; }
    label { display: block; margin: 0.75rem 0 0.25rem; }
    input, select, button { font: inherit; }
    input[type=number] { width: 6rem; }
    select { min-width: 12rem; }
    button { margin-top: 1rem; padding: 0.4rem 0.8rem; }
    p.hint { color: #444; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>Analog clock worksheet</h1>
  <p>Build a US Letter PDF with analog clocks for time practice (one or more pages).</p>
  <form method="post" action="/worksheet">
    <label for="max_problems">Clocks on each page</label>
    <input id="max_problems" name="max_problems" type="number" min="1" max="$max_clocks" value="6" required />

    <label for="pages">Number of pages in the PDF</label>
    <input id="pages" name="pages" type="number" min="1" max="$max_pages" value="1" required />

    <label for="minutes">Minute hand options</label>
    <select id="minutes" name="minutes" required>
      <option value="exact">Exact — on the hour only (:00)</option>
      <option value="half">Half — :00 and :30</option>
      <option value="quarter">Quarter — 0, 15, 20, 45</option>
      <option value="fives" selected>Fives — any 5-minute step</option>
    </select>
    <p class="hint">Hour hand: on the hour when minutes are 0; otherwise between the two hour numbers (simplified).</p>

    <label for="show_minutes_numbers">Outer minute numbers (5, 10, 15, …)</label>
    <select id="show_minutes_numbers" name="show_minutes_numbers">
      <option value="1" selected>Show</option>
      <option value="0">Hide</option>
    </select>

    <label for="show_minutes_ticks">Small 1-minute tick marks</label>
    <select id="show_minutes_ticks" name="show_minutes_ticks">
      <option value="1" selected>Show</option>
      <option value="0">Hide</option>
    </select>

    <label for="seed">Random seed (optional)</label>
    <input id="seed" name="seed" type="number" step="1" placeholder="(optional)" />

    <div><button type="submit">Download PDF</button></div>
  </form>
  <p><small>v$version</small></p>
</body>
</html>
""")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _PAGE.substitute(
        version=__version__,
        max_clocks=MAX_CLOCKS_PER_PAGE,
        max_pages=MAX_PDF_PAGES,
    )


def _form_on(v: str) -> bool:
    return str(v).strip() not in ("0", "false", "False", "off", "no", "")


@app.post("/worksheet")
def worksheet(
    max_problems: int = Form(6, ge=1, le=MAX_CLOCKS_PER_PAGE),
    pages: int = Form(1, ge=1, le=MAX_PDF_PAGES),
    minutes: str = Form("fives"),
    show_minutes_numbers: str = Form("1"),
    show_minutes_ticks: str = Form("1"),
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
