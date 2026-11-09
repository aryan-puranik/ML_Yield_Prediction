"""
Build a unified, authentic crop-yield dataset for Precision-Agriculture research.

Schema (exact, in order):
  Year, Region, Crop, Season, Temperature, Rainfall, Humidity, Soil Type, pH,
  Nitrogen, Phosphorus, Potassium, Fertilizer, Pesticide, Yield
Authoritative sources
  - ICRISAT District Level Database (CC BY 4.0) : yield, area, fertilizer N/P/K,
    soil type, district rainfall   -> http://data.icrisat.org/dld/
  - NASA POWER (NASA LaRC)                       : temperature, humidity, rainfall
  - FAOSTAT (UN FAO)                             : pesticide use (India, national)
Derived / flagged
  - Season : crop -> ICAR cropping-calendar season
  - pH     : area-weighted typical pH from ICRISAT soil-order taxonomy
"""
import json
import re
import numpy as np
import pandas as pd
YEAR_MIN, YEAR_MAX = 1966, 2017
RAW = "raw_icrisat"
# ----------------------------------------------------------------------------- helpers
def load_grid(path):
    with open(path, encoding="utf-8") as f:
        j = json.load(f)
    cols = [h["header"] for h in j["headers"]]
    return pd.DataFrame(j["data"], columns=cols)

def num(s):
    return pd.to_numeric(s, errors="coerce")
# ----------------------------------------------------------------------------- 1. districts
with open(f"{RAW}/districts.json", encoding="utf-8") as f:
    dj = json.load(f)
dist_master = {
    int(d["DIST"]): {
        "District": str(d["DISTNAME"]).strip(),
        "State": str(d["STNAME"]).strip(),
        "Lat": d["LAT"], "Lon": d["LONG"],
        "AEZ": d.get("AEZ"), "RegName": d.get("REG_NAME"),
    }
    for d in dj
}
# ----------------------------------------------------------------------------- 2. yield (melt)
CROP_SEASON = {
    "RICE": "Kharif", "WHEAT": "Rabi", "KHARIF SORGHUM": "Kharif",
    "RABI SORGHUM": "Rabi", "PEARL MILLET": "Kharif", "MAIZE": "Kharif",
    "FINGER MILLET": "Kharif", "BARLEY": "Rabi", "CHICKPEA": "Rabi",
    "PIGEONPEA": "Kharif", "MINOR PULSES": "Whole Year", "GROUNDNUT": "Kharif",
    "SESAMUM": "Kharif", "RAPESEED AND MUSTARD": "Rabi", "SAFFLOWER": "Rabi",
    "CASTOR": "Kharif", "LINSEED": "Rabi", "SUNFLOWER": "Whole Year",
    "SOYABEAN": "Kharif", "SUGARCANE": "Whole Year", "COTTON": "Kharif",
}
CROP_DISPLAY = {
    "RICE": "Rice", "WHEAT": "Wheat", "KHARIF SORGHUM": "Sorghum (Kharif)",
    "RABI SORGHUM": "Sorghum (Rabi)", "PEARL MILLET": "Pearl Millet",
    "MAIZE": "Maize", "FINGER MILLET": "Finger Millet", "BARLEY": "Barley",
    "CHICKPEA": "Chickpea", "PIGEONPEA": "Pigeonpea", "MINOR PULSES": "Minor Pulses",
    "GROUNDNUT": "Groundnut", "SESAMUM": "Sesamum",
    "RAPESEED AND MUSTARD": "Rapeseed & Mustard", "SAFFLOWER": "Safflower",
    "CASTOR": "Castor", "LINSEED": "Linseed", "SUNFLOWER": "Sunflower",
    "SOYABEAN": "Soybean", "SUGARCANE": "Sugarcane", "COTTON": "Cotton",
}
apy = load_grid(f"{RAW}/area-production-yield.json")
apy["DIST"] = num(apy["Dist Code"]).astype("Int64")
apy["Year"] = num(apy["Year"]).astype("Int64")
parts = []
for crop in CROP_SEASON:
    a, y = f"{crop} AREA", f"{crop} YIELD"
    sub = pd.DataFrame({
        "DIST": apy["DIST"], "Year": apy["Year"],
        "CropKey": crop,
        "Area": num(apy[a]), "Yield": num(apy[y]),
    })
    parts.append(sub)
yld = pd.concat(parts, ignore_index=True)
yld = yld[(yld["Yield"] > 0) & (yld["Area"] > 0)].copy()
yld = yld[(yld["Year"] >= YEAR_MIN) & (yld["Year"] <= YEAR_MAX)]
print("yield rows:", len(yld))
# ----------------------------------------------------------------------------- 3. fertilizer N/P/K (kg/ha of GCA)
fert = load_grid(f"{RAW}/fertilizer-consumption.json")
fert["DIST"] = num(fert["Dist Code"]).astype("Int64")
fert["Year"] = num(fert["Year"]).astype("Int64")
def clean_rate(s):
    v = num(s)
    return v.where(v >= 0)  # -1 -> NaN
fert_tab = pd.DataFrame({
    "DIST": fert["DIST"], "Year": fert["Year"],
    "Nitrogen": clean_rate(fert["NITROGEN PER HA OF GCA"]),
    "Phosphorus": clean_rate(fert["PHOSPHATE PER HA OF GCA"]),
    "Potassium": clean_rate(fert["POTASH PER HA OF GCA"]),
    "Fertilizer": clean_rate(fert["TOTAL PER HA OF GCA"]),
})
# ----------------------------------------------------------------------------- 4. ICRISAT district rainfall (annual, 1966-2003)
rain = load_grid(f"{RAW}/bio-monthly-rainfall.json")
rain["DIST"] = num(rain["Dist Code"]).astype("Int64")
rain["Year"] = num(rain["Year"]).astype("Int64")
rain_tab = pd.DataFrame({
    "DIST": rain["DIST"], "Year": rain["Year"],
    "Rain_ICRISAT": clean_rate(rain["ANNUAL RAINFALL"]),
})
# normal (30-yr) rainfall as final fallback
nrain = load_grid(f"{RAW}/bio-normal-rainfall.json")
nrain["DIST"] = num(nrain["Dist Code"]).astype("Int64")
normal_rain = dict(zip(nrain["DIST"], num(nrain["ANNUAL NORMAL RAINFALL"])))
# ----------------------------------------------------------------------------- 5. NASA POWER weather
with open("weather_cache.json", encoding="utf-8") as f:
    wc = json.load(f)
wrows = []
for dist_k, rec in wc.items():
    d = int(dist_k)
    for y, v in rec["years"].items():
        wrows.append((d, int(y), v["temp"], v["humidity"], v["rain_mm"]))
wdf = pd.DataFrame(wrows, columns=["DIST", "Year", "T_nasa", "H_nasa", "Rain_nasa"])
# per-district climatological normals (1981-1990) for pre-1981 back-fill
norm = (wdf[wdf["Year"] <= 1990].groupby("DIST")[["T_nasa", "H_nasa"]]
        .mean().rename(columns={"T_nasa": "T_norm", "H_nasa": "H_norm"}))
# ----------------------------------------------------------------------------- 6. soil type + derived pH
# (keyword, USDA soil order, typical pH) -- matched longest-keyword-first.
# Covers ICRISAT spelling variants & suborder names (Ustic/Udic/Aridic etc.)
SOIL_RULES = [
    # Vertisols (incl. "vertic soils" intergrades + misspellings)
    ("VERTISOL", "Vertisols", 7.8), ("VERRTISOL", "Vertisols", 7.8),
    ("USTERT", "Vertisols", 7.8), ("VERTIC", "Vertisols", 7.6),
    ("VRTIC", "Vertisols", 7.6), ("VERTI", "Vertisols", 7.6),
    # Aridisols
    ("ARIDISOL", "Aridisols", 8.0), ("ORTHID", "Aridisols", 8.0),
    # Mollisols
    ("MOLLISOL", "Mollisols", 7.0), ("USTOLL", "Mollisols", 7.2),
    ("UDOLL", "Mollisols", 6.8),
    # Alfisols
    ("ALFISOL", "Alfisols", 6.2), ("USTALF", "Alfisols", 6.2),
    ("UDALF", "Alfisols", 6.0),
    # Inceptisols (incl. tropepts/ochrepts/udepts + misspellings)
    ("INNCEPTISOL", "Inceptisols", 6.8), ("INCEPTISOL", "Inceptisols", 6.8),
    ("USTOCHREPT", "Inceptisols", 6.8), ("OCHREPT", "Inceptisols", 6.8),
    ("DYSTROPEPT", "Inceptisols", 5.6), ("TROPEPT", "Inceptisols", 6.2),
    ("UDUPT", "Inceptisols", 6.4), ("UDEPT", "Inceptisols", 6.4),
    ("AQUEPT", "Inceptisols", 6.5),
    # Entisols (incl. sandy psamments + misspellings)
    ("PSSAMNET", "Entisols", 6.5), ("PSSAMENT", "Entisols", 6.5),
    ("PSAMMENT", "Entisols", 6.5), ("FLUVENT", "Entisols", 7.4),
    ("ORTHENT", "Entisols", 7.0), ("ENTISOL", "Entisols", 7.0),
    # other orders
    ("ULTISOL", "Ultisols", 5.2), ("OXISOL", "Oxisols", 5.0),
    ("HISTOSOL", "Histosols", 4.8),
]
def parse_soil(s):
    """Return (dominant_soil_type, area_weighted_pH) from an ICRISAT soil string."""
    if not isinstance(s, str) or not s.strip() or s.strip().upper() == "NA":
        return (None, None)
    comps = re.split(r"[;]", s)
    weighted_ph, wsum, best_pct, best_order = 0.0, 0.0, -1.0, None
    for c in comps:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", c)
        pct = float(m.group(1)) if m else 100.0 / max(len(comps), 1)
        text = c.upper()
        ph = order = None
        for kw, od, val in SOIL_RULES:
            if kw in text:
                ph, order = val, od
                break
        if ph is not None:
            weighted_ph += ph * pct
            wsum += pct
            if pct > best_pct:
                best_pct, best_order = pct, order
    if wsum == 0:
        return (None, None)
    return (best_order, round(weighted_ph / wsum, 2))
soil = load_grid(f"{RAW}/bio-soil-type.json")
soil["DIST"] = num(soil["Dist Code"]).astype("Int64")
soil_map = {}
for _, r in soil.iterrows():
    st, ph = parse_soil(r["SOIL TYPE PERCENT"])
    soil_map[int(r["DIST"])] = {"SoilType": st, "pH": ph, "raw": r["SOIL TYPE PERCENT"]}
# ----------------------------------------------------------------------------- 7. FAOSTAT pesticide (India, kg/ha cropland)
pest = pd.read_csv(f"{RAW}/faostat_pesticide_india.csv")
pest = pest[pest["Element"] == "Use per area of cropland"][["Year", "Value"]]
pest_by_year = dict(zip(pest["Year"].astype(int), pest["Value"].astype(float)))
pest_years = sorted(pest_by_year)
PEST_MIN = pest_years[0]
# ----------------------------------------------------------------------------- 8. assemble
df = yld.merge(fert_tab, on=["DIST", "Year"], how="left")
df = df.merge(rain_tab, on=["DIST", "Year"], how="left")
df = df.merge(wdf, on=["DIST", "Year"], how="left")
df = df.merge(norm, on="DIST", how="left")
# Region / District / State
df["District"] = df["DIST"].map(lambda d: dist_master.get(d, {}).get("District"))
df["State"] = df["DIST"].map(lambda d: dist_master.get(d, {}).get("State"))
df["Region"] = df["District"].astype(str) + ", " + df["State"].astype(str)

# Crop / Season
df["Crop"] = df["CropKey"].map(CROP_DISPLAY)
df["Season"] = df["CropKey"].map(CROP_SEASON)
# Temperature & Humidity (NASA; pre-1981 -> climatological normal)
df["Temperature"] = df["T_nasa"].fillna(df["T_norm"]).round(2)
df["Humidity"] = df["H_nasa"].fillna(df["H_norm"]).round(1)
df["temp_src"] = np.where(df["T_nasa"].notna(), "NASA_POWER",
                          np.where(df["T_norm"].notna(), "NASA_climatic_normal", "NA"))
# Rainfall: ICRISAT gauge -> NASA -> ICRISAT 30yr normal
df["Rainfall"] = df["Rain_ICRISAT"]
df["rain_src"] = np.where(df["Rain_ICRISAT"].notna(), "ICRISAT_gauge", None)
m = df["Rainfall"].isna() & df["Rain_nasa"].notna()
df.loc[m, "Rainfall"] = df.loc[m, "Rain_nasa"]
df.loc[m, "rain_src"] = "NASA_POWER"
m = df["Rainfall"].isna()
df.loc[m, "Rainfall"] = df.loc[m, "DIST"].map(normal_rain)
df.loc[m, "rain_src"] = "ICRISAT_30yr_normal"
df["Rainfall"] = df["Rainfall"].round(1)
# Soil
df["Soil Type"] = df["DIST"].map(lambda d: soil_map.get(d, {}).get("SoilType"))
df["pH"] = df["DIST"].map(lambda d: soil_map.get(d, {}).get("pH"))

# Pesticide (national; pre-1990 -> earliest available, flagged)
def pest_val(y):
    return pest_by_year.get(y, pest_by_year.get(PEST_MIN))
df["Pesticide"] = df["Year"].map(pest_val).round(4)
df["pest_src"] = np.where(df["Year"] >= PEST_MIN, "FAOSTAT_India",
                          "FAOSTAT_India_backfilled")
# ----------------------------------------------------------------------------- 9. final schema
SCHEMA = ["Year", "Region", "Crop", "Season", "Temperature", "Rainfall",
          "Humidity", "Soil Type", "pH", "Nitrogen", "Phosphorus",
          "Potassium", "Fertilizer", "Pesticide", "Yield"]
final = df.copy()
# require the core agronomic real fields to be present
final = final.dropna(subset=["Temperature", "Humidity", "Rainfall", "Soil Type",
                             "Nitrogen", "Phosphorus", "Potassium", "Fertilizer",
                             "Pesticide", "Yield"])
final = final.sort_values(["State", "District", "Year", "Crop"]).reset_index(drop=True)

clean = final[SCHEMA].copy()
clean.to_csv("crop_yield_dataset.csv", index=False)
prov_cols = SCHEMA + ["State", "District", "temp_src", "rain_src", "pest_src"]
final[prov_cols].to_csv("crop_yield_dataset_with_provenance.csv", index=False)
# ----------------------------------------------------------------------------- 10. report
print("=" * 60)
print("FINAL ROWS:", len(clean))
print("Years:", int(clean['Year'].min()), "-", int(clean['Year'].max()))
print("Districts:", final['District'].nunique(), "| States:", final['State'].nunique())
print("Crops:", clean['Crop'].nunique())
print("\nTemp source:\n", final['temp_src'].value_counts().to_string())
print("\nRain source:\n", final['rain_src'].value_counts().to_string())
print("\nPest source:\n", final['pest_src'].value_counts().to_string())
print("\nNulls per column:\n", clean.isna().sum().to_string())
print("\nHead:\n", clean.head(8).to_string())
