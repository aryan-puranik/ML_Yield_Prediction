import csv

path = r"D:\ML_Yield_Prediction\RR_IND_2025_488\Reproducbility Package\raw\DLD\Apportioned\Crops_Area Production Yield.csv"

with open(path, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)

    for i, row in enumerate(reader):
        print(row)
        if i == 4:
            break