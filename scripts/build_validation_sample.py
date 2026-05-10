"""Build a stratified random sample of LLM classifications for hand-validation.

Reads data/processed/classified_claims.csv. Writes data/processed/validation_sample.csv
with empty my_* / agreement / notes columns to fill in by hand.

Uses stdlib csv (avoids pandas import hangs in this environment).
"""
from __future__ import annotations

import csv
import random
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "processed" / "classified_claims.csv"
DST = REPO_ROOT / "data" / "processed" / "validation_sample.csv"

SEED = 42

# Each stratum: (label, predicate on row dict, target n)
STRATA = [
    ("ACCURATE",             lambda r: r["classification"] == "ACCURATE",             15),
    ("INACCURATE",           lambda r: r["classification"] == "INACCURATE",           15),
    ("PARTIALLY_ACCURATE",   lambda r: r["classification"] == "PARTIALLY_ACCURATE",   15),
    ("OUTSIDE_GROUND_TRUTH", lambda r: r["classification"] == "OUTSIDE_GROUND_TRUTH",  5),
    ("no_claim",             lambda r: r["contains_claim"] == "False",                10),
]

OUTPUT_COLS = [
    "comment_id", "subreddit", "body",
    "llm_comment_type", "llm_category", "llm_classification", "llm_reasoning",
    "my_comment_type", "my_category", "my_classification",
    "agreement", "notes",
]


def normalize_body(b: str) -> str:
    return re.sub(r"\s+", " ", b or "").strip()


def main() -> None:
    with SRC.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"loaded {len(rows)} classified rows from {SRC.name}")

    rng = random.Random(SEED)
    selected: list[dict] = []
    for label, pred, n in STRATA:
        pool = [r for r in rows if pred(r)]
        if len(pool) < n:
            print(f"  ! stratum '{label}' has {len(pool)} rows, requested {n}; taking all")
            picked = pool
        else:
            picked = rng.sample(pool, n)
        for r in picked:
            r["_stratum"] = label
        selected.extend(picked)
        print(f"  stratum '{label}': sampled {len(picked)}")

    DST.parent.mkdir(parents=True, exist_ok=True)
    with DST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in selected:
            w.writerow({
                "comment_id":         r.get("id", ""),
                "subreddit":          r.get("subreddit", ""),
                "body":               normalize_body(r.get("body", "")),
                "llm_comment_type":   r.get("comment_type", ""),
                "llm_category":       r.get("category", ""),
                "llm_classification": r.get("classification", ""),
                "llm_reasoning":      r.get("reasoning", ""),
                "my_comment_type":    "",
                "my_category":        "",
                "my_classification":  "",
                "agreement":          "",
                "notes":              "",
            })

    print(f"\nwrote {DST.relative_to(REPO_ROOT)} ({len(selected)} rows)")
    print(f"  columns: {OUTPUT_COLS}")


if __name__ == "__main__":
    main()
