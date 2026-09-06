"""Regression test for a real bug (docs/phase-notes/phase-3.md): dataset.cases must
reflect newly-added cases immediately within the same session, not just after a fresh
query — see the fix in app/services/dataset_loader.py (assign the relationship, not the
FK column directly)."""

from pathlib import Path

from app.services.dataset_loader import load_dataset_from_file

DATASET_FILE = Path(__file__).resolve().parents[3] / "datasets" / "stub-agent" / "smoke-v1" / "cases.yaml"


def test_new_dataset_cases_relationship_is_populated_immediately(session):
    dataset = load_dataset_from_file(session, DATASET_FILE)
    assert len(dataset.cases) == 7  # would be 0 if cases were attached by FK id only


def test_reloading_the_same_file_is_idempotent(session):
    load_dataset_from_file(session, DATASET_FILE)
    dataset = load_dataset_from_file(session, DATASET_FILE)
    assert len(dataset.cases) == 7
