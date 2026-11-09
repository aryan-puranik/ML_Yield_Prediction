import pandas as pd
df = pd.read_csv("crop_yield_dataset.csv")
print("ROWS:", len(df), "| COLS:", len(df.columns))
print("Columns:", list(df.columns))
print("\n--- numeric ranges ---")
for c in ["Temperature", "Rainfall", "Humidity", "pH", "Nitrogen",
          "Phosphorus", "Potassium", "Fertilizer", "Pesticide", "Yield"]:
    s = df[c]
    print(f"  {c:12} min={s.min():>10.2f}  mean={s.mean():>10.2f}  max={s.max():>12.2f}")
print("\n--- categorical ---")
print("Seasons:", df["Season"].value_counts().to_dict())
print("Soil types:", df["Soil Type"].value_counts().to_dict())
print("Years:", int(df.Year.min()), "-", int(df.Year.max()), "| #years:", df.Year.nunique())
print("\nCrops:", sorted(df["Crop"].unique()))
print("\nRows per decade:")
print((df.Year // 10 * 10).value_counts().sort_index().to_string())
print("\nDuplicate (Year,Region,Crop,Season) rows:",
      df.duplicated(subset=["Year", "Region", "Crop", "Season"]).sum())
