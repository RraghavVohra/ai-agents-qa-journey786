"""
profiler.py -- Step 1 of the Data-Analysis Agent

Job of this file, and only this file: look at a raw dataset and describe
its shape -- accurately, in code, with zero LLM involvement.

Why this comes first: every later step (Explorer, Analyst, Verifier) will
read THIS profile instead of the raw data. If this is wrong, everything
built on top of it is wrong too. So we build and test this alone, first,
before writing a single line of LLM code.
"""

import sys
import json
import pandas as pd


def load_dataset(path: str) -> pd.DataFrame:
    """Load a CSV into a DataFrame.

    Kept as its own function (not inlined into main) so that later, when
    we support Excel/JSON files too, we only touch this one function --
    profile_dataset() below never needs to know or care where the data
    came from.
    """
    return pd.read_csv(path)


def profile_column(series: pd.Series) -> dict:
    """Profile a single column.

    Numeric and categorical columns need completely different stats to be
    useful -- a mean/median of a "region" column is meaningless, and a
    top-5 value count of a "price" column usually isn't either. So we
    branch on dtype and give each kind what actually helps the Explorer
    (the next component) form a good hypothesis.
    """
    col_profile = {
        "dtype": str(series.dtype),
        "null_count": int(series.isnull().sum()),
        "null_pct": round(float(series.isnull().mean()) * 100, 2),
    }

    if pd.api.types.is_numeric_dtype(series):
        # Numeric column -> distribution stats.
        has_data = series.notna().any()
        col_profile.update({
            "mean": round(float(series.mean()), 2) if has_data else None,
            "median": round(float(series.median()), 2) if has_data else None,
            "min": float(series.min()) if has_data else None,
            "max": float(series.max()) if has_data else None,
            "std": round(float(series.std()), 2) if has_data else None,
        })
    else:
        # Categorical/text column -> cardinality + most common values.
        value_counts = series.value_counts().head(5)
        col_profile.update({
            "unique_count": int(series.nunique()),
            "top_values": {str(k): int(v) for k, v in value_counts.items()},
        })

    return col_profile


def profile_dataset(df: pd.DataFrame) -> dict:
    """Profile the whole dataset: shape + per-column detail.

    This dict is the ONLY thing the Explorer will ever see in the next
    step -- it will never touch the raw DataFrame directly. That's the
    whole point: one cheap pass here means every later LLM call reads a
    small structured summary instead of re-reading raw rows every time.
    """
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": {col: profile_column(df[col]) for col in df.columns},
    }


if __name__ == "__main__":
    # Standalone test entry point.
    # Running this file directly, with no other component built yet, is
    # the whole proof-in-isolation step. If this prints a sensible profile
    # for a real CSV, step 1 is done -- only then do we move to step 2.
    if len(sys.argv) != 2:
        print("Usage: python profiler.py <path_to_csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    df = load_dataset(csv_path)
    profile = profile_dataset(df)

    print(json.dumps(profile, indent=2))