# Crop yield dataset reconstruction scripts

## Provenance
These six Python scripts are taken from the public MIT-licensed project:
https://github.com/sid09008mane/crop-yield (branch: main, inspected 2026-11-02).
The accompanying DATASET_README.md is user-provided. Original scripts are
available at https://github.com/sid09008mane/crop-yield/blob/main/<script>.py.

The scripts were Python-syntax checked in this package, but live end-to-end
reconstruction could not be tested here because the execution environment
cannot reach the ICRISAT, NASA POWER, or FAOSTAT endpoints. Their availability,
API response structure, and FAOSTAT download names may have changed.

## Run from THIS DIRECTORY (Python 3.11 suggested)

    python -m venv .venv
    # Linux / macOS: source .venv/bin/activate
    # Windows PowerShell: .venv\\Scripts\\Activate.ps1
    pip install -r requirements_reconstruction.txt
    python fetch_icrisat.py
    python fetch_biophysical.py
    python fetch_weather.py
    python fetch_pesticide.py
    python check_required_inputs.py
    python build_dataset.py
    python validate_dataset.py

`fetch_weather.py` makes hundreds of requests and uses a resumable `weather_cache.json`.
Keep downloaded JSON and the weather cache between runs. Source downloads may take
substantial time; failures can occur, and the original fetch scripts sometimes
print errors without stopping the process.

## Required inputs for build_dataset.py

    raw_icrisat/districts.json
    raw_icrisat/area-production-yield.json
    raw_icrisat/fertilizer-consumption.json
    raw_icrisat/bio-monthly-rainfall.json
    raw_icrisat/bio-normal-rainfall.json
    raw_icrisat/bio-soil-type.json
    raw_icrisat/faostat_pesticide_india.csv
    weather_cache.json

`check_required_inputs.py` verifies file existence, JSON parseability and the
expected weather cache nesting before the build. It does NOT verify that
all historical values match the author's archived source snapshot.

## Expected outputs

    crop_yield_dataset.csv
    crop_yield_dataset_with_provenance.csv

The reference README reports 198,369 rows, 309 districts, 20 states, 21 crops
and 1966–2017 coverage. Rebuilding against live data may differ due to updates
and revisions. Compare schema, rows and provenance flag counts; treat differences
as audit findings rather than silently patching the data.

## Research caution

- `pH` and `Season` are derived, not measured at farm level.
- Temperature/Humidity pre-1981 use future climatological normals; avoid these
  years in strict forecasting tests.
- Pesticide is India-wide per-year, not district-specific; pre-1990 backfilled.
- A model that uses realized annual weather is a retrospective yield estimator,
  not necessarily a prospective sowing-time forecast.
- The source files are public and MIT licensed; ICRISAT/FAO/NASA data retain
  their own license and attribution requirements.
