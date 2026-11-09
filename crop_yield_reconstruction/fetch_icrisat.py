"""Fetch ICRISAT District Level Database (apportioned) raw JSON.
Source: http://data.icrisat.org/dld/  (CC BY 4.0)
Endpoints reverse-engineered from dldOperations.js:
  /dldAPI/{datatype}/districts
  /dldAPI/{datatype}/{subcategory}
"""
import json
import os
import requests

BASE = "http://data.icrisat.org/dldAPI"
DATATYPE = "apportioned"
OUTDIR = "raw_icrisat"
os.makedirs(OUTDIR, exist_ok=True)
SUBCATS = {
    "districts": f"{BASE}/{DATATYPE}/districts",
    "area-production-yield": f"{BASE}/{DATATYPE}/area-production-yield",
    "fertilizer-consumption": f"{BASE}/{DATATYPE}/fertilizer-consumption",
    "season-fertilizer-consumption": f"{BASE}/{DATATYPE}/season-fertilizer-consumption",
}

sess = requests.Session()
sess.headers.update({"User-Agent": "Mozilla/5.0 research-data-fetch"})
for name, url in SUBCATS.items():
    try:
        r = sess.get(url, timeout=120)
        print(f"{name}: HTTP {r.status_code}  bytes={len(r.content)}")
        if r.status_code != 200:
            print("   body head:", r.text[:200])
            continue
        data = r.json()
        path = os.path.join(OUTDIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        # quick structure summary
        if isinstance(data, list):
            print(f"   list of {len(data)} items; sample keys: {list(data[0].keys()) if data else 'NA'}")
        elif isinstance(data, dict):
            print(f"   dict keys: {list(data.keys())}")
            if "data" in data:
                print(f"   data rows: {len(data['data'])}")
            if "headers" in data:
                print(f"   #headers: {len(data['headers'])}")
            if "items" in data:
                print(f"   items: {data['items']}")
            if "elements" in data:
                print(f"   elements: {data['elements']}")
            if "years" in data:
                yrs = data["years"]
                print(f"   years: {yrs[0]}..{yrs[-1]} (n={len(yrs)})")
    except Exception as e:
        print(f"{name}: ERROR {type(e).__name__}: {e}")
