"""CLI entry point for the bm_analytics pipeline."""

import argparse
import logging
import pathlib
import sys
import time

from src import config, loader
from src import layer1 as _layer1
from src import layer2 as _layer2
from src import layer3_segmentation as _l3seg
from src import layer3_timeseries as _l3ts


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BM Analytics pipeline.")
    p.add_argument(
        "--input-file",
        type=pathlib.Path,
        default=config.INPUT_FILE,
        help="Path to raw_report.csv",
    )
    p.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=config.OUTPUT_DIR,
        help="Directory to write layer reports",
    )
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> int:
    """Run the full bm_analytics pipeline.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    args = _parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    output_dir: pathlib.Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()

    try:
        with config.timed("load"):
            raw = loader.load(args.input_file)

        with config.timed("layer1"):
            l1 = _layer1.build(raw)

        with config.timed("write_layer1"):
            l1_path = output_dir / "layer1_report.csv"
            l1.to_csv(l1_path, index=False)
            logging.info("Wrote %d rows → %s", len(l1), l1_path)

        with config.timed("layer2"):
            l2 = _layer2.build(l1, raw)

        with config.timed("write_layer2"):
            l2_path = output_dir / "layer2_report.csv"
            l2.to_csv(l2_path, index=False)
            logging.info("Wrote %d rows → %s", len(l2), l2_path)

        with config.timed("layer3_segmentation"):
            l3seg = _l3seg.build(l1)

        with config.timed("write_layer3_segmentation"):
            l3seg_path = output_dir / "layer3_segmentation.csv"
            l3seg.to_csv(l3seg_path, index=False)
            logging.info("Wrote %d rows → %s", len(l3seg), l3seg_path)

        with config.timed("layer3_timeseries"):
            l3ts = _l3ts.build(raw)

        with config.timed("write_layer3_timeseries"):
            l3ts_path = output_dir / "layer3_timeseries.csv"
            l3ts.to_csv(l3ts_path, index=False)
            logging.info("Wrote %d rows → %s", len(l3ts), l3ts_path)

    except Exception as exc:
        if args.verbose:
            raise
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    elapsed = time.perf_counter() - start
    print(
        f"Done: {len(raw)} rows in → "
        f"layer1: {len(l1)} rows, "
        f"layer2: {len(l2)} rows, "
        f"layer3_seg: {len(l3seg)} rows, "
        f"layer3_ts: {len(l3ts)} rows  ({elapsed:.2f} s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
