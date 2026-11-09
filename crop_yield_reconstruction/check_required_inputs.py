"""Fail early if the eight expected build inputs are absent or not parseable."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
expected = [
    "raw_icrisat/districts.json",
    "raw_icrisat/area-production-yield.json",
    "raw_icrisat/fertilizer-consumption.json",
    "raw_icrisat/bio-monthly-rainfall.json",
    "raw_icrisat/bio-normal-rainfall.json",
    "raw_icrisat/bio-soil-type.json",
    "raw_icrisat/faostat_pesticide_india.csv",
    "weather_cache.json",
]
failed = False
for rel in expected:
    path = root / rel
    if not path.is_file() or not path.stat().st_size:
        print("MISSING:", rel)
        failed = True
        continue
    try:
        if path.suffix == '.json':
            with path.open(encoding='utf-8') as f:
                data = json.load(f)
            if path.name == 'weather_cache.json':
                if not isinstance(data, dict) or not data:
                    raise ValueError('Weather cache has no district data')
                if not all(isinstance(v, dict) and 'years' in v for v in data.values()):
                    raise ValueError('Unexpected weather cache structure')
            if path.name == 'districts.json':
                if not isinstance(data, list) or not data:
                    raise ValueError('District master must be a nonempty list')
        print('OK:', rel, f'({path.stat().st_size:,} bytes)')
    except (ValueError, json.JSONDecodeError, UnicodeError) as err:
        print('INVALID:', rel, err)
        failed = True
print('READY TO BUILD' if not failed else 'NOT READY: fix listed inputs')
sys.exit(1 if failed else 0)
