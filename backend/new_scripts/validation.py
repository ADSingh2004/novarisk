from __future__ import annotations

from collections.abc import Iterable


def compare_against_reference(predicted: Iterable[float], reference: Iterable[float]) -> dict[str, float]:
    pred = list(predicted)
    ref = list(reference)
    if len(pred) != len(ref) or len(pred) == 0:
        raise ValueError("predicted and reference must be non-empty and of equal length")

    abs_errors = [abs(p - r) for p, r in zip(pred, ref, strict=False)]
    mae = sum(abs_errors) / len(abs_errors)

    mape_terms = []
    for p, r in zip(pred, ref, strict=False):
        if r != 0:
            mape_terms.append(abs((p - r) / r) * 100.0)
    mape = sum(mape_terms) / len(mape_terms) if mape_terms else 0.0

    return {
        "samples": float(len(pred)),
        "mae": float(mae),
        "mape_pct": float(mape),
    }
