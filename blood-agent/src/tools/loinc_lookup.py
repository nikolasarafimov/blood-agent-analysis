import pandas as pd
from rapidfuzz import process, fuzz
from starlette import requests

from ..models import LabDoc, LoincDoc, LoincMappedItem

_loinc = pd.read_csv("data/loinc.csv", dtype=str)  # minimally needs: LOINC_NUM, LONG_COMMON_NAME, CLASS, EXAMPLE_UCUM_UNITS

def map_to_loinc(doc: LabDoc) -> LoincDoc:
    items = []
    choices = _loinc["LONG_COMMON_NAME"].tolist()
    for obs in doc.items:
        match = process.extractOne(obs.parameter, choices, scorer=fuzz.WRatio)
        loinc_code = None; long_name=None; loinc_class=None
        if match and match[1] > 80:  # threshold—tune per dataset
            row = _loinc[_loinc["LONG_COMMON_NAME"]==match[0]].iloc[0]
            loinc_code = row["LOINC_NUM"]; long_name=row["LONG_COMMON_NAME"]; loinc_class=row.get("CLASS")
        items.append(LoincMappedItem(
            parameter=obs.parameter, value=obs.value, unit=obs.unit,
            ref_range=obs.ref_range, flags=obs.flags,
            loinc_code=loinc_code, loinc_long_name=long_name, class_name=loinc_class
        ))
    return LoincDoc(items=items)

def get_loinc_class(test_name):
    params = {
        "pageSize": 1,  # Get only the first match
        "vocabulary": "LOINC",
        "page": 1,
        "query": test_name
    }

    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    response = requests.get("https://athena.ohdsi.org/api/v1/concepts", params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if data.get("content"):  # Check if results exist
            first_match = data["content"][0]
            if first_match["id"]:
                return f"https://athena.ohdsi.org/search-terms/terms/{first_match['id']}"
    return "No LOINC match found"