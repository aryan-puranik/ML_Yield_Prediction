# Crop Yield Prediction Dataset — Precision Agriculture (India, district-level)

A unified, **authentic, multi-source** panel dataset for crop-yield prediction
research, assembled from authoritative government / inter-governmental open-data
portals. Built for the study *"Design and Development of a Hybrid Deep Learning
Model for Crop Yield Prediction in Precision Agriculture."*

## Files

| File | Description |
|------|-------------|
| `crop_yield_dataset.csv` | **Main deliverable** — exact 15-column schema |
| `crop_yield_dataset_with_provenance.csv` | Same rows + `State`, `District`, and per-cell source/quality flags (`temp_src`, `rain_src`, `pest_src`) |
| `DATASET_README.md` | This document (data dictionary, provenance, methods, limitations) |

## Headline numbers

- **198,369 records** (≈ target of 200,000)
- **309 districts** across **20 Indian states**, **52 years (1966–2017)**, **21 crops**
- **0 missing values** in the main file
- Unit of observation: one **(district × year × crop)** combination

## Schema / Data dictionary

| # | Column | Unit | Source | Granularity | Type |
|---|--------|------|--------|-------------|------|
| 1 | `Year` | year | ICRISAT DLD | district-year | measured |
| 2 | `Region` | "District, State" | ICRISAT DLD | district | measured |
| 3 | `Crop` | name | ICRISAT DLD | — | measured |
| 4 | `Season` | Kharif/Rabi/Whole Year | derived (ICAR cropping calendar) | crop | **derived** |
| 5 | `Temperature` | °C (annual mean, 2 m) | NASA POWER `T2M` | district-year | measured¹ |
| 6 | `Rainfall` | mm (annual total) | ICRISAT gauge ∪ NASA POWER | district-year | measured² |
| 7 | `Humidity` | % (annual mean RH, 2 m) | NASA POWER `RH2M` | district-year | measured¹ |
| 8 | `Soil Type` | USDA soil order | ICRISAT DLD (Biophysical) | district | measured |
| 9 | `pH` | pH (H₂O) | derived from ICRISAT soil-order taxonomy | district | **derived** |
| 10 | `Nitrogen` | kg/ha (of gross cropped area) | ICRISAT DLD (Inputs) — N applied | district-year | measured |
| 11 | `Phosphorus` | kg/ha | ICRISAT DLD — P₂O₅ applied | district-year | measured |
| 12 | `Potassium` | kg/ha | ICRISAT DLD — K₂O applied | district-year | measured |
| 13 | `Fertilizer` | kg/ha | ICRISAT DLD — total NPK applied | district-year | measured |
| 14 | `Pesticide` | kg/ha (of cropland) | FAOSTAT (India, national) | national-year | measured³ |
| 15 | `Yield` | kg/ha | ICRISAT DLD (Area-Production-Yield) | district-year-crop | **measured (target)** |

¹ NASA POWER covers **1981–2017**. For 1966–1980, `Temperature`/`Humidity` are
back-filled with the **per-district 1981–1990 climatological normal** (flagged
`NASA_climatic_normal` in `temp_src`). 73 % of rows use direct satellite values.

² `Rainfall` priority: ICRISAT district rain gauge (1966–2003) → NASA POWER
(2004–2017) → ICRISAT 30-year normal (gap fill). 89 % of rows use ICRISAT gauge
measurements. See `rain_src`.

³ FAOSTAT pesticide use for India is a **national** series (1990–2023); it varies
by year, not by district. Pre-1990 rows carry the earliest (1990) national value
(flagged `FAOSTAT_India_backfilled` in `pest_src`).

## Data sources & citations

1. **ICRISAT District Level Database (DLD)** — Apportioned database (1966 district
   boundaries), variables: Area-Production-Yield, Fertilizer consumption,
   Biophysical (Soil type, Rainfall). Licensed **CC BY 4.0**.
   http://data.icrisat.org/dld/
   *Cite as:* ICRISAT, *District Level Database for Indian Agriculture*, ICRISAT,
   Hyderabad. (Accessed Jun 2026.)

2. **NASA POWER** (Prediction Of Worldwide Energy Resources), NASA Langley
   Research Center — `T2M`, `RH2M`, `PRECTOTCORR` (monthly, AG community).
   https://power.larc.nasa.gov/
   *Cite as:* NASA/POWER CERES/MERRA2 Native Resolution Monthly.

3. **FAOSTAT — Pesticides Use**, Food and Agriculture Organization of the UN.
   https://www.fao.org/faostat/en/#data/RP

## Method summary (reproducible)

The dataset is fully reproducible with the scripts in this folder:

1. `fetch_icrisat.py` — pulls ICRISAT yield + fertilizer JSON via the DLD API.
2. `fetch_biophysical.py` — pulls ICRISAT soil-type + rainfall JSON.
3. `fetch_weather.py` — pulls NASA POWER annual weather for all 313 district
   centroids (cached in `weather_cache.json`, resumable).
4. `fetch_pesticide.py` — downloads the FAOSTAT pesticide bulk file, filters India.
5. `build_dataset.py` — melts crop columns to long format, merges every source on
   `(district, year)`, derives `Season` and `pH`, applies the documented fallbacks,
   drops rows lacking any measured field, and writes the two CSVs.
6. `validate_dataset.py` — sanity-checks ranges, categories and key uniqueness.

### Derived-field methodology

- **Season**: each crop is mapped to its dominant Indian growing season using the
  standard ICAR cropping calendar (e.g., Rice/Maize/Groundnut = *Kharif*;
  Wheat/Chickpea/Mustard = *Rabi*; Sugarcane/Sunflower = *Whole Year*). Sorghum is
  kept split into its native ICRISAT Kharif/Rabi series.
- **pH**: ICRISAT reports the soil-order composition per district (e.g.
  "VERTISOLS – 70%; ALFISOLS – 30%"). pH is the **area-weighted mean** of
  literature-standard typical pH values per USDA soil order
  (Vertisols ≈ 7.8, Aridisols ≈ 8.0, Mollisols ≈ 7.0, Alfisols ≈ 6.2,
  Inceptisols ≈ 6.8, Entisols ≈ 7.0, Ultisols ≈ 5.2). The dominant order is
  reported in `Soil Type`.

## Known limitations (disclose in any publication)

- `Temperature`/`Humidity` for 1966–1980 are climatological normals, not
  inter-annually varying observations (≈ 27 % of rows; see `temp_src`).
- `Pesticide` is a national annual series broadcast to districts (no sub-national
  resolution); pre-1990 values are back-filled.
- `pH` is a taxonomy-derived proxy, constant within a soil order, not an in-situ
  laboratory measurement.
- ICRISAT apportioned boundaries fix districts to their 1966 parents for time-series
  consistency; modern district splits are aggregated to parents.
- Environmental/input covariates are district-year level and therefore identical
  across crops within the same district-year (only `Yield`/`Season` vary by crop) —
  the expected structure for a panel yield-prediction problem.

## License & attribution

Derived from CC BY 4.0 (ICRISAT) and open NASA / FAO data. When using this dataset,
cite all three primary sources above.
