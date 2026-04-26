# Analog clock worksheet

Generate **US Letter** PDF worksheets with random **analog clocks** and answer lines for **hours** and **minutes** useful for teaching time in early grades.

Each page uses a **two-column** layout. Times on a page are **unique** (no duplicate clock times on the same page). The hour hand uses a simplified model: on the hour when minutes are zero; otherwise between the two hour numbers.

## Requirements

- **Python 3.10+**
- Dependencies are listed in `requirements.txt` (ReportLab, FastAPI, Uvicorn, Pydantic).

## Install

From the project root:

```bash
pip install -r requirements.txt
```

This installs the package `analog-clock-worksheet` and the console script **`clock-worksheet`**.

You can also run the module without installing:

```bash
python -m analog_clock_worksheet --help
```

## Command line

```text
clock-worksheet [options]
# or:  python -m analog_clock_worksheet [options]
```

| Option | Description |
|--------|-------------|
| `--max-problems N` | Clocks **per page** (default: 6, max: 10). |
| `--pages P` | Number of pages in one PDF (default: 1, max: 50). |
| `--minutes MODE` | `exact` | `half` | `quarter` (alias `quater`) | `fives` |
| `--output-dir DIR` | Where to write PDFs (default: `output`). |
| `--seed N` | Random seed for reproducible times. |
| `--show-minutes-numbers` / `--no-show-minutes-numbers` | Outer minute labels (5, 10, 15...). |
| `--show-minutes-ticks` / `--no-show-minutes-ticks` | Small 1-minute tick marks. |
| `--version` | Print version and exit. |

PDF files are named like `clock_YYYY-MM-DD_HH-MM-SS.pdf` under the output directory.

### Example

```bash
clock-worksheet --max-problems 8 --minutes fives --pages 2 --seed 42
```

## Web UI

```bash
uvicorn analog_clock_worksheet.web:app --host 0.0.0.0 --port 8000
```

Open the app in a browser, fill the form, and download the generated PDF. Generated files are also saved under `output/` on the server.

## Customizing the PDF

Most layout, fonts, tick sizes, hand arrows, header/footer text, and answer-line labels are controlled by **module-level variables** in:

`src/analog_clock_worksheet/pdf_gen.py`

Examples: `_WORKSHEET_HEADER_TEXT`, `_WORKSHEET_FOOTER_FIELD_SEPARATOR`, hand lengths, hand arrow fractions, and `_ANSWER_BLANK_HOURS_TEXT` / `_ANSWER_BLANK_MINUTES_TEXT`.

## Project layout

```text
src/analog_clock_worksheet/
  pdf_gen.py      # PDF rendering and worksheet layout
  cli.py          # Command-line entry
  web.py          # FastAPI app
  minutes_mode.py # Minute-step modes
  geometry.py     # Simplified hand angles
  output_paths.py # Default output paths / filenames
```

## License

See your repository for license information if applicable.
