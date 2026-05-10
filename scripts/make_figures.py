"""Generate the 5 paper figures from data/processed/classified_claims.csv.

All figures saved as 300 DPI PNGs to outputs/. Uses stdlib csv + matplotlib
(Agg backend) — does not depend on pandas.
"""
from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

# Set non-interactive backend before importing pyplot
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "processed" / "classified_claims.csv"
OUT = REPO_ROOT / "outputs"

IN_SCOPE = ["pill", "EC", "fertility", "withdrawal", "condoms"]
ACC_CLASSES = ["ACCURATE", "PARTIALLY_ACCURATE", "INACCURATE", "OUTSIDE_GROUND_TRUTH"]
COMMENT_TYPES = ["claim_fact", "personal_experience", "social_encouragement", "other"]

# Color palettes
ACC_COLORS = {
    "ACCURATE":             "#2a9d8f",  # green
    "PARTIALLY_ACCURATE":   "#e9c46a",  # gold
    "INACCURATE":           "#e76f51",  # red-orange
    "OUTSIDE_GROUND_TRUTH": "#9aa0a6",  # gray
}
TYPE_COLORS = {
    "claim_fact":           "#264653",
    "personal_experience":  "#2a9d8f",
    "social_encouragement": "#e9c46a",
    "other":                "#bdbdbd",
}

# Validation results from the hand-labeled sample (carried through)
VALIDATION = [
    ("ACCURATE",            13, 13),
    ("PARTIALLY_ACCURATE",   6,  7),
    ("INACCURATE",           9, 13),
    ("OUTSIDE_GT",           2,  2),
    ("non_claim",            5,  5),
]


def load_rows() -> list[dict]:
    with SRC.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_int(s: str) -> int:
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return 0


def setup_axes(ax):
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="both", labelsize=9)


def fig1_comment_type_by_sub(rows: list[dict]) -> Path:
    subs = sorted({r["subreddit"] for r in rows})
    counts = {sub: Counter(r["comment_type"] or "other" for r in rows if r["subreddit"] == sub) for sub in subs}
    totals = {sub: sum(counts[sub].values()) for sub in subs}

    fig, ax = plt.subplots(figsize=(7, 4))
    bottoms = [0.0] * len(subs)
    for ct in COMMENT_TYPES:
        pcts = [(counts[sub].get(ct, 0) / totals[sub] * 100) if totals[sub] else 0 for sub in subs]
        ax.bar([f"r/{s}\n(n={totals[s]})" for s in subs], pcts, bottom=bottoms,
               label=ct, color=TYPE_COLORS[ct], edgecolor="white", linewidth=0.6)
        bottoms = [b + p for b, p in zip(bottoms, pcts)]

    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_ylabel("share of comments")
    ax.set_title("Comment type composition by subreddit", loc="left", fontsize=11)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), ncol=4, frameon=False, fontsize=8)
    setup_axes(ax)
    fig.tight_layout()
    path = OUT / "fig1_comment_type_by_sub.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def fig2_accuracy_by_category(rows: list[dict]) -> Path:
    claim_rows = [r for r in rows if r.get("comment_type") == "claim_fact"]
    cat_data: dict[str, Counter] = {cat: Counter() for cat in IN_SCOPE}
    for r in claim_rows:
        cat = r.get("category")
        cls = r.get("classification")
        if cat in cat_data and cls in ACC_CLASSES:
            cat_data[cat][cls] += 1
    totals = {cat: sum(cat_data[cat].values()) for cat in IN_SCOPE}

    # Order categories by descending n
    ordered = sorted([c for c in IN_SCOPE if totals[c] > 0], key=lambda c: -totals[c])

    fig, ax = plt.subplots(figsize=(8, 4))
    lefts = [0.0] * len(ordered)
    y_labels = [f"{c}\n(n={totals[c]})" for c in ordered]
    for cls in ACC_CLASSES:
        pcts = [(cat_data[c].get(cls, 0) / totals[c] * 100) if totals[c] else 0 for c in ordered]
        ax.barh(y_labels, pcts, left=lefts, label=cls, color=ACC_COLORS[cls],
                edgecolor="white", linewidth=0.6)
        lefts = [l + p for l, p in zip(lefts, pcts)]

    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_xlabel("share of claims in category")
    ax.set_title("Accuracy distribution within `claim_fact`, by category", loc="left", fontsize=11)
    ax.invert_yaxis()
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.02), ncol=4, frameon=False, fontsize=8)
    setup_axes(ax)
    fig.tight_layout()
    path = OUT / "fig2_accuracy_by_category.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def fig3_upvotes_by_classification(rows: list[dict]) -> Path:
    claim_rows = [r for r in rows if r.get("comment_type") == "claim_fact"]
    classes = ["ACCURATE", "PARTIALLY_ACCURATE", "INACCURATE"]
    data = []
    labels = []
    for cls in classes:
        scores = [max(to_int(r.get("score", "0")), 1) for r in claim_rows if r.get("classification") == cls]
        if not scores:
            continue
        data.append(scores)
        labels.append(f"{cls}\n(n={len(scores)})")

    fig, ax = plt.subplots(figsize=(7, 4))
    bp = ax.boxplot(data, labels=labels, patch_artist=True, widths=0.5,
                    showfliers=True, flierprops=dict(marker="o", markersize=4, alpha=0.5))
    for patch, cls in zip(bp["boxes"], classes):
        patch.set_facecolor(ACC_COLORS[cls])
        patch.set_edgecolor("#333")
        patch.set_alpha(0.85)
    for med in bp["medians"]:
        med.set_color("#222")
        med.set_linewidth(1.5)
    ax.set_yscale("log")
    ax.set_ylabel("comment score (log scale)")
    ax.set_title("Upvote distribution by classification (log scale)", loc="left", fontsize=11)
    setup_axes(ax)
    fig.tight_layout()
    path = OUT / "fig3_upvotes_by_classification.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def fig4_validation(rows: list[dict]) -> Path:
    overall = (35, 40)
    labels = [f"{lab}\n({a}/{t})" for lab, a, t in VALIDATION]
    rates = [a / t * 100 for _, a, t in VALIDATION]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, rates, color="#264653", edgecolor="white", linewidth=0.6)
    overall_line = overall[0] / overall[1] * 100
    ax.axhline(overall_line, color="#e76f51", linestyle="--", linewidth=1.2,
               label=f"overall {overall[0]}/{overall[1]} = {overall_line:.1f}%")
    for bar, r in zip(bars, rates):
        ax.annotate(f"{r:.0f}%", (bar.get_x() + bar.get_width() / 2, r),
                    xytext=(0, 4), textcoords="offset points", ha="center", fontsize=9)

    ax.set_ylim(0, 110)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_ylabel("agreement with hand-rater")
    ax.set_title("LLM-rater agreement by stratum (n=40 hand-validated)", loc="left", fontsize=11)
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    setup_axes(ax)
    fig.tight_layout()
    path = OUT / "fig4_validation_agreement.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def fig5_category_distribution(rows: list[dict]) -> Path:
    claim_rows = [r for r in rows if r.get("comment_type") == "claim_fact"]
    counts = Counter(r.get("category") or "(empty)" for r in claim_rows)
    n_total = sum(counts.values())

    order = IN_SCOPE + ["outside"]
    order = [c for c in order if c in counts]
    values = [counts[c] for c in order]
    pcts = [v / n_total * 100 for v in values]
    colors = ["#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51", "#9aa0a6"][:len(order)]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh(order, values, color=colors, edgecolor="white", linewidth=0.6)
    for bar, v, p in zip(bars, values, pcts):
        ax.annotate(f"{v} ({p:.1f}%)", (v, bar.get_y() + bar.get_height() / 2),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=9)
    ax.set_xlabel("number of claim_fact comments")
    ax.set_xlim(0, max(values) * 1.20)
    ax.set_title(f"Category distribution within `claim_fact` (n={n_total})", loc="left", fontsize=11)
    ax.invert_yaxis()
    setup_axes(ax)
    fig.tight_layout()
    path = OUT / "fig5_category_distribution.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    print(f"loaded {len(rows)} rows")
    for fn in [fig1_comment_type_by_sub, fig2_accuracy_by_category,
               fig3_upvotes_by_classification, fig4_validation, fig5_category_distribution]:
        path = fn(rows)
        print(f"  wrote {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
