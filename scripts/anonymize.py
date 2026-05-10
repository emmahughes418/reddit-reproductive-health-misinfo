"""Anonymize author columns by SHA-256(author)[:8]. Hash is consistent across files.

Inputs:
  data/raw/posts.csv
  data/raw/comments.csv
  data/processed/classified_claims.csv

Outputs (committable):
  data/anonymized/posts.csv
  data/anonymized/comments.csv
  data/anonymized/classified_claims.csv

Pass-through for already-anonymous tokens [deleted], AutoModerator, *-ModTeam.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    (REPO_ROOT / "data" / "raw" / "posts.csv",                   REPO_ROOT / "data" / "anonymized" / "posts.csv"),
    (REPO_ROOT / "data" / "raw" / "comments.csv",                REPO_ROOT / "data" / "anonymized" / "comments.csv"),
    (REPO_ROOT / "data" / "processed" / "classified_claims.csv", REPO_ROOT / "data" / "anonymized" / "classified_claims.csv"),
]

# Tokens to leave unchanged (not real usernames)
PASSTHROUGH_PREFIXES = ("[deleted]", "AutoModerator")
PASSTHROUGH_SUFFIXES = ("-ModTeam",)


def hash_author(name: str) -> str:
    if not isinstance(name, str) or not name:
        return ""
    if name in PASSTHROUGH_PREFIXES:
        return name
    if any(name.endswith(suf) for suf in PASSTHROUGH_SUFFIXES):
        return name
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]


def process(src: Path, dst: Path) -> tuple[int, int]:
    """Returns (rows, unique_anonymized_authors)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    seen = set()
    for r in rows:
        if "author" in r:
            new = hash_author(r["author"])
            if new not in PASSTHROUGH_PREFIXES and not new.endswith("-ModTeam"):
                seen.add(new)
            r["author"] = new
    with dst.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)
    return len(rows), len(seen)


def main() -> None:
    for src, dst in SOURCES:
        if not src.exists():
            print(f"  ! {src.relative_to(REPO_ROOT)} missing, skipping")
            continue
        n, k = process(src, dst)
        print(f"  wrote {dst.relative_to(REPO_ROOT)}  rows={n}  unique_hashed_authors={k}")


if __name__ == "__main__":
    main()
