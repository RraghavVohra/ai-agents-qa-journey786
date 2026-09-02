"""
filter_complete_years.py -- keeps only full calendar years (2017-2025).

2016 has only Nov-Dec (naturally high-pollution months), and 2026 has
only Jan-Sep (missing the high-pollution Oct-Dec months). Averaging by
year with both of those included biases 2016 up and 2026 down --
exactly the kind of thing that could fake an "improving trend" even if
none exists. This strips both partial years out before re-testing.
"""

import pandas as pd

df = pd.read_csv("delhi_aqi.csv")
df["date"] = pd.to_datetime(df["date"])

filtered = df[(df["date"].dt.year >= 2017) & (df["date"].dt.year <= 2025)]

filtered.to_csv("delhi_aqi_complete_years.csv", index=False)
print(f"Kept {len(filtered)} of {len(df)} rows")
print("Years included:", sorted(filtered['date'].dt.year.unique()))