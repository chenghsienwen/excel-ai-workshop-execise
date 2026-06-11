"""CLI entry point for the BM Report Transformer.

Usage:
    python main.py [--raw-data-dir PATH] [--output-dir PATH] [--verbose]
"""

import argparse
import logging
import pathlib
import sys
import time

import pandas as pd

from src import config
from src import loader
from src import transformer
from src import writer


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)s %(message)s", level=level)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform raw Excel BM-report files into a consolidated CSV."
    )
    parser.add_argument(
        "--raw-data-dir",
        type=pathlib.Path,
        default=config.RAW_DATA_DIR,
        metavar="PATH",
        help="Directory containing source .xlsx files (default: %(default)s).",
    )
    parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=config.OUTPUT_DIR,
        metavar="PATH",
        help="Directory to write raw_report.csv (default: %(default)s).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging including per-stage timing.",
    )
    return parser.parse_args()


def _process_file(path: pathlib.Path) -> pd.DataFrame:
    """Loads and transforms one Excel file into a clean DataFrame.

    Args:
        path: Path to the source ``.xlsx`` file.

    Returns:
        Normalised DataFrame matching ``config.OUTPUT_COLUMNS``.
    """
    with config.timed(f"load:{path.name}"):
        raw_df = loader.load_excel(path)

    product = raw_df["product"].iloc[0] if not raw_df.empty else ""
    year = int(raw_df["year"].iloc[0]) if not raw_df.empty else 0

    with config.timed(f"transform:{path.name}"):
        return transformer.transform(raw_df, product, year)


def main() -> int:
    """Runs the full transformation pipeline.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    args = _parse_args()
    _configure_logging(args.verbose)

    xlsx_files = sorted(args.raw_data_dir.glob("*.xlsx"))
    if not xlsx_files:
        logging.error("No .xlsx files found in %s", args.raw_data_dir)
        return 1

    output_file = args.output_dir / "raw_report.csv"
    pipeline_start = time.perf_counter()

    frames = list(map(_process_file, xlsx_files))

    with config.timed("concat_and_sort"):
        combined = (
            pd.concat(frames, ignore_index=True)
            .sort_values(config.SORT_COLUMNS)
            .reset_index(drop=True)
        )

    with config.timed("write_report"):
        writer.write_report(combined, output_file)

    total_elapsed = time.perf_counter() - pipeline_start
    print(
        f"Done: {len(xlsx_files)} files processed, "
        f"{len(combined)} rows written in {total_elapsed:.2f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
