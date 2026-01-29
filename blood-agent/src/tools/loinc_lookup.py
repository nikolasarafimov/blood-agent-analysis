from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
from rapidfuzz import process, fuzz

from ..models import LabDoc, LoincDoc, LoincMappedItem

_LOINC_DF: Optional[pd.DataFrame] = None


def _load_loinc_df() -> pd.DataFrame:
    global _LOINC_DF
    if _LOINC_DF is not None:
        return _LOINC_DF

    csv_path = Path(__file__).resolve().parents[2] / "data" / "loinc.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"LOINC file not found at: {csv_path}")

    df = pd.read_csv(csv_path, dtype=str).fillna("")
    required = {"LOINC_NUM", "LONG_COMMON_NAME"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"loinc.csv missing required columns: {sorted(missing)}")

    _LOINC_DF = df
    return df


def _best_loinc_match(parameter: str, threshold: int = 80) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    p = (parameter or "").strip()
    if not p:
        return None, None, None

    df = _load_loinc_df()
    choices: List[str] = df["LONG_COMMON_NAME"].astype(str).tolist()

    match = process.extractOne(p, choices, scorer=fuzz.WRatio)
    if not match:
        return None, None, None

    name, score, _idx = match
    if score < threshold:
        return None, None, None

    row = df.loc[df["LONG_COMMON_NAME"] == name].iloc[0]
    code = row.get("LOINC_NUM") or None
    long_name = row.get("LONG_COMMON_NAME") or None
    loinc_class = row.get("CLASS") or None
    return code, long_name, loinc_class


def map_to_loinc(doc: LabDoc, threshold: int = 80) -> LoincDoc:
    items: List[LoincMappedItem] = []

    for obs in getattr(doc, "items", []) or []:
        code, long_name, loinc_class = _best_loinc_match(getattr(obs, "parameter", ""), threshold=threshold)

        items.append(
            LoincMappedItem(
                parameter=getattr(obs, "parameter", None),
                value=getattr(obs, "value", None),
                unit=getattr(obs, "unit", None),
                ref_range=getattr(obs, "ref_range", None),
                flags=getattr(obs, "flags", None),
                loinc_code=code,
                loinc_long_name=long_name,
                class_name=loinc_class,
            )
        )

    return LoincDoc(items=items)