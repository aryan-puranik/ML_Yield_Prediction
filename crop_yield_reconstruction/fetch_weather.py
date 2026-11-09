"""Fetch annual weather (Temperature, Humidity, Rainfall) per ICRISAT district
from NASA POWER (https://power.larc.nasa.gov). Free, authoritative (NASA/LaRC).
Monthly endpoint returns a YYYY13 key = annual aggregate.
  T2M           -> annual mean 2m air temperature (degC)
  RH2M          -> annual mean 2m relative humidity (%)
  PRECTOTCORR   -> annual mean precipitation (mm/day) ; *365.25 -> annual mm
Caches to weather_cache.json so it is resumable.
"""
import json, os, time, sys
import requests
START, END = 1981, 2017
CACHE = "weather_cache.json"
URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"

with open("raw_icrisat/districts.json", encoding="utf-8") as f:
    districts = json.load(f)

cache = {}
if os.path.exists(CACHE):
    with open(CACHE, encoding="utf-8") as f:
        cache = json.load(f)

sess = requests.Session()
sess.headers.update({"User-Agent": "research-weather-fetch"})
def fill(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if v < -900 else v
total = len(districts)
done = 0
for d in districts:
    key = str(d["DIST"])
    if key in cache:
        done += 1
        continue
    lat, lon = d["LAT"], d["LONG"]
    params = {"parameters": "T2M,RH2M,PRECTOTCORR", "community": "AG",
              "longitude": lon, "latitude": lat, "start": START, "end": END, "format": "JSON"}
    for attempt in range(4):
        try:
            r = sess.get(URL, params=params, timeout=90)
            if r.status_code != 200:
                time.sleep(3); continue
            par = r.json()["properties"]["parameter"]
            rec = {}
            for y in range(START, END + 1):
                k = f"{y}13"
                t = fill(par["T2M"].get(k))
                h = fill(par["RH2M"].get(k))
                p = fill(par["PRECTOTCORR"].get(k))
                rec[str(y)] = {
                    "temp": t,
                    "humidity": h,
                    "rain_mm": round(p * 365.25, 1) if p is not None else None,
                }
            cache[key] = {"dist": d["DISTNAME"], "state": d["STNAME"],
                          "lat": lat, "lon": lon, "years": rec}
            break
        except Exception as e:
            time.sleep(3)
    done += 1
    if done % 10 == 0 or done == total:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        print(f"[{done}/{total}] cached={len(cache)}  last={d['DISTNAME']}", flush=True)
with open(CACHE, "w", encoding="utf-8") as f:
    json.dump(cache, f)
print(f"DONE cached={len(cache)}/{total}", flush=True)
