import json, os, requests

BASE = "http://data.icrisat.org/dldAPI/apportioned"
OUT = "raw_icrisat"
os.makedirs(OUT, exist_ok=True)
subs = ["soil-type", "normal-rainfall", "monthly-rainfall", "length-of-growing-period", "landuse"]
for s in subs:
    try:
        r = requests.get(f"{BASE}/{s}", timeout=120)
        print(f"\n=== {s}: HTTP {r.status_code} bytes={len(r.content)} ===")
        if r.status_code != 200:
            print("  body:", r.text[:160]); continue
        j = r.json()
        json.dump(j, open(os.path.join(OUT, f"bio-{s}.json"), "w", encoding="utf-8"))
        if isinstance(j, dict):
            print("  items:", j.get("items"))
            print("  elements:", j.get("elements"))
            yrs = j.get("years", [])
            if yrs:
                print(f"  years: {yrs[0]}..{yrs[-1]} (n={len(yrs)})")
            print(f"  data rows: {len(j.get('data', []))}")
            print("  headers:", [h.get("header") for h in j.get("headers", [])])
            if j.get("data"):
                print("  sample row:", j["data"][0])
    except Exception as e:
        print(f"{s}: ERR {type(e).__name__}: {e}")
