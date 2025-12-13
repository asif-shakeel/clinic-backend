# column_normalization.py

def normalize_col(col: str) -> str:
    return (
        col.strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def normalize_columns(df):
    df.columns = [normalize_col(c) for c in df.columns]
    return df


def normalize_list(cols):
    return [normalize_col(c) for c in cols]
