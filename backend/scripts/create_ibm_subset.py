
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[1]

SOURCE = BASE / "data/raw/HI-Small_Trans.csv"
OUTPUT = BASE / "data/processed/HI-Small_MVP_1000.csv"
ROW_MAP = BASE / "data/processed/HI-Small_MVP_source_rows.csv"
LABELS = BASE / "data/evaluation/HI-Small_MVP_labels.csv"

SEED = 42
TARGET = 1000
CHUNK_SIZE = 100_000

if not SOURCE.exists():
    raise FileNotFoundError(SOURCE)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
LABELS.parent.mkdir(parents=True, exist_ok=True)

# Sample candidate rows across the source.
candidates = []
offset = 0

for chunk in pd.read_csv(
    SOURCE,
    chunksize=CHUNK_SIZE,
    dtype={"From Bank": str, "To Bank": str,
           "Account": str, "Account.1": str}
):
    chunk["original_source_row"] = (
        chunk.index.to_numpy() + 2
    )

    n = min(100, len(chunk))
    candidates.append(
        chunk.sample(n=n, random_state=SEED + offset)
    )
    offset += 1

sample = pd.concat(candidates, ignore_index=True)

# Choose sender accounts without consulting labels.
seed_rows = sample.sample(
    n=min(30, len(sample)),
    random_state=SEED
)

seed_accounts = set(
    zip(seed_rows["From Bank"], seed_rows["Account"])
)

# Collect transactions involving selected accounts.
connected = []
for chunk in pd.read_csv(
    SOURCE,
    chunksize=CHUNK_SIZE,
    dtype={"From Bank": str, "To Bank": str,
           "Account": str, "Account.1": str}
):
    chunk["original_source_row"] = (
        chunk.index.to_numpy() + 2
    )

    senders = list(zip(chunk["From Bank"], chunk["Account"]))
    receivers = list(zip(chunk["To Bank"], chunk["Account.1"]))

    mask = [
        a in seed_accounts or b in seed_accounts
        for a, b in zip(senders, receivers)
    ]

    selected = chunk.loc[mask]
    if not selected.empty:
        connected.append(selected)

connected_df = (
    pd.concat(connected, ignore_index=True)
    if connected else sample.iloc[0:0].copy()
)

# Limit connected candidates deterministically.
connected_df = connected_df.sample(
    n=min(750, len(connected_df)),
    random_state=SEED
) if not connected_df.empty else connected_df

# Add random background rows.
remaining = sample[
    ~sample["original_source_row"].isin(
        connected_df["original_source_row"]
    )
]

background = remaining.sample(
    n=min(TARGET - len(connected_df), len(remaining)),
    random_state=SEED
)

result = pd.concat(
    [connected_df, background],
    ignore_index=True
).drop_duplicates(subset=["original_source_row"])

result = result.sort_values(
    "original_source_row"
).reset_index(drop=True)

# Sidecar maps upload-row references to original CSV rows.
result["upload_source_row"] = result.index + 2

result[[
    "upload_source_row", "original_source_row"
]].to_csv(ROW_MAP, index=False)

# Keep labels in a restricted evaluation file.
result[[
    "upload_source_row",
    "original_source_row",
    "Is Laundering"
]].to_csv(LABELS, index=False)

# Preserve the exact 11 columns expected by the
# current FastAPI ingestion endpoint.
original_columns = [
    c for c in result.columns
    if c not in ("original_source_row", "upload_source_row")
]

result[original_columns].to_csv(OUTPUT, index=False)

print("Subset created:", OUTPUT)
print("Rows:", len(result))
print("Original-row mapping:", ROW_MAP)
print("Evaluation labels:", LABELS)
print("Columns:", original_columns)
