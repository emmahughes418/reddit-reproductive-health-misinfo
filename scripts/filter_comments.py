"""Filter automod / deleted / mod-team comments from data/raw/comments.csv.

Writes data/processed/comments_filtered.csv. Run before verify_claims.py.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "raw" / "comments.csv"
DST = REPO_ROOT / "data" / "processed" / "comments_filtered.csv"

# Exact-match exclusions. Avoids false positives on humans with "bot" in their name.
EXCLUDE_AUTHORS = {"AutoModerator", "[deleted]"}


def is_bot_or_mod(author: object) -> bool:
    if not isinstance(author, str):
        return False
    if author in EXCLUDE_AUTHORS:
        return True
    # Subreddit mod-team accounts (e.g., "birthcontrol-ModTeam") are not human conversation
    if author.endswith("-ModTeam"):
        return True
    return False


def main() -> None:
    df = pd.read_csv(SRC)
    mask = df["author"].apply(is_bot_or_mod)
    removed = int(mask.sum())
    kept_df = df[~mask].reset_index(drop=True)

    DST.parent.mkdir(parents=True, exist_ok=True)
    kept_df.to_csv(DST, index=False)

    print(f"Filtered out {removed} automod/bot comments. Running pipeline on {len(kept_df)} human comments.")
    print(f"  excluded breakdown: {df[mask]['author'].value_counts().to_dict()}")
    print(f"  wrote: {DST.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
