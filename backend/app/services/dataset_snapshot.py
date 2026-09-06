"""Dataset drift detection. ADR-0003: Dataset/EvaluationCase are mutable, so every
EvaluationRun records a content hash of the cases it actually used, letting comparisons
flag drift after the fact rather than requiring full dataset versioning."""

import hashlib
import json

from app.models.dataset import EvaluationCase


def compute_dataset_snapshot_hash(cases: list[EvaluationCase]) -> str:
    payload = [
        {"key": case.key, "input": case.input, "expected": case.expected}
        for case in sorted(cases, key=lambda c: c.key)
    ]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode())
    return digest.hexdigest()
