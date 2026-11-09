"""Fetch FAOSTAT pesticide use for India (authoritative: UN FAO).
Bulk normalized download -> filter Area=India.
"""
import io, zipfile, requests
import pandas as pd
URL = "https://bulks-faostat.fao.org/production/Inputs_Pesticides_Use_E_All_Data_(Normalized).zip"
r = requests.get(URL, timeout=180)
print("download HTTP", r.status_code, "bytes", len(r.content))
z = zipfile.ZipFile(io.BytesIO(r.content))
print("files:", z.namelist())
csv_name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
with z.open(csv_name) as fh:
    df = pd.read_csv(fh, encoding="latin-1")
print("cols:", list(df.columns))
print("elements:", list(df["Element"].unique()))
india = df[df["Area"] == "India"].copy()
print("India rows:", len(india))
india.to_csv("raw_icrisat/faostat_pesticide_india.csv", index=False)
# Summarize per year for the main 'Use' element
for el in india["Element"].unique():
    sub = india[india["Element"] == el]
    yrs = sorted(sub["Year"].unique())
    if yrs:
        print(f"  [{el}] {sub['Unit'].iloc[0]}: {yrs[0]}..{yrs[-1]} n={len(yrs)}")
