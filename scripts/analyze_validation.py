"""Compute agreement statistics from the partially-completed validation_sample.csv.

Reads only rows where the user filled in `agreement` (True/False).
Saves disagreement rows to outputs/validation_disagreements.csv.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "processed" / "validation_sample.csv"
DST = REPO_ROOT / "outputs" / "validation_disagreements.csv"

DISAGREEMENT_COLS = [
    "comment_id", "subreddit", "body",
    "llm_classification", "my_classification",
    "llm_comment_type", "my_comment_type",
    "llm_category", "my_category",
    "llm_reasoning", "notes",
]


def parse_bool(s: str) -> bool | None:
    s = (s or "").strip().lower()
    if s in {"true", "t", "yes", "y", "1"}:
        return True
    if s in {"false", "f", "no", "n", "0"}:
        return False
    return None


def stratum_label(llm_classification: str) -> str:
    if llm_classification == "NOT_APPLICABLE":
        return "non_claim"
    return llm_classification or "(empty)"


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two raters on nominal labels. Returns None if undefined."""
    if not pairs:
        return None
    n = len(pairs)
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    if len(labels) < 2:
        return None
    idx = {lab: i for i, lab in enumerate(labels)}
    matrix = [[0] * len(labels) for _ in labels]
    for a, b in pairs:
        matrix[idx[a]][idx[b]] += 1
    agree = sum(matrix[i][i] for i in range(len(labels)))
    p_o = agree / n
    row_tot = [sum(matrix[i]) for i in range(len(labels))]
    col_tot = [sum(matrix[i][j] for i in range(len(labels))) for j in range(len(labels))]
    p_e = sum((row_tot[i] / n) * (col_tot[i] / n) for i in range(len(labels)))
    if p_e == 1.0:
        return None
    return (p_o - p_e) / (1 - p_e)


def main() -> None:
    with SRC.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    validated = []
    for r in rows:
        agree = parse_bool(r.get("agreement", ""))
        if agree is None:
            continue
        r["_agree"] = agree
        validated.append(r)

    n = len(validated)
    if n == 0:
        print("No validated rows found.")
        return

    n_agree = sum(1 for r in validated if r["_agree"])
    overall_rate = n_agree / n

    by_stratum_total: Counter = Counter()
    by_stratum_agree: Counter = Counter()
    for r in validated:
        s = stratum_label(r["llm_classification"])
        by_stratum_total[s] += 1
        if r["_agree"]:
            by_stratum_agree[s] += 1

    pairs: list[tuple[str, str]] = []
    for r in validated:
        my = (r.get("my_classification") or "").strip()
        if my:
            pairs.append((r["llm_classification"] or "", my))
    kappa = cohen_kappa(pairs)

    disagreements = [r for r in validated if not r["_agree"]]

    print(f"=== validation summary ===")
    print(f"  total rows in sample: {len(rows)}")
    print(f"  validated (agreement filled): {n}")
    print(f"  overall agreement rate: {n_agree}/{n} = {overall_rate:.1%}")
    print()
    print(f"=== agreement by llm_classification stratum ===")
    for s in sorted(by_stratum_total):
        a, t = by_stratum_agree[s], by_stratum_total[s]
        print(f"  {s:<22} {a}/{t} = {a / t:.1%}" if t else f"  {s}: 0/0")
    print()
    if kappa is None:
        print(f"=== Cohen's kappa: not computable (only {len(pairs)} rows have my_classification filled) ===")
    else:
        print(f"=== Cohen's kappa (llm_classification vs my_classification, n={len(pairs)}) ===")
        print(f"  kappa = {kappa:.3f}")
    print()
    print(f"=== disagreements ({len(disagreements)} rows) ===")
    for r in disagreements:
        body = (r.get("body") or "").replace("\n", " ")
        if len(body) > 200:
            body = body[:200] + "..."
        my_cls = (r.get("my_classification") or "").strip() or "(empty)"
        notes = (r.get("notes") or "").strip() or "(no notes)"
        print(f"  - id={r['comment_id']} r/{r['subreddit']}")
        print(f"    body: {body}")
        print(f"    llm: {r['llm_classification']}  →  my: {my_cls}")
        print(f"    notes: {notes}")
        print()

    DST.parent.mkdir(parents=True, exist_ok=True)
    with DST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DISAGREEMENT_COLS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in disagreements:
            w.writerow({k: r.get(k, "") for k in DISAGREEMENT_COLS})

    print(f"wrote {DST.relative_to(REPO_ROOT)} ({len(disagreements)} rows)")


if __name__ == "__main__":
    main()
