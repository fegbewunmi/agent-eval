"""Load a dataset authored as a YAML file (ADR-0003) into the database.

The file is the human-editable, code-reviewed source of truth for authoring; the database
row is the runtime source of truth once loaded. Re-loading the same file is idempotent and
upserts cases by (dataset name, case key).
"""

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, EvaluationCase


def load_dataset_from_file(session: Session, path: str | Path) -> Dataset:
    data = yaml.safe_load(Path(path).read_text())
    ds_meta = data["dataset"]

    dataset = session.query(Dataset).filter_by(name=ds_meta["name"]).one_or_none()
    if dataset is None:
        dataset = Dataset(name=ds_meta["name"], description=ds_meta.get("description"))
        session.add(dataset)
        session.flush()

    existing_cases = {case.key: case for case in dataset.cases}
    for case_data in data["cases"]:
        key = case_data["key"]
        case = existing_cases.get(key)
        if case is None:
            # Assigning the relationship (not dataset_id directly) makes SQLAlchemy append
            # this case to dataset.cases in-memory immediately, via back_populates - not
            # just on the next fresh load. Setting dataset_id=dataset.id here instead was a
            # real bug in Phase 1's runner (docs/phase-notes/phase-1.md): a case added by
            # FK id doesn't show up in an already-loaded `dataset.cases` collection within
            # the same session, e.g. right after this function returns.
            case = EvaluationCase(dataset=dataset, key=key, input={})
            session.add(case)
        case.input = case_data["input"]
        case.expected = case_data.get("expected", {})
        case.tags = case_data.get("tags", [])
        case.case_metadata = case_data.get("metadata", {})

    session.flush()
    return dataset
