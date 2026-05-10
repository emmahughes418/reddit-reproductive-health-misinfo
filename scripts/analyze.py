"""Analyze data/processed/classified_claims.csv.

Outputs:
  outputs/results_summary.txt — section-formatted stats for paper copy-paste
  outputs/example_claims.csv  — top 2 INACCURATE/PARTIALLY_ACCURATE examples per
                                in-scope category, ranked by upvote score
"""
from __future__ import annotations

import csv
import statistics
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "processed" / "classified_claims.csv"
SUMMARY_PATH = REPO_ROOT / "outputs" / "results_summary.txt"
EXAMPLES_PATH = REPO_ROOT / "outputs" / "example_claims.csv"

IN_SCOPE_CATEGORIES = ["pill", "EC", "fertility", "withdrawal", "condoms"]
ACCURACY_CLASSES = ["ACCURATE", "INACCURATE", "PARTIALLY_ACCURATE", "OUTSIDE_GROUND_TRUTH"]
COMMENT_TYPES = ["claim_fact", "personal_experience", "social_encouragement", "other"]

# Validation results (n=40 hand-validated rows from prior step)
VALIDATION = {
    "overall_n": 40,
    "overall_agree": 35,
    "by_stratum": [
        ("ACCURATE",             13, 13),
        ("INACCURATE",           9,  13),
        ("PARTIALLY_ACCURATE",   6,  7),
        ("OUTSIDE_GROUND_TRUTH", 2,  2),
        ("non_claim",            5,  5),
    ],
}


def to_int(s: str, default: int = 0) -> int:
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return default


def fmt_pct(n: int, total: int) -> str:
    return f"{(n / total * 100):.1f}%" if total else "—"


def fmt_count(label: str, n: int, total: int, label_w: int = 24) -> str:
    return f"  {label:<{label_w}} {n:>4}  ({fmt_pct(n, total)})"


def section(title: str) -> str:
    return f"\n{'=' * 70}\n{title}\n{'=' * 70}"


def median_mean(values: list[float]) -> tuple[float, float] | None:
    if not values:
        return None
    return statistics.median(values), statistics.fmean(values)


def write_summary(rows: list[dict]) -> str:
    n = len(rows)
    lines: list[str] = []
    lines.append("Reddit Reproductive Health Misinformation — Analysis Summary")
    lines.append(f"Source: data/processed/classified_claims.csv  ({n} comments)")

    # 1. corpus size
    by_sub = Counter(r["subreddit"] for r in rows)
    lines.append(section("1. CORPUS"))
    lines.append(f"  total comments: {n}")
    for sub in sorted(by_sub):
        lines.append(fmt_count(f"r/{sub}", by_sub[sub], n))

    # 2. comment_type distribution
    ct_counts = Counter(r.get("comment_type") or "(empty)" for r in rows)
    lines.append(section("2. COMMENT_TYPE DISTRIBUTION (all comments)"))
    for ct in COMMENT_TYPES + sorted(set(ct_counts) - set(COMMENT_TYPES)):
        if ct in ct_counts:
            lines.append(fmt_count(ct, ct_counts[ct], n))

    # 3 & 4. claim_fact subset: category + classification
    claim_fact_rows = [r for r in rows if r.get("comment_type") == "claim_fact"]
    nf = len(claim_fact_rows)
    lines.append(section("3. CLAIM_FACT SUBSET — CATEGORY DISTRIBUTION"))
    lines.append(f"  claim_fact rows: {nf}")
    cat_counts = Counter(r.get("category") or "(empty)" for r in claim_fact_rows)
    for cat in IN_SCOPE_CATEGORIES + ["outside"] + sorted(set(cat_counts) - set(IN_SCOPE_CATEGORIES) - {"outside"}):
        if cat in cat_counts:
            lines.append(fmt_count(cat, cat_counts[cat], nf))

    cls_counts = Counter(r.get("classification") or "(empty)" for r in claim_fact_rows)
    lines.append(section("4. CLAIM_FACT SUBSET — CLASSIFICATION DISTRIBUTION"))
    for cls in ACCURACY_CLASSES + sorted(set(cls_counts) - set(ACCURACY_CLASSES)):
        if cls in cls_counts:
            lines.append(fmt_count(cls, cls_counts[cls], nf))

    # 5. cross-tab: classification × category
    lines.append(section("5. ACCURACY × CATEGORY (within claim_fact)"))
    lines.append(f"  Rows = category, columns = classification (% within category row)")
    header = "  " + "category".ljust(14) + "  " + "  ".join(c[:6].ljust(6) for c in ACCURACY_CLASSES) + "  total"
    lines.append(header)
    for cat in IN_SCOPE_CATEGORIES + ["outside"]:
        cat_rows = [r for r in claim_fact_rows if r.get("category") == cat]
        total = len(cat_rows)
        if total == 0:
            continue
        cells = []
        for cls in ACCURACY_CLASSES:
            k = sum(1 for r in cat_rows if r.get("classification") == cls)
            cells.append(f"{(k/total*100):>5.1f}%")
        lines.append("  " + cat.ljust(14) + "  " + "  ".join(c.ljust(6) for c in cells) + f"  {total}")

    # 6. subreddit comparison
    lines.append(section("6. PER-SUBREDDIT COMPARISON"))
    for sub in sorted(by_sub):
        sub_rows = [r for r in rows if r["subreddit"] == sub]
        s_n = len(sub_rows)
        lines.append(f"\n  r/{sub}  (n={s_n})")
        # comment_type
        sct = Counter(r.get("comment_type") or "(empty)" for r in sub_rows)
        lines.append("    comment_type:")
        for ct in COMMENT_TYPES:
            if ct in sct:
                lines.append("    " + fmt_count(ct, sct[ct], s_n).lstrip())
        # claim_fact subset accuracy
        cf = [r for r in sub_rows if r.get("comment_type") == "claim_fact"]
        scls = Counter(r.get("classification") or "(empty)" for r in cf)
        lines.append(f"    claim_fact accuracy (n={len(cf)}):")
        for cls in ACCURACY_CLASSES:
            if cls in scls:
                lines.append("    " + fmt_count(cls, scls[cls], len(cf)).lstrip())

    # 7. upvote analysis
    lines.append(section("7. UPVOTE ANALYSIS"))
    lines.append("  By classification (within claim_fact):")
    lines.append(f"    {'class':<22} {'n':>4}  {'median':>7}  {'mean':>7}")
    for cls in ACCURACY_CLASSES:
        scores = [to_int(r.get("score", "0")) for r in claim_fact_rows if r.get("classification") == cls]
        mm = median_mean([float(s) for s in scores])
        if mm:
            lines.append(f"    {cls:<22} {len(scores):>4}  {mm[0]:>7.1f}  {mm[1]:>7.2f}")

    lines.append("\n  By comment_type (all comments):")
    lines.append(f"    {'type':<22} {'n':>4}  {'median':>7}  {'mean':>7}")
    for ct in COMMENT_TYPES:
        scores = [to_int(r.get("score", "0")) for r in rows if r.get("comment_type") == ct]
        mm = median_mean([float(s) for s in scores])
        if mm:
            lines.append(f"    {ct:<22} {len(scores):>4}  {mm[0]:>7.1f}  {mm[1]:>7.2f}")

    # 8. validation summary
    v = VALIDATION
    lines.append(section("8. VALIDATION (hand-labeled stratified sample)"))
    lines.append(f"  validated rows: {v['overall_n']}")
    lines.append(f"  overall agreement: {v['overall_agree']}/{v['overall_n']} = {fmt_pct(v['overall_agree'], v['overall_n'])}")
    lines.append("  by LLM stratum:")
    for label, agree, total in v["by_stratum"]:
        lines.append(f"    {label:<22} {agree}/{total} = {fmt_pct(agree, total)}")
    lines.append("  Cohen's kappa: not computable (my_classification column not filled in this round)")

    return "\n".join(lines) + "\n"


def write_examples(rows: list[dict]) -> int:
    """Top 2 INACCURATE / PARTIALLY_ACCURATE examples per in-scope category, by upvote score."""
    target_classes = ["INACCURATE", "PARTIALLY_ACCURATE"]
    out_rows = []
    for cat in IN_SCOPE_CATEGORIES:
        for cls in target_classes:
            pool = [r for r in rows if r.get("category") == cat and r.get("classification") == cls]
            pool.sort(key=lambda r: -to_int(r.get("score", "0")))
            for r in pool[:2]:
                out_rows.append({
                    "category":        cat,
                    "classification":  cls,
                    "body":            (r.get("body") or "").replace("\n", " ").strip(),
                    "score":           to_int(r.get("score", "0")),
                    "llm_reasoning":   r.get("reasoning", ""),
                    "llm_claim_text":  r.get("claim_text", ""),
                })
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXAMPLES_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["category", "classification", "body", "score", "llm_reasoning", "llm_claim_text"], quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out_rows)
    return len(out_rows)


def main() -> None:
    with SRC.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    summary = write_summary(rows)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(summary, encoding="utf-8")
    n_examples = write_examples(rows)

    print(summary)
    print(f"\nwrote {SUMMARY_PATH.relative_to(REPO_ROOT)}")
    print(f"wrote {EXAMPLES_PATH.relative_to(REPO_ROOT)} ({n_examples} example rows)")


if __name__ == "__main__":
    main()
