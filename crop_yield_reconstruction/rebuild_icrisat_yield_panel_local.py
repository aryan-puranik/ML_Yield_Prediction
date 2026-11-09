"""Reconstruct ICRISAT district-year-crop panel from the local Apportioned CSV.
Usage: python rebuild_icrisat_yield_panel_local.py --csv "D:\\path\\Crops_Area Production Yield.csv"
Requires: pandas
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

YEAR_MIN_DEFAULT, YEAR_MAX_DEFAULT = 1966, 2017
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path, help="Local Apportioned Crops_Area Production Yield.csv")
    parser.add_argument("--year-min", type=int, default=YEAR_MIN_DEFAULT)
    parser.add_argument("--year-max", type=int, default=YEAR_MAX_DEFAULT)
    args = parser.parse_args()
    if args.year_min > args.year_max:
        parser.error("--year-min must be <= --year-max")
    if not args.csv.is_file():
        parser.error(f"CSV not found: {args.csv}")

    root = Path(__file__).resolve().parent
    out_dir = root / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    apy = pd.read_csv(args.csv, low_memory=False, encoding="utf-8-sig")
    apy.columns = apy.columns.str.strip()
    required = ["Dist Code", "Year", "State Name", "Dist Name"]
    missing = [c for c in required if c not in apy.columns]
    if missing:
        raise ValueError(f"Missing identifier columns: {missing}")

    # The local export includes measurement units; the API used shorter names.
    # Explicit exception handles RICEYIELD (no space) in the provided CSV.
    def column_for(crop, kind):
        if crop == "RICE" and kind == "YIELD":
            candidates = ["RICEYIELD (Kg per ha)", "RICE YIELD (Kg per ha)"]
        else:
            units = "1000 ha" if kind == "AREA" else "Kg per ha"
            candidates = [f"{crop} {kind} ({units})"]
        matches = [c for c in candidates if c in apy.columns]
        if len(matches) != 1:
            raise ValueError(f"Expected one {crop} {kind} column from {candidates}; found {matches}")
        return matches[0]

    apy["District_Code"] = pd.to_numeric(apy["Dist Code"], errors="coerce").astype("Int64")
    apy["Year"] = pd.to_numeric(apy["Year"], errors="coerce").astype("Int64")
    # Keep original source names; a district code should not map to conflicting
    # names/states without a warning in the audit.
    district_map = apy[["District_Code", "Dist Name", "State Name"]].dropna(subset=["District_Code"]).copy()
    district_map["Dist Name"] = district_map["Dist Name"].astype("string").str.strip()
    district_map["State Name"] = district_map["State Name"].astype("string").str.strip()
    conflicts = district_map.groupby("District_Code").agg(
        district_names=("Dist Name", "nunique"), state_names=("State Name", "nunique")
    )
    conflicting_codes = conflicts.index[(conflicts.district_names > 1) | (conflicts.state_names > 1)].tolist()

    blocks = []
    for crop_key, (crop_name, season) in CROPS.items():
        blocks.append(pd.DataFrame({
            "District_Code": apy["District_Code"],
            "District": apy["Dist Name"].astype("string").str.strip(),
            "State": apy["State Name"].astype("string").str.strip(),
            "Year": apy["Year"],
            "Crop_Source_Key": crop_key,
            "Crop": crop_name,
            "Season": season,
            "Area": pd.to_numeric(apy[column_for(crop_key, "AREA")], errors="coerce"),
            "Yield": pd.to_numeric(apy[column_for(crop_key, "YIELD")], errors="coerce"),
        }))
    panel = pd.concat(blocks, ignore_index=True)
    panel = panel[panel["District_Code"].notna() & panel["Year"].notna() &
                  panel["Year"].between(args.year_min, args.year_max)].copy()
    panel["District_Code"] = panel["District_Code"].astype("int64")
    panel["Year"] = panel["Year"].astype("int64")
    panel["District_Matched"] = panel["District"].notna() & panel["State"].notna() & (panel["District"] != "") & (panel["State"] != "")
    panel["Region"] = panel["District"].fillna("UNMAPPED DISTRICT") + ", " + panel["State"].fillna("UNMAPPED STATE")
    panel = panel[["District_Code", "District", "State", "Region", "Year", "Crop_Source_Key", "Crop", "Season", "Area", "Yield", "District_Matched"]].sort_values(["District_Code", "Crop_Source_Key", "Year"]).reset_index(drop=True)

    paths = {
        "all_source_rows": out_dir / "icrisat_yield_panel_all_source_rows.csv",
        "repository_filter": out_dir / "icrisat_yield_panel_repository_filter.csv",
        "keep_zero_yield": out_dir / "icrisat_yield_panel_keep_zero_yield.csv",
        "duplicate_keys": out_dir / "icrisat_yield_panel_duplicate_keys.csv",
    }
    repo_panel = panel[(panel["Area"] > 0) & (panel["Yield"] > 0)].copy()
    zero_panel = panel[(panel["Area"] > 0) & (panel["Yield"] >= 0)].copy()
    keys = ["District_Code", "Year", "Crop_Source_Key"]
    duplicates = repo_panel[repo_panel.duplicated(keys, keep=False)].sort_values(keys)
    for key, frame in [("all_source_rows", panel), ("repository_filter", repo_panel), ("keep_zero_yield", zero_panel), ("duplicate_keys", duplicates)]:
        frame.to_csv(paths[key], index=False)

    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": "ICRISAT District Level Database (local apportioned CSV)",
        "source_file": str(args.csv.resolve()),
        "sha256": {"source_csv": sha256(args.csv)},
        "study_period": [args.year_min, args.year_max],
        "filters": {"repository_filter": "Area > 0 and Yield > 0", "zero_preserving_alternative": "Area > 0 and Yield >= 0"},
        "counts": {
            "district_master_rows": int(panel["District_Code"].nunique()),
            "all_source_long_rows": int(len(panel)),
            "repository_filter_rows": int(len(repo_panel)),
            "zero_preserving_rows": int(len(zero_panel)),
            "missing_area": int(panel["Area"].isna().sum()),
            "missing_yield": int(panel["Yield"].isna().sum()),
            "zero_yield": int(panel["Yield"].eq(0).sum()),
            "negative_yield": int(panel["Yield"].lt(0).sum()),
            "unmatched_district_rows": int((~panel["District_Matched"]).sum()),
            "duplicate_keys_in_repository_filter": int(len(duplicates)),
            "conflicting_district_code_count": len(conflicting_codes),
        },
        "conflicting_district_codes": [int(x) for x in conflicting_codes[:100]],
        "files": {k: str(v.relative_to(root)) for k, v in paths.items()},
        "notes": [
            "District/State names come from CSV rows, not the API district master; exact parity is not established.",
            "Area values remain in 1000 hectares and Yield in kg/ha.",
            "Negative sentinels are preserved in all-source output and excluded by positive-value filters.",
            "Season is a static crop mapping, not an observed variable.",
            "Weather and auxiliary variables are not reconstructed.",
        ],
    }
    audit_path = out_dir / "reconstruction_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nRECONSTRUCTION SUMMARY")
    for key, value in audit["counts"].items():
        print(f"{key}: {value:,}")
    print("\nCreated:")
    for p in [*paths.values(), audit_path]:
        print(" ", p)
    if conflicting_codes:
        print("WARNING: Some district codes have conflicting district/state names. Check audit.")
    if len(duplicates):
        print("WARNING: Duplicate district-year-crop keys detected.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
