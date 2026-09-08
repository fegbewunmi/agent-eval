#!/usr/bin/env python3
"""CLI: load (or update) a dataset file into the database without running anything.
docs/roadmap.md Phase 3 dataset tooling; ADR-0003 (file-authored, DB-loaded datasets).

Usage:
    uv run python ../scripts/load_dataset.py --dataset-file ../datasets/.../cases.yaml
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.services.dataset_loader import load_dataset_from_file  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-file", required=True)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        dataset = load_dataset_from_file(session, args.dataset_file)
        session.commit()
        case_count = len(dataset.cases)
        print(f"Loaded dataset {dataset.name!r} (id={dataset.id}) - {case_count} case(s).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
