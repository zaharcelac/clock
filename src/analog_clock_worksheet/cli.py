"""CLI to generate a clock worksheet PDF."""

from __future__ import annotations

import argparse
import random
import sys

from analog_clock_worksheet import __version__
from analog_clock_worksheet.minutes_mode import MinutesMode, allowed_minutes
from analog_clock_worksheet.output_paths import ensure_clock_pdf_path
from analog_clock_worksheet.pdf_gen import MAX_CLOCKS_PER_PAGE, MAX_PDF_PAGES, write_clock_worksheet_pdf


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a US Letter PDF of analog clock faces for time practice."
    )
    p.add_argument(
        "--max-problems",
        type=int,
        default=6,
        metavar="N",
        help=f"Number of clock faces on each page, max {MAX_CLOCKS_PER_PAGE} (default: 6).",
    )
    p.add_argument(
        "--pages",
        type=int,
        default=1,
        metavar="P",
        help=f"How many worksheet pages in the PDF, 1–{MAX_PDF_PAGES} (default: 1).",
    )
    p.add_argument(
        "--minutes",
        type=str,
        default="fives",
        choices=[m.value for m in MinutesMode] + ["quater"],
        help=(
            "Which minute hand positions to allow: "
            "exact (:00 only), half (:00, :30), "
            "quarter (0, 15, 20, 45; 'quater' accepted), fives (step of 5)."
        ),
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help='Directory for PDFs (default: "output"). File name: clock_YYYY-MM-DD_HH-MM-SS.pdf',
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible clock times.",
    )
    p.add_argument(
        "--show-minutes-numbers",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Draw 5, 10, 15, … on the outer ring (default: on).",
    )
    p.add_argument(
        "--show-minutes-ticks",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Draw the small 1-minute tick marks (default: on).",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    n = min(MAX_CLOCKS_PER_PAGE, max(1, int(args.max_problems)))
    pages = max(1, min(MAX_PDF_PAGES, int(args.pages)))
    mode = MinutesMode.from_str(args.minutes)
    minutes_list = list(allowed_minutes(mode))
    rng = random.Random(args.seed)
    out_path = ensure_clock_pdf_path(output_dir=args.output_dir)
    try:
        write_clock_worksheet_pdf(
            out_path,
            max_problems=n,
            minute_values=minutes_list,
            rng=rng,
            show_minutes_numbers=args.show_minutes_numbers,
            show_minutes_ticks=args.show_minutes_ticks,
            minutes_mode=args.minutes,
            pages=pages,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
