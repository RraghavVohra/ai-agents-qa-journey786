"""
golden_dataset.py -- Step 8 (part 1): Golden Eval Dataset

Generates a synthetic dataset with two deliberately engineered patterns:

1. REAL pattern (channel -> units_sold): a genuine, large, low-noise
   effect. Online vastly outsells Retail. This should verify reliably,
   every time, no matter how the data is split.

2. FAKE pattern (segment -> engagement_score): a coincidental false
   positive. Four normal segments carry no real effect, but a tiny
   3-row "seg_rare" group has a tightly-clustered, artificially elevated
   score. On the FULL dataset this looks extremely significant
   (p ~ 3e-7) -- genuinely fooling a naive "just check the p-value"
   approach. But it's fragile: split the data in half, and the 3 rare
   rows land unevenly, breaking the effect in at least one half.

This is the whole point of the eval: if the Verifier can't tell these
two apart, it isn't doing its job. If it can, that's proof the
architecture works -- not just a demo that happened to produce nice
numbers once.

Deterministic on purpose (fixed seeds) -- rerunning this always
produces the exact same dataset, so the eval result is reproducible,
not a matter of luck.
"""

import pandas as pd
import numpy as np


def generate_golden_dataset(path: str = "golden_dataset.csv"):
    np.random.seed(7)

    n_per_channel = 50
    online = pd.DataFrame({"channel": "Online", "units_sold": np.random.normal(80, 5, n_per_channel)})
    retail = pd.DataFrame({"channel": "Retail", "units_sold": np.random.normal(40, 5, n_per_channel)})
    df = pd.concat([online, retail], ignore_index=True)
    n = len(df)

    # engagement_score is intentionally UNRELATED to channel -- kept low
    # and uniform variance so the rare-group trick below isn't drowned
    # out by channel's much bigger, unrelated effect.
    df["engagement_score"] = np.random.normal(60, 4, n)

    segments = (["seg1", "seg2", "seg3", "seg4"] * ((n - 3) // 4 + 1))[: n - 3]
    segments += ["seg_rare"] * 3
    df["segment"] = segments

    rare_idx = df[df["segment"] == "seg_rare"].index
    df.loc[rare_idx, "engagement_score"] = np.random.normal(75, 1, len(rare_idx))

    df = df.sample(frac=1, random_state=1).reset_index(drop=True)
    df.to_csv(path, index=False)
    return df


if __name__ == "__main__":
    df = generate_golden_dataset()
    print(f"Golden dataset written: {len(df)} rows")
    print(df.head())