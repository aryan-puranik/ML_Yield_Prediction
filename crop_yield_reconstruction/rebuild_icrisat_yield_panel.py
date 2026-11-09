"""
Rebuild the ICRISAT district-year-crop yield panel for CAAS Phase 1.

Run from the repository root (or keep this script in the repository root):
    python rebuild_icrisat_yield_panel.py

Dependencies:
    python -m pip install pandas requests

Outputs:
    data/raw_icrisat/districts.json
    data/raw_icrisat/area-production-yield.json
    data/processed/icrisat_yield_panel_all_source_rows.csv
    data/processed/icrisat_yield_panel_repository_filter.csv
    data/processed/icrisat_yield_panel_keep_zero_yield.csv
    data/processed/icrisat_yield_panel_duplicate_keys.csv
    data/processed/reconstruction_audit.json

The repository's build_dataset.py filters to Area > 0 and Yield > 0.
This script reproduces that filter AND saves an alternative retaining zero
yields (Area > 0 and Yield >= 0), so zero-yield records can be investigated.
It reconstructs only yield/area/district/crop data, not weather or other
auxiliary variables.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


API_BASES = [
    "http://data.icrisat.org/dldAPI/apportioned",
    "https://data.icrisat.org/dldAPI/apportioned",
]
YEAR_MIN_DEFAULT, YEAR_MAX_DEFAULT = 1966, 2017

# Crop source column key: (display name, season)
CROPS = {
    "RICE": ("Rice", "Kharif"),
    "WHEAT": ("Wheat", "Rabi"),
    "KHARIF SORGHUM": ("Sorghum (Kharif)", "Kharif"),
    "RABI SORGHUM": ("Sorghum (Rabi)", "Rabi"),
    "PEARL MILLET": ("Pearl Millet", "Kharif"),
    "MAIZE": ("Maize", "Kharif"),
    "FINGER MILLET": ("Finger Millet", "Kharif"),
    "BARLEY": ("Barley", "Rabi"),
    "CHICKPEA": ("Chickpea", "Rabi"),
    "PIGEONPEA": ("Pigeonpea", "Kharif"),
    "MINOR PULSES": ("Minor Pulses", "Whole Year"),
    "GROUNDNUT": ("Groundnut", "Kharif"),
    "SESAMUM": ("Sesamum", "Kharif"),
    "RAPESEED AND MUSTARD": ("Rapeseed & Mustard", "Rabi"),
    "SAFFLOWER": ("Safflower", "Rabi"),
    "CASTOR": ("Castor", "Kharif"),
    "LINSEED": ("Linseed", "Rabi"),
    "SUNFLOWER": ("Sunflower", "Whole Year"),
    "SOYABEAN": ("Soybean", "Kharif"),
    "SUGARCANE": ("Sugarcane", "Whole Year"),
    "COTTON": ("Cotton", "Kharif"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_json(session, name, destination, refresh=False):
    if destination.exists() and not refresh:
        with open(destination, encoding="utf-8") as f:
            obj = json.load(f)
        print(f"[CACHE] {destination}")
        return obj, "local cache", sha256(destination)

    errors = []
    for base in API_BASES:
        url = f"{base}/{name}"
        try:
            response = session.get(url, timeout=(20, 180))
            response.raise_for_status()
            obj = response.json()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with open(destination, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
            print(f"[DOWNLOADED] {name}: HTTP {response.status_code}")
            return obj, response.url, sha256(destination)
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    raise RuntimeError(
        f"Could not retrieve {name}.\n  " + "\n  ".join(errors)
        + "\nCheck the ICRISAT API connection and try again later."
    )


def to_grid_frame(obj, label):
    if not isinstance(obj, dict) or "headers" not in obj or "data" not in obj:
        raise ValueError(
            f"{label}: unexpected API schema. Expected 'headers' and 'data'."
        )
    headers = [
        x["header"] if isinstance(x, dict) else str(x)
        for x in obj["headers"]
    ]
    return pd.DataFrame(obj["data"], columns=headers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year-min", type=int, default=YEAR_MIN_DEFAULT)
    parser.add_argument("--year-max", type=int, default=YEAR_MAX_DEFAULT)
    parser.add_argument(
        "--refresh", action="store_true",
        help="Redownload source JSON instead of using cached raw files."
    )
    args = parser.parse_args()

    if args.year_min > args.year_max:
        parser.error("--year-min must be <= --year-max")

    root = Path(__file__).resolve().parent
    raw_dir = root / "data" / "raw_icrisat"
    out_dir = root / "data" / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "CAAS-academic-yield-reconstruction/1.0"}
    )

    try:
        districts_json, districts_url, districts_hash = get_json(
            session, "districts", raw_dir / "districts.json", args.refresh
        )
        apy_json, apy_url, apy_hash = get_json(
            session, "area-production-yield",
            raw_dir / "area-production-yield.json", args.refresh
        )
    except Exception as exc:
        print(f"\nDOWNLOAD ERROR: {exc}", file=sys.stderr)
        return 1

    if not isinstance(districts_json, list):
        raise ValueError("District endpoint did not return a JSON list.")

    district_rows = []
    for d in districts_json:
        code = pd.to_numeric(d.get("DIST"), errors="coerce")
        if pd.notna(code):
            district_rows.append({
                "District_Code": int(code),
                "District": str(d.get("DISTNAME", "")).strip(),
                "State": str(d.get("STNAME", "")).strip(),
            })
    districts = pd.DataFrame(district_rows)
    if districts.empty:
        raise ValueError("No district records were parsed.")
    if districts["District_Code"].duplicated().any():
        raise ValueError("Duplicate DIST codes in district master; inspect raw JSON.")

    apy = to_grid_frame(apy_json, "area-production-yield")
    for required in ["Dist Code", "Year"]:
        if required not in apy.columns:
            raise ValueError(f"APY source is missing column: {required}")

    apy["District_Code"] = pd.to_numeric(
        apy["Dist Code"], errors="coerce"
    ).astype("Int64")
    apy["Year"] = pd.to_numeric(apy["Year"], errors="coerce").astype("Int64")

    blocks = []
    for crop_key, (crop_name, season) in CROPS.items():
        area_col, yield_col = f"{crop_key} AREA", f"{crop_key} YIELD"
        missing = [c for c in (area_col, yield_col) if c not in apy.columns]
        if missing:
            raise ValueError(
                f"Missing source columns {missing}; inspect downloaded APY JSON."
            )
        blocks.append(pd.DataFrame({
            "District_Code": apy["District_Code"],
            "Year": apy["Year"],
            "Crop_Source_Key": crop_key,
            "Crop": crop_name,
            "Season": season,
            "Area": pd.to_numeric(apy[area_col], errors="coerce"),
            "Yield": pd.to_numeric(apy[yield_col], errors="coerce"),
        }))

    panel = pd.concat(blocks, ignore_index=True)
    panel = panel[
        panel["District_Code"].notna()
        & panel["Year"].notna()
        & panel["Year"].between(args.year_min, args.year_max)
    ].copy()
    panel["District_Code"] = panel["District_Code"].astype("int64")
    panel["Year"] = panel["Year"].astype("int64")

    panel = panel.merge(
        districts, on="District_Code", how="left",
        validate="many_to_one", indicator=True
    )
    panel["District_Matched"] = panel["_merge"].eq("both")
    panel.drop(columns="_merge", inplace=True)
    panel["Region"] = (
        panel["District"].fillna("UNMAPPED DISTRICT")
        + ", "
        + panel["State"].fillna("UNMAPPED STATE")
    )

    panel = panel[
        [
            "District_Code", "District", "State", "Region", "Year",
            "Crop_Source_Key", "Crop", "Season", "Area", "Yield",
            "District_Matched",
        ]
    ].sort_values(
        ["District_Code", "Crop_Source_Key", "Year"]
    ).reset_index(drop=True)

    # Save all source cells before applying the repository's filters.
    all_path = out_dir / "icrisat_yield_panel_all_source_rows.csv"
    panel.to_csv(all_path, index=False)

    # Exact yield/area eligibility filter used by the repository's builder.
    repo_panel = panel[(panel["Area"] > 0) & (panel["Yield"] > 0)].copy()
    repo_path = out_dir / "icrisat_yield_panel_repository_filter.csv"
    repo_panel.to_csv(repo_path, index=False)

    # Alternative retains zero yield for inspection, provided area is positive.
    zero_panel = panel[(panel["Area"] > 0) & (panel["Yield"] >= 0)].copy()
    zero_path = out_dir / "icrisat_yield_panel_keep_zero_yield.csv"
    zero_panel.to_csv(zero_path, index=False)

    keys = ["District_Code", "Year", "Crop_Source_Key"]
    duplicate_rows = repo_panel[
        repo_panel.duplicated(keys, keep=False)
    ].sort_values(keys)
    duplicate_path = out_dir / "icrisat_yield_panel_duplicate_keys.csv"
    duplicate_rows.to_csv(duplicate_path, index=False)

    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "ICRISAT District Level Database (apportioned)",
        "source_urls": {
            "districts": districts_url,
            "area-production-yield": apy_url,
        },
        "sha256": {
            "districts.json": districts_hash,
            "area-production-yield.json": apy_hash,
        },
        "study_period": [args.year_min, args.year_max],
        "filters": {
            "repository_filter": "Area > 0 and Yield > 0",
            "zero_preserving_alternative": "Area > 0 and Yield >= 0",
        },
        "counts": {
            "district_master_rows": int(len(districts)),
            "all_source_long_rows": int(len(panel)),
            "repository_filter_rows": int(len(repo_panel)),
            "zero_preserving_rows": int(len(zero_panel)),
            "missing_area": int(panel["Area"].isna().sum()),
            "missing_yield": int(panel["Yield"].isna().sum()),
            "zero_yield": int(panel["Yield"].eq(0).sum()),
            "negative_yield": int(panel["Yield"].lt(0).sum()),
            "unmatched_district_rows": int((~panel["District_Matched"]).sum()),
            "duplicate_keys_in_repository_filter": int(len(duplicate_rows)),
        },
        "files": {
            "all_source_rows": str(all_path.relative_to(root)),
            "repository_filter": str(repo_path.relative_to(root)),
            "keep_zero_yield": str(zero_path.relative_to(root)),
            "duplicate_keys": str(duplicate_path.relative_to(root)),
        },
        "notes": [
            "Area is retained for auditing and source filtering; do not automatically use it as a predictor.",
            "The repository's builder excludes zero-yield observations. The alternative output retains them for investigation.",
            "Season is a crop-to-season mapping, not a separately observed field in this extraction.",
            "This is a reproducible extraction, not independent certification of the original measurements.",
        ],
    }
    audit_path = out_dir / "reconstruction_audit.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    print("\nRECONSTRUCTION SUMMARY")
    print(f"District master rows:        {len(districts):,}")
    print(f"All source long rows:        {len(panel):,}")
    print(f"Repository-filter rows:      {len(repo_panel):,}")
    print(f"Zero-preserving rows:        {len(zero_panel):,}")
    print(f"Missing yield:               {panel['Yield'].isna().sum():,}")
    print(f"Zero yield:                  {panel['Yield'].eq(0).sum():,}")
    print(f"Negative yield:              {panel['Yield'].lt(0).sum():,}")
    print(f"Unmatched district rows:     {(~panel['District_Matched']).sum():,}")
    print(f"Duplicate filtered keys:     {len(duplicate_rows):,}")
    print("\nCreated:")
    for p in [all_path, repo_path, zero_path, duplicate_path, audit_path]:
        print(" ", p)

    if len(duplicate_rows):
        print("\nWARNING: duplicate district-year-crop keys need investigation.")
    if (~panel["District_Matched"]).any():
        print("\nWARNING: some district codes did not match the district master.")
    print("\nReview reconstruction_audit.json before using any output for ML.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
